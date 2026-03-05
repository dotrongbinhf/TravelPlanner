"use client";

import { useEffect, useRef } from "react";
import { Mic, Send, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  readonly input: string;
  readonly onInputChange: (value: string) => void;
  readonly onSend: () => void;
  readonly showBuilderButton?: boolean;
  readonly onOpenBuilder?: () => void;
}

export default function ChatInput({
  input,
  onInputChange,
  onSend,
  showBuilderButton = false,
  onOpenBuilder,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize whenever `input` changes (including programmatic sets)
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 150) + "px";
  }, [input]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    onInputChange(e.target.value);
  };

  return (
    <div className="p-3 flex-shrink-0">
      <div className="flex flex-col rounded-lg border-2 border-gray-200 bg-white focus-within:ring-2 focus-within:ring-blue-500 focus-within:border-transparent transition-shadow overflow-hidden transition-all duration-300 ease-in-out">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask about destinations, itineraries, tips..."
          rows={1}
          className="w-full px-3 py-2 text-sm bg-transparent resize-none focus:outline-none custom-scrollbar"
          style={{ maxHeight: "150px" }}
        />
        <div className="flex justify-end items-center gap-1 px-2 pb-2 bg-white">
          <Button
            size="icon"
            className="h-8 w-8 rounded-full text-gray-500 hover:text-gray-600 hover:bg-gray-200 bg-gray-100"
            title="Voice input"
          >
            <Mic className="w-4 h-4" />
          </Button>
          <Button
            onClick={onSend}
            disabled={!input.trim()}
            size="icon"
            className="h-8 w-8 rounded-full bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white disabled:opacity-40 transition-all"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
