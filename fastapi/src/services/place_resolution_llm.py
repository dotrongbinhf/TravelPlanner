"""
LLM-Verified Place Resolution Service.

Resolves attraction names from LLM output to verified Google Place IDs:
1. Code: textSearch(name) → top 5 placeIds per attraction
2. Code: get_place_from_db(placeId) → title, address from DB for each candidate
3. ONE LLM call: verify ALL attractions at once — pick correct candidate, detect duplicates
4. Code: verify name↔placeId pairs
5. If retry needed: code re-searches with LLM-suggested alt_query → ONE more LLM call
6. Return: segments with resolved names + placeIds
"""

import asyncio
import json
import logging
import re
from typing import Any, Callable, Coroutine, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from src.tools.maps_tools import places_text_search_id_only
from src.tools.dotnet_tools import get_place_from_db
from src.config import settings

logger = logging.getLogger(__name__)

llm_verify = (
    ChatOpenAI(
        model="google/gemini-3.1-flash-lite-preview",
        api_key=settings.VERCEL_AI_GATEWAY_API_KEY,
        base_url="https://ai-gateway.vercel.sh/v1",
        temperature=0.3,
        streaming=False,
    )
    if settings.USE_VERCEL_AI_GATEWAY
    else ChatGoogleGenerativeAI(
        model="gemini-2.5-flash-lite",
        google_api_key=settings.GOOGLE_GEMINI_API_KEY_PAID,
        temperature=0.3,
        streaming=False,
    )
)

VERIFY_SYSTEM_PROMPT = """You verify attraction names against Google Maps candidates.

For each attraction, pick the candidate that IS that place (names may differ between languages).
If no candidate matches, suggest ONE alternative search query following the ALT LANGUAGE instruction.

Output ONLY a JSON array, one entry per attraction, in order:
[
  {"match": 2, "alt": null},
  {"match": -1, "alt": "Phố cổ Hà Nội"}
]

- match: 0-based candidate index, or -1 if no match
- alt: ONE alternative search query (only when match is -1), or null
- IMPORTANT: if "searched_queries" is shown, those queries already failed to produce correct candidates. You MUST suggest a COMPLETELY DIFFERENT query that is NOT in the searched list.
- IMPORTANT: follow the "ALT LANGUAGE" instruction in the prompt to decide the language for your alt suggestion.
"""

def _extract_json(text_or_list: Any) -> dict:
    """Extract JSON from LLM response text. Local copy to avoid circular import."""
    text = ""
    if isinstance(text_or_list, list):
        for part in text_or_list:
            if isinstance(part, dict) and "text" in part:
                text += part["text"]
            elif isinstance(part, str):
                text += part
    elif isinstance(text_or_list, dict):
        return text_or_list
    else:
        text = str(text_or_list)

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = re.sub(r"```\s*$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"error": "Failed to parse JSON", "raw": text[:500]}

async def _fetch_candidates(
    name: str,
    semaphore: asyncio.Semaphore,
    location_bias: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Fetch candidates for a single attraction name.

    1. textSearch(name) → top 5 placeIds
    2. get_place_from_db for each placeId → title, address

    Returns list of candidate dicts with: placeId, title, address
    """
    async with semaphore:
        logger.info(f"[resolve] Fetching candidates for: '{name}'")

        # Step 1: Text Search → placeIds (primary name)
        all_place_ids = []
        seen_pids = set()

        async def _search_and_collect(query: str):
            try:
                results = await places_text_search_id_only.ainvoke({
                    "query": query,
                    "location_bias": location_bias or "",
                })
            except Exception as e:
                logger.error(f"[resolve] textSearch failed for '{query}': {e}")
                return
            if not results or not isinstance(results, list):
                return
            if isinstance(results[0], dict) and "error" in results[0]:
                logger.error(f"[resolve] textSearch error for '{query}': {results[0]}")
                return
            for r in results:
                pid = r.get("place_id", "")
                if pid and pid not in seen_pids:
                    seen_pids.add(pid)
                    all_place_ids.append(pid)

        await _search_and_collect(name)

        if not all_place_ids:
            return []

        # Step 2: DB lookup for each candidate (parallel within semaphore)
        async def _get_db_info(pid: str) -> Optional[dict]:
            try:
                result = await get_place_from_db.ainvoke({"place_id": pid})
                if isinstance(result, dict) and result.get("success"):
                    data = result.get("data", {})
                    return {
                        "placeId": pid,
                        "title": data.get("title", ""),
                        "address": data.get("address", ""),
                        "category": data.get("category", ""),
                        "db_data": data,
                    }
            except Exception as e:
                logger.error(f"[resolve] DB lookup failed for placeId={pid}: {e}")
            return None

        db_tasks = [_get_db_info(pid) for pid in all_place_ids]
        db_results = await asyncio.gather(*db_tasks)

        candidates = [c for c in db_results if c is not None]
        logger.info(f"[resolve] '{name}' → {len(candidates)} candidates from DB")
        return candidates


def _build_verify_prompt(
    attractions_with_candidates: list[dict],
    destination: str,
    failed_queries: dict[int, list[str]] | None = None,
    alt_language: str | None = "local",
) -> str:
    """Build the human message for LLM verification.

    alt_language controls what kind of alternative the LLM should suggest:
      - "local": suggest alt in the destination's local language
      - "english": suggest alt in English / international name
      - None: final round, no more alt suggestions
    """
    lines = [f"Destination: {destination}\n"]

    # Language instruction for alt suggestions
    if alt_language == "local":
        lines.append("ALT LANGUAGE: If no match, suggest an alternative name in the LOCAL language of the destination (e.g. Vietnamese for Vietnam, Japanese for Japan). Do NOT suggest English names.\n")
    elif alt_language == "english":
        lines.append("ALT LANGUAGE: If no match, suggest the place's ENGLISH / international name as the alt query. Do NOT repeat local-language names that already failed.\n")
    else:
        lines.append("ALT LANGUAGE: This is the FINAL round — set alt to null for ALL entries. No more retries available.\n")

    for i, item in enumerate(attractions_with_candidates):
        name = item["name"]
        search_query = item.get("search_query")
        candidates = item["candidates"]
        lines.append(f'{i}. "{name}"')

        # Show what query was actually searched (if different from name)
        if search_query and search_query != name:
            lines.append(f'   (searched as: "{search_query}")')

        # Show previously failed queries so LLM suggests different ones
        if failed_queries and i in failed_queries:
            lines.append(f"   (searched_queries: {failed_queries[i]})")

        if not candidates:
            lines.append("   (no candidates)")
        else:
            for j, c in enumerate(candidates):
                cat = c.get('category', 'unknown')
                lines.append(f'   {j}: "{c["title"]}" — {c["address"]} (Category: {cat})')
        lines.append("")

    return "\n".join(lines)


def _code_verify(
    llm_results: list,
    attractions_with_candidates: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Code-level verification of LLM's choices.

    Input: flat array from LLM — [{match: 0, alt: null}, ...]
    Checks: placeId not empty, name↔placeId pair is correct.

    Returns (verified, failed) lists with attraction index attached.
    """
    verified = []
    failed = []

    for i, entry in enumerate(llm_results):
        if i >= len(attractions_with_candidates):
            break

        raw_match = entry.get("match", -1)
        if raw_match is None:
            match_idx = -1
        else:
            try:
                match_idx = int(raw_match)
            except ValueError:
                match_idx = -1
                
        alt_query = entry.get("alt")
        candidates = attractions_with_candidates[i]["candidates"]

        # No match → retry with alt_query
        if match_idx == -1 or match_idx is None:
            failed.append({"idx": i, "alt": alt_query})
            continue

        # Invalid index
        if match_idx < 0 or match_idx >= len(candidates):
            failed.append({"idx": i, "alt": alt_query})
            logger.warning(f"[resolve] Invalid match index {match_idx} for attraction {i}")
            continue

        candidate = candidates[match_idx]

        # Check: placeId not empty
        if not candidate.get("placeId"):
            failed.append({"idx": i, "alt": alt_query})
            continue

        # Passed — take title and placeId directly from DB candidate
        verified.append({
            "idx": i,
            "placeId": candidate["placeId"],
            "title": candidate["title"],
            "db_data": candidate.get("db_data"),
        })

    return verified, failed


async def resolve_all_attractions(
    attraction_result: dict[str, Any],
    destination: str = "",
    location_bias: Optional[str] = None,
    on_place_resolved: Optional[Callable[[dict[str, Any]], Coroutine]] = None,
) -> dict[str, Any]:
    """Resolve all attraction names in segments to verified placeIds.

    Flow:
    1. Collect all attraction names (main + includes)
    2. textSearch + DB lookup for each (parallel, Semaphore(5))
    3. ONE LLM call to verify all at once
    4. Code verify name↔placeId
    5. Retry failed with alt_query if LLM suggested one
    6. Code dedup by placeId
    7. Apply back to segments

    Returns the modified attraction_result.
    """
    segments = attraction_result.get("segments", [])
    if not segments:
        return attraction_result

    # --- Step 1: Collect ALL attraction names (main + includes) ---
    all_attractions = []

    for seg_idx, segment in enumerate(segments):
        for attr_idx, attr in enumerate(segment.get("attractions", [])):
            all_attractions.append({
                "name": attr.get("name", ""),
                "segment_idx": seg_idx,
                "attraction_idx": attr_idx,
                "is_include": False,
                "include_idx": -1,
            })

    if not all_attractions:
        return attraction_result

    logger.info(f"[resolve] Resolving {len(all_attractions)} attractions for '{destination}'")

    # --- Step 2: Fetch candidates (parallel) ---
    semaphore = asyncio.Semaphore(5)
    all_candidates = await asyncio.gather(*[
        _fetch_candidates(
            a["name"], semaphore, location_bias
        )
        for a in all_attractions
    ])

    # Track all queries that have been tried per attraction
    searched_queries: dict[int, list[str]] = {}
    for a_idx, info in enumerate(all_attractions):
        searched_queries[a_idx] = [info["name"]]

    awc = []  # attractions_with_candidates
    for a, c in zip(all_attractions, all_candidates):
        search_query = a["name"]
        awc.append({
            "name": a["name"],
            "search_query": search_query,
            "candidates": c
        })

    # --- Step 3: LLM Verify (ONE call) ---
    prompt = _build_verify_prompt(awc, destination, failed_queries=searched_queries, alt_language="local")
    messages = [
        SystemMessage(content=VERIFY_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]

    logger.info(f"[resolve] Calling LLM to verify {len(awc)} attractions...")
    try:
        result = await llm_verify.ainvoke(messages)
        llm_results = _extract_json(result.content)
        # Ensure it's a list (LLM should return array)
        if isinstance(llm_results, dict):
            llm_results = llm_results.get("results", llm_results.get("data", []))
        if not isinstance(llm_results, list):
            llm_results = []
    except Exception as e:
        logger.error(f"[resolve] LLM verify failed: {e}", exc_info=True)
        # Without verify, we return unchanged. No fallback to first candidate to avoid hallucination.
        return attraction_result
    # --- Step 4: Code Verify ---
    verified, failed = _code_verify(llm_results, awc)

    logger.info(f"[resolve] Verified: {len(verified)}, Failed: {len(failed)}")

    # --- Step 5: Retry pipeline (local alt → English alt → drop) ---
    # Track all queries that have been tried per attraction
    # (already initialized before Round 1 as `searched_queries`)

    still_failed_indices = set(f["idx"] for f in failed)

    # --- Round 2: Retry with local-language alt ---
    local_retry_items = [(f["idx"], f["alt"]) for f in failed if f.get("alt")]
    en_retry_items: list[tuple[int, str]] = []

    if local_retry_items:
        logger.info(f"[resolve] Round 2: Retrying {len(local_retry_items)} with local-language alt queries...")

        retry_awc = []
        retry_original_indices = []
        for orig_idx, alt_query in local_retry_items:
            searched_queries.setdefault(orig_idx, []).append(alt_query)
            candidates = await _fetch_candidates(alt_query, semaphore, location_bias)
            retry_awc.append({
                "name": all_attractions[orig_idx]["name"],
                "search_query": alt_query,
                "candidates": candidates,
            })
            retry_original_indices.append(orig_idx)

        if retry_awc:
            # Verify — if still no match, LLM suggests ENGLISH alt this time
            retry_prompt = _build_verify_prompt(
                retry_awc, destination,
                {i: searched_queries.get(retry_original_indices[i], []) for i in range(len(retry_awc))},
                alt_language="english",
            )
            try:
                retry_result = await llm_verify.ainvoke([
                    SystemMessage(content=VERIFY_SYSTEM_PROMPT),
                    HumanMessage(content=retry_prompt),
                ])
                retry_llm = _extract_json(retry_result.content)
                if isinstance(retry_llm, dict):
                    retry_llm = retry_llm.get("results", retry_llm.get("data", []))
                if not isinstance(retry_llm, list):
                    retry_llm = []

                retry_verified, retry_failed_2 = _code_verify(retry_llm, retry_awc)
                # Map back to original indices
                for rv in retry_verified:
                    local_idx = rv["idx"]
                    if local_idx < len(retry_original_indices):
                        rv["idx"] = retry_original_indices[local_idx]
                        verified.append(rv)
                        still_failed_indices.discard(rv["idx"])

                # Collect English alt suggestions for Round 3
                for rf in retry_failed_2:
                    local_idx = rf["idx"]
                    en_alt = rf.get("alt")  # Should be English per our prompt
                    if en_alt and local_idx < len(retry_original_indices):
                        orig_idx = retry_original_indices[local_idx]
                        if orig_idx in still_failed_indices:
                            searched_queries.setdefault(orig_idx, []).append(en_alt)
                            en_retry_items.append((orig_idx, en_alt))
            except Exception as e:
                logger.error(f"[resolve] Round 2 LLM verify failed: {e}")

    # --- Round 3: Retry with English alt ---
    if en_retry_items:
        logger.info(f"[resolve] Round 3: Retrying {len(en_retry_items)} with English names...")
        en_awc = []
        en_original_indices = []
        for orig_idx, en_query in en_retry_items:
            candidates = await _fetch_candidates(en_query, semaphore, location_bias)
            en_awc.append({
                "name": all_attractions[orig_idx]["name"],
                "search_query": en_query,
                "candidates": candidates,
            })
            en_original_indices.append(orig_idx)

        if en_awc:
            # Final verify — no more alt suggestions
            en_prompt = _build_verify_prompt(
                en_awc, destination,
                {i: searched_queries.get(en_original_indices[i], []) for i in range(len(en_awc))},
                alt_language=None,
            )
            try:
                en_result = await llm_verify.ainvoke([
                    SystemMessage(content=VERIFY_SYSTEM_PROMPT),
                    HumanMessage(content=en_prompt),
                ])
                en_llm = _extract_json(en_result.content)
                if isinstance(en_llm, dict):
                    en_llm = en_llm.get("results", en_llm.get("data", []))
                if not isinstance(en_llm, list):
                    en_llm = []

                en_verified, _ = _code_verify(en_llm, en_awc)
                for ev in en_verified:
                    local_idx = ev["idx"]
                    if local_idx < len(en_original_indices):
                        ev["idx"] = en_original_indices[local_idx]
                        verified.append(ev)
                logger.info(f"[resolve] Round 3: resolved {len(en_verified)} more")
            except Exception as e:
                logger.error(f"[resolve] Round 3 English retry failed: {e}")

    # Log dropped attractions after all retries
    final_verified_indices = {v["idx"] for v in verified}
    dropped = [all_attractions[i]["name"] for i in range(len(all_attractions)) if i not in final_verified_indices]
    if dropped:
        logger.warning(f"[resolve] DROPPED after all retries: {dropped}")

    # --- Step 6: Dedup by placeId (code, not LLM) ---
    seen_place_ids = {}
    duplicate_indices = set()
    for v in verified:
        pid = v["placeId"]
        if pid in seen_place_ids:
            logger.warning(f"[resolve] Duplicate placeId {pid}: idx {v['idx']} duplicates idx {seen_place_ids[pid]}")
            duplicate_indices.add(v["idx"])
        else:
            seen_place_ids[pid] = v["idx"]

    # --- Step 7: Apply to segments ---
    resolved_map = {}
    for v in verified:
        idx = v["idx"]
        if idx not in duplicate_indices:
            db_data = v.get("db_data") or {}
            location = db_data.get("location")
            resolved_map[idx] = {
                "placeId": v["placeId"],
                "title": v["title"],
                "location": location,
                "db_data": db_data,
            }

    _apply_to_segments(attraction_result, all_attractions, resolved_map, duplicate_indices, on_place_resolved=on_place_resolved)

    # Fire callback for each resolved place
    if on_place_resolved:
        for v in verified:
            if v["idx"] not in duplicate_indices:
                db_data = v.get("db_data") or {}
                location = db_data.get("location") or {}
                coords = location.get("coordinates", [0, 0])
                lat = coords[1] if len(coords) > 1 else 0
                lng = coords[0] if len(coords) > 0 else 0
                if lat != 0 and lng != 0:
                    try:
                        await on_place_resolved({
                            "placeId": v["placeId"],
                            "name": v["title"],
                            "lat": lat,
                            "lng": lng,
                            "agentName": "attraction_agent",
                        })
                    except Exception as e:
                        logger.error(f"[resolve] on_place_resolved callback failed: {e}")

    logger.info(f"[resolve] Final: {len(resolved_map)}/{len(all_attractions)} resolved, "
                f"{len(duplicate_indices)} duplicates removed")

    return attraction_result


def _apply_to_segments(
    attraction_result: dict,
    all_attractions: list[dict],
    resolved_map: dict[int, dict],
    duplicate_indices: set[int],
    on_place_resolved: Optional[Callable] = None,
) -> None:
    """Apply resolved placeId + name back to segments."""
    segments = attraction_result.get("segments", [])
    removals = {}  # (seg_idx, attr_idx) → True

    for global_idx, info in enumerate(all_attractions):
        seg_idx = info["segment_idx"]
        attr_idx = info["attraction_idx"]

        if seg_idx >= len(segments):
            continue
        attractions = segments[seg_idx].get("attractions", [])
        if attr_idx >= len(attractions):
            continue
        attraction = attractions[attr_idx]

        if global_idx in duplicate_indices:
            removals[(seg_idx, attr_idx)] = True
            continue

        if global_idx in resolved_map:
            resolved = resolved_map[global_idx]
            attraction["name"] = resolved["title"]
            attraction["placeId"] = resolved["placeId"]
            if resolved.get("location"):
                attraction["_location"] = resolved["location"]
            if resolved.get("db_data"):
                attraction["db_data"] = resolved["db_data"]

    # Remove duplicates (reverse order to preserve indices)
    for seg_idx in range(len(segments)):
        attrs = segments[seg_idx].get("attractions", [])
        to_remove = sorted(
            [ai for (si, ai) in removals if si == seg_idx],
            reverse=True,
        )
        for idx in to_remove:
            if idx < len(attrs):
                removed = attrs.pop(idx)
                logger.info(f"[resolve] Removed duplicate: '{removed.get('name', '?')}'")

async def resolve_place_names_batch(
    names: list[str],
    destination: str,
    location_bias: str | None = None,
) -> list[dict]:
    """Batch resolve a list of attraction names using LLM verification.
    
    Returns a list of dicts:
    [
        {
            "original_name": "...",
            "placeId": "...",
            "title": "...",
            "db_data": { full db record }
        },
        ...
    ]
    Ignores names that could not be resolved.
    """
    if not names:
        return []

    logger.info(f"[resolve] Batch resolving {len(names)} names for '{destination}'")
    semaphore = asyncio.Semaphore(5)

    all_candidates = await asyncio.gather(*[
        _fetch_candidates(name, semaphore, location_bias)
        for name in names
    ])

    awc = []
    for name, candidates in zip(names, all_candidates):
        awc.append({
            "name": name,
            "search_query": name,
            "candidates": candidates
        })

    # LLM Verify (ONE call)
    prompt = _build_verify_prompt(awc, destination, alt_language=None)
    
    try:
        result = await llm_verify.ainvoke([
            SystemMessage(content=VERIFY_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ])
        llm_results = _extract_json(result.content)
        if isinstance(llm_results, dict):
            llm_results = llm_results.get("results", llm_results.get("data", []))
        if not isinstance(llm_results, list):
            llm_results = []
            
        verified, _ = _code_verify(llm_results, awc)
    except Exception as e:
        logger.error(f"[resolve] Batch LLM verify failed: {e}")
        verified = []

    resolved_list = []
    for v in verified:
        idx = v["idx"]
        if idx < len(names):
            resolved_list.append({
                "original_name": names[idx],
                "placeId": v["placeId"],
                "title": v["title"],
                "db_data": v.get("db_data"),
            })
            
    return resolved_list
