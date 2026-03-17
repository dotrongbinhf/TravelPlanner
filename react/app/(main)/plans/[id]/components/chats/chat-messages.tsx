"use client";

import { useEffect, useRef, useCallback } from "react";
import { BotMessageSquare, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

interface ChatMessagesProps {
  readonly messages: ChatMessage[];
  readonly streamingContent?: string;
  readonly currentAgent?: string | null;
  readonly isStreaming?: boolean;
}

// Map agent names to display labels
const AGENT_LABELS: Record<string, string> = {
  planner: "🧠 Planner",
  researcher: "🔍 Researcher",
  dotnet_integration: "📡 Data Fetcher",
  response: "📝 Composing Response",
};

export default function ChatMessages({
  messages,
  streamingContent,
  currentAgent,
  isStreaming,
}: ChatMessagesProps) {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, streamingContent, scrollToBottom]);

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
        >
          {msg.role === "assistant" && (
            <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
              <BotMessageSquare className="w-3 h-3 text-white" />
            </div>
          )}
          <div
            className={cn(
              "max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words",
              msg.role === "user"
                ? "bg-gradient-to-r from-blue-500 to-blue-600 text-white rounded-br-md"
                : "bg-gray-100 text-gray-800 rounded-bl-md",
            )}
          >
            {msg.content}
          </div>
        </div>
      ))}

      {/* Streaming indicator & content */}
      {isStreaming && (
        <div className="flex justify-start">
          <div className="w-6 h-6 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0 mr-2 mt-1">
            <BotMessageSquare className="w-3 h-3 text-white" />
          </div>
          <div className="max-w-[80%] space-y-2">
            {/* Agent status badge */}
            {currentAgent && (
              <div className="flex items-center gap-1.5 text-xs text-blue-600 font-medium animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>{AGENT_LABELS[currentAgent] || currentAgent}</span>
              </div>
            )}

            {/* Streamed text content */}
            {streamingContent ? (
              <div className="rounded-2xl rounded-bl-md px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words bg-gray-100 text-gray-800">
                {streamingContent}
                <span className="inline-block w-1.5 h-4 bg-blue-500 ml-0.5 animate-pulse rounded-sm" />
              </div>
            ) : (
              <div className="rounded-2xl rounded-bl-md px-4 py-2.5 bg-gray-100">
                <div className="flex items-center gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      <div ref={messagesEndRef} />
    </div>
  );
}
