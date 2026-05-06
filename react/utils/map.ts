import { ItineraryItem } from "@/types/itineraryItem";
import { ItineraryItemsRoute } from "@/types/itineraryItemsRoute";

export function isPlacedItem(item: ItineraryItem): boolean {
  return !!item.place?.location?.coordinates;
}

export function hasEnoughPlacedItems(items: ItineraryItem[]): boolean {
  if (!items) return false;
  return items.filter(isPlacedItem).length >= 2;
}

export function hasMiddleUnplacedItems(items: ItineraryItem[]): boolean {
  if (!items || items.length < 2) return false;

  // Find index of first and last placed items
  const firstPlacedIndex = items.findIndex(isPlacedItem);
  const lastPlacedIndex = items.findLastIndex(isPlacedItem);

  // If fewer than 2 placed items, no "middle" to check
  if (
    firstPlacedIndex === -1 ||
    lastPlacedIndex === -1 ||
    firstPlacedIndex === lastPlacedIndex
  ) {
    return false;
  }

  // Check if any item between firstPlaced and lastPlaced is unplaced
  for (let i = firstPlacedIndex + 1; i < lastPlacedIndex; i++) {
    if (!isPlacedItem(items[i])) {
      return true;
    }
  }

  return false;
}

export function splitIntoPlacedSegments(
  items: ItineraryItem[],
): ItineraryItem[][] {
  if (!items || items.length < 2) return [];

  const segments: ItineraryItem[][] = [];
  let currentSegment: ItineraryItem[] = [];

  for (const item of items) {
    if (isPlacedItem(item)) {
      currentSegment.push(item);
    } else {
      // Unplaced item breaks the segment
      if (currentSegment.length >= 2) {
        segments.push(currentSegment);
      }
      currentSegment = [];
    }
  }

  // last segment
  if (currentSegment.length >= 2) {
    segments.push(currentSegment);
  }

  return segments;
}

export function generateGoogleMapsLink(
  items: ItineraryItem[],
  existingRoutes: ItineraryItemsRoute[],
  travelMode: string = "driving",
): string {
  if (!items || items.length < 2) return "";

  // Filter to only placed items
  const placedItems = items.filter(isPlacedItem);
  if (placedItems.length < 2) return "";

  const originItem = placedItems[0];
  const destinationItem = placedItems[placedItems.length - 1];

  const originCoords = originItem.place?.location?.coordinates;
  const destCoords = destinationItem.place?.location?.coordinates;

  if (!originCoords || !destCoords) return "";

  // Origin and destination as lat,lng strings
  const origin = `${originCoords[1]},${originCoords[0]}`;
  const destination = `${destCoords[1]},${destCoords[0]}`;

  // 2. Build via waypoints using custom routes between places and intermediate places
  const waypointsList: string[] = [];

  for (let i = 0; i < placedItems.length - 1; i++) {
    const startItem = placedItems[i];
    const endItem = placedItems[i + 1];

    // Find custom waypoints for this segment from existingRoutes
    const route = existingRoutes.find(
      (r) =>
        r.startItineraryItemId === startItem.id &&
        r.endItineraryItemId === endItem.id,
    );

    const customWaypoints = route?.waypoints ?? [];

    // Add custom waypoints
    customWaypoints
      .sort((a, b) => a.order - b.order)
      .forEach((wp) => {
        waypointsList.push(`${wp.lat},${wp.lng}`);
      });

    // Add the next place as a waypoint (if it's not the final destination)
    if (i < placedItems.length - 2) {
      const nextPlaceCoords = endItem.place?.location?.coordinates;
      if (nextPlaceCoords) {
        waypointsList.push(`${nextPlaceCoords[1]},${nextPlaceCoords[0]}`);
      }
    }
  }

  // 3. Construct the Google Maps URL
  const baseUrl = "https://www.google.com/maps/dir/?api=1";
  const params = new URLSearchParams();

  params.append("origin", origin);
  params.append("destination", destination);

  if (waypointsList.length > 0) {
    params.append("waypoints", waypointsList.join("|"));
  }

  params.append("travelmode", travelMode);

  return `${baseUrl}&${params.toString()}`;
}
