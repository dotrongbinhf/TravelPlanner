"use client";

import { useState, useCallback, useRef } from "react";
import { AgentEvent, AgentStreamState } from "@/api/aiChat/types";
import { TokenStorage } from "@/utils/tokenStorage";
import { refreshToken } from "@/api/auth/auth";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_ENDPOINT;

/**
 * Custom hook for streaming AI agent events via SSE (Server-Sent Events).
 *
 * Sends a message via HTTP POST to the .NET API and reads back SSE events.
 * No persistent connection — each message creates a new HTTP request that
 * returns an SSE stream, which closes automatically when the workflow completes.
 *
 */
export function useAgentStream() {
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamState, setStreamState] = useState<AgentStreamState>({
    events: [],
    activeAgents: [],
    completedAgents: [],
    streamedContent: "",
    structuredData: null,
    isComplete: false,
    error: null,
  });

  // AbortController for cancelling in-flight requests
  const abortControllerRef = useRef<AbortController | null>(null);

  /**
   * Process a single SSE event and update stream state.
   */
  const processEvent = useCallback((event: AgentEvent) => {
    setStreamState((prev) => {
      const newEvents = [...prev.events, event];
      let activeAgents = [...prev.activeAgents];
      let completedAgents = [...prev.completedAgents];
      let streamedContent = prev.streamedContent;
      let isComplete = prev.isComplete;
      let error = prev.error;

      switch (event.eventType) {
        case "agent_start":
          if (event.agentName && !activeAgents.includes(event.agentName)) {
            activeAgents.push(event.agentName);
          }
          break;

        case "agent_end":
          if (event.agentName) {
            activeAgents = activeAgents.filter((a) => a !== event.agentName);
            if (!completedAgents.includes(event.agentName)) {
              completedAgents.push(event.agentName);
            }
          }
          break;

        case "text_chunk":
          if (event.content) {
            streamedContent += event.content;
          }
          break;

        case "structured_data":
          if (event.structuredData) {
            if (event.agentName) {
              return {
                ...prev,
                events: newEvents,
                structuredData: {
                  ...(prev.structuredData || {}),
                  [event.agentName]: event.structuredData,
                },
              };
            }

            return {
              ...prev,
              events: newEvents,
              structuredData: {
                ...(prev.structuredData || {}),
                ...event.structuredData,
              },
            };
          }
          break;

        case "workflow_complete":
          activeAgents = [];
          isComplete = true;
          // Only use finalResponse as fallback when no streaming occurred
          if (event.finalResponse && !streamedContent) {
            streamedContent = event.finalResponse;
          }
          break;

        case "error":
          error = event.errorMessage || "Unknown error occurred";
          isComplete = true;
          activeAgents = [];
          break;
      }

      return {
        events: newEvents,
        activeAgents,
        completedAgents,
        streamedContent,
        structuredData: prev.structuredData,
        isComplete,
        error,
      };
    });

    // If workflow is complete or errored, stop streaming
    if (
      event.eventType === "workflow_complete" ||
      event.eventType === "error"
    ) {
      setIsStreaming(false);
    }
  }, []);

  /**
   * Send a message to the AI agent system via HTTP POST.
   * The response is an SSE stream that delivers agent events in real-time.
   *
   * Lifecycle: POST request opens → SSE events stream → workflow_complete → HTTP closes
   */
  const sendMessage = useCallback(
    async (conversationId: string, message: string) => {
      // Cancel any in-flight request
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Reset stream state for new message
      setStreamState({
        events: [],
        activeAgents: [],
        completedAgents: [],
        streamedContent: "",
        structuredData: null,
        isComplete: false,
        error: null,
      });
      setIsStreaming(true);

      const abortController = new AbortController();
      abortControllerRef.current = abortController;

      try {
        const makeStreamRequest = async (token: string | null) => {
          return fetch(
            `${API_BASE_URL}/api/aichat/conversations/${conversationId}/messages/stream`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                ...(token ? { Authorization: `Bearer ${token}` } : {}),
              },
              body: JSON.stringify({ content: message }),
              signal: abortController.signal,
            },
          );
        };

        let token = TokenStorage.getAccessToken();
        let response = await makeStreamRequest(token);

        // Auto-refresh
        if (response.status === 401) {
          try {
            const refreshResult = await refreshToken();
            const newToken = refreshResult.accessToken;
            TokenStorage.setAccessToken(newToken);
            response = await makeStreamRequest(newToken);
          } catch {
            TokenStorage.removeAccessToken();
            window.location.href = "/login";
            return;
          }
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error("No response body — SSE streaming not supported");
        }

        // Read SSE stream
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Process complete SSE lines
          const lines = buffer.split("\n");
          // Keep the last potentially incomplete line in the buffer
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              try {
                const event = JSON.parse(line.slice(6)) as AgentEvent;
                processEvent(event);
              } catch (e) {
                console.warn(
                  "[AgentStream] Failed to parse SSE event:",
                  line,
                  e,
                );
              }
            }
          }
        }

        // Process any remaining data in buffer
        if (buffer.startsWith("data: ")) {
          try {
            const event = JSON.parse(buffer.slice(6)) as AgentEvent;
            processEvent(event);
          } catch {
            /* ignore incomplete final line */
          }
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === "AbortError") {
          console.log("[AgentStream] Request aborted");
          return;
        }

        console.error("[AgentStream] Failed to stream:", err);
        setIsStreaming(false);
        setStreamState((prev) => ({
          ...prev,
          error:
            err instanceof Error
              ? err.message
              : "Failed to connect to agent system",
          isComplete: true,
        }));
      } finally {
        if (abortControllerRef.current === abortController) {
          abortControllerRef.current = null;
        }
      }
    },
    [processEvent],
  );

  return {
    sendMessage,
    streamState,
    isStreaming,
    isConnected: true, // Always "connected" — no persistent connection to manage
  };
}
