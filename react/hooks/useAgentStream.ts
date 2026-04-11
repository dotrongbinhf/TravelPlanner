"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import * as signalR from "@microsoft/signalr";
import { AgentEvent, AgentStreamState, ResolvedPlace } from "@/api/aiChat/types";
import { TokenStorage } from "@/utils/tokenStorage";

const SIGNALR_HUB_URL = `${process.env.NEXT_PUBLIC_API_ENDPOINT}/hubs/agent`;

/**
 * Custom hook for streaming AI agent events via SignalR.
 *
 * Connects to the .NET SignalR AgentHub and provides:
 * - sendMessage(): send a message to the agent system
 * - streamState: current streaming state (events, status, content)
 * - isStreaming: whether agents are currently processing
 *
 * Architecture: React → SignalR → .NET → WebSocket → FastAPI (LangGraph)
 */
export function useAgentStream() {
  const connectionRef = useRef<signalR.HubConnection | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamState, setStreamState] = useState<AgentStreamState>({
    events: [],
    activeAgents: [],
    completedAgents: [],
    streamedContent: "",
    structuredData: null,
    resolvedPlaces: [],
    isComplete: false,
    error: null,
  });

  // Build SignalR connection
  useEffect(() => {
    const connection = new signalR.HubConnectionBuilder()
      .withUrl(SIGNALR_HUB_URL, {
        accessTokenFactory: () => TokenStorage.getAccessToken() || "",
        skipNegotiation: true,
        transport: signalR.HttpTransportType.WebSockets,
      })
      .withAutomaticReconnect()
      .configureLogging(signalR.LogLevel.Information)
      .build();

    // Handle incoming agent events
    connection.on("ReceiveAgentEvent", (event: AgentEvent) => {
      console.log("[AgentStream] Event received:", event.eventType, event);

      setStreamState((prev) => {
        const newEvents = [...prev.events, event];
        let activeAgents = [...prev.activeAgents];
        let completedAgents = [...prev.completedAgents];
        let streamedContent = prev.streamedContent;
        let resolvedPlaces = prev.resolvedPlaces;
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

          case "place_resolved":
            console.log("📍 received place_resolved event:", event);
            if (event.placeData) {
              const place = event.placeData as ResolvedPlace;
              console.log("📍 processed place:", place);
              // Deduplicate by placeId
              if (!resolvedPlaces.some((p) => p.placeId === place.placeId)) {
                resolvedPlaces = [...resolvedPlaces, place];
                console.log("📍 added to resolvedPlaces array, new length:", resolvedPlaces.length);
              }
            } else {
              console.warn("⚠️ place_resolved event came without placeData!", event);
            }
            break;

          case "structured_data":
            if (event.structuredData) {
              return {
                ...prev,
                events: newEvents,
                structuredData: event.structuredData,
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
          resolvedPlaces,
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
    });

    // Connection state handlers
    connection.onclose(() => {
      console.log("[AgentStream] Connection closed");
      setIsConnected(false);
    });

    connection.onreconnecting(() => {
      console.log("[AgentStream] Reconnecting...");
      setIsConnected(false);
    });

    connection.onreconnected(() => {
      console.log("[AgentStream] Reconnected");
      setIsConnected(true);
    });

    // Start connection
    connection
      .start()
      .then(() => {
        console.log("[AgentStream] Connected to AgentHub");
        setIsConnected(true);
      })
      .catch((err) => {
        console.error("[AgentStream] Connection failed:", err);
      });

    connectionRef.current = connection;

    return () => {
      connection.stop();
    };
  }, []);

  /**
   * Send a message to the AI agent system.
   * Resets stream state and begins receiving events.
   */
  const sendMessage = useCallback(
    async (conversationId: string, message: string) => {
      if (!connectionRef.current || !isConnected) {
        console.error("[AgentStream] Not connected to SignalR");
        return;
      }

      // Reset stream state for new message
      setStreamState({
        events: [],
        activeAgents: [],
        completedAgents: [],
        streamedContent: "",
        structuredData: null,
        resolvedPlaces: [],
        isComplete: false,
        error: null,
      });
      setIsStreaming(true);

      try {
        await connectionRef.current.invoke(
          "SendMessage",
          conversationId,
          message,
        );
      } catch (err) {
        console.error("[AgentStream] Failed to send message:", err);
        setIsStreaming(false);
        setStreamState((prev) => ({
          ...prev,
          error: "Failed to send message to agent system",
          isComplete: true,
        }));
      }
    },
    [isConnected],
  );

  return {
    sendMessage,
    streamState,
    isStreaming,
    isConnected,
  };
}
