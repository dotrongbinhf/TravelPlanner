"use client";

import { useState } from "react";
import { X, Send, Bot, Mic } from "lucide-react";
import { Button } from "@/components/ui/button";

interface AIChatProps {
  readonly planName: string;
  readonly onClose: () => void;
}

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
}

export default function AIChat({ planName, onClose }: AIChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: `Hello! I'm AI assistant for plan "${planName}". How can I help you?`,
    },
  ]);
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "AI feature is under development. Please come back later!",
      },
    ]);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
  };

  return (
    <div className="w-full h-full flex flex-col rounded-lg border-2 border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 bg-gradient-to-r from-blue-50 to-indigo-50 flex-shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0">
            <Bot className="w-4 h-4 text-white" />
          </div>
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-gray-800 truncate">
              AI Assistant
            </h3>
            <p className="text-xs text-gray-500 truncate">{planName}</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="icon"
          onClick={onClose}
          className="h-8 w-8 rounded-full hover:bg-red-50 hover:text-red-500 flex-shrink-0"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-gradient-to-r from-blue-500 to-indigo-600 text-white rounded-br-md"
                  : "bg-gray-100 text-gray-800 rounded-bl-md"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input Area */}
      <div className="p-3 flex-shrink-0">
        <div className="flex flex-col rounded-lg border-2 border-gray-200 bg-white focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent transition-shadow overflow-hidden transition-all duration-300 ease-in-out">
          <textarea
            value={input}
            onChange={handleInput}
            onKeyDown={handleKeyDown}
            placeholder="Ask something..."
            rows={1}
            className="w-full px-3 py-2 text-sm bg-transparent resize-none focus:outline-none custom-scrollbar"
            style={{ maxHeight: "150px" }}
          />
          <div className="flex justify-end items-center gap-1 px-2 pb-2 bg-white">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 rounded-full text-gray-400 hover:text-gray-600 hover:bg-gray-100"
              title="Nhập bằng giọng nói"
            >
              <Mic className="w-4 h-4" />
            </Button>
            <Button
              onClick={handleSend}
              disabled={!input.trim()}
              size="icon"
              className="h-8 w-8 rounded-full bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 text-white disabled:opacity-40 transition-all"
            >
              <Send className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
