"use client";

import { useState, useCallback } from "react";
import { X, BotMessageSquare, Lightbulb, Compass, Wand2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import WelcomeScreen, {
  HowToAskGuide,
  SamplePromptsPopup,
} from "./chats/welcome-screen";
import ChatMessages, { ChatMessage } from "./chats/chat-messages";
import ChatInput from "./chats/chat-input";
import PromptBuilder from "./chats/prompt-builder";
import { createPortal } from "react-dom";

interface AIChatProps {
  readonly planName: string;
  readonly planStartDate?: Date;
  readonly planEndDate?: Date;
  readonly onClose: () => void;
}

export default function AIChat({
  planName,
  planStartDate,
  planEndDate,
  onClose,
}: AIChatProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [activePopup, setActivePopup] = useState<"guide" | "prompts" | null>(
    null,
  );
  const [showBuilder, setShowBuilder] = useState(false);

  const hasMessages = messages.length > 0;

  const sendMessage = useCallback((text: string) => {
    if (!text.trim()) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: "user",
      content: text.trim(),
    };

    setMessages((prev) => [
      ...prev,
      userMessage,
      {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: "AI feature is under development. Please come back later! 🚧",
      },
    ]);
    setInput("");
    setActivePopup(null);
  }, []);

  const handleSend = () => sendMessage(input);

  const handlePromptClick = (prompt: string) => {
    sendMessage(prompt);
  };

  const handleBuilderGenerate = (prompt: string) => {
    // setShowBuilder(false);
    setInput(prompt);
  };

  const handleOpenBuilder = () => {
    setActivePopup(null);
    setShowBuilder(true);
  };

  const handleSetPopup = (popup: "guide" | "prompts" | null) => {
    setActivePopup(popup);
  };

  return (
    <div className="w-full h-full flex flex-col rounded-lg border-2 border-gray-200 bg-white overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 flex-shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center flex-shrink-0">
            <BotMessageSquare className="w-4 h-4 text-white" />
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
          className="h-8 w-8 rounded-lg hover:bg-gray-100 hover:text-gray-500 flex-shrink-0"
        >
          <X className="w-4 h-4" />
        </Button>
      </div>

      {hasMessages ? <ChatMessages messages={messages} /> : <WelcomeScreen />}

      {showBuilder &&
        document.getElementById("right-panel-container") &&
        createPortal(
          <div className="absolute inset-0 z-50 bg-white/60 backdrop-blur-sm flex items-center justify-center p-4 rounded-lg overflow-hidden animate-in fade-in duration-200">
            <div className="w-full h-full shadow-2xl rounded-lg overflow-hidden flex flex-col">
              <PromptBuilder
                onGenerate={handleBuilderGenerate}
                onClose={() => setShowBuilder(false)}
                defaultStartDate={planStartDate}
                defaultEndDate={planEndDate}
              />
            </div>
          </div>,
          document.getElementById("right-panel-container")!,
        )}

      <div className="flex-shrink-0 relative">
        {activePopup && (
          <div className="absolute bottom-full left-3 right-3 mb-1 rounded-xl border border-blue-100 bg-white shadow-lg overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200 z-10">
            <div className="flex items-center justify-between px-3 pt-2.5 pb-0">
              <div className="flex items-center gap-1.5">
                {activePopup === "guide" ? (
                  <Lightbulb className="w-3.5 h-3.5 text-amber-500" />
                ) : (
                  <Compass className="w-3.5 h-3.5 text-blue-500" />
                )}
                <span className="text-xs font-semibold text-gray-700">
                  {activePopup === "guide" ? "How to ask AI" : "Quick start"}
                </span>
              </div>
              <button
                onClick={() => handleSetPopup(null)}
                className="p-0.5 rounded hover:bg-gray-100 transition-colors"
              >
                <X className="w-3 h-3 text-gray-400" />
              </button>
            </div>
            {activePopup === "guide" ? (
              <HowToAskGuide onOpenBuilder={handleOpenBuilder} />
            ) : (
              <SamplePromptsPopup
                onPromptClick={handlePromptClick}
                onClose={() => handleSetPopup(null)}
              />
            )}
          </div>
        )}

        <div className="px-3 pt-1 pb-0 flex items-center gap-2 justify-end">
          <button
            onClick={() =>
              handleSetPopup(activePopup === "prompts" ? null : "prompts")
            }
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-all",
              activePopup === "prompts"
                ? "bg-blue-50 border-blue-200 text-blue-700"
                : "bg-white border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50",
            )}
          >
            <Compass className="w-3.5 h-3.5" />
            Quick start
          </button>
          <button
            onClick={() =>
              handleSetPopup(activePopup === "guide" ? null : "guide")
            }
            className={cn(
              "flex items-center gap-1.5 px-3 py-2 rounded-xl border text-xs font-medium transition-all",
              activePopup === "guide"
                ? "bg-amber-50 border-amber-200 text-amber-700"
                : "bg-white border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50",
            )}
          >
            <Lightbulb className="w-3.5 h-3.5" />
            How to ask
          </button>
          <button
            onClick={handleOpenBuilder}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl border border-blue-200 bg-blue-50 text-blue-700 text-xs font-medium hover:bg-blue-100 transition-all"
          >
            <Wand2 className="w-3.5 h-3.5" />
            Prompt Builder
          </button>
        </div>

        <ChatInput
          input={input}
          onInputChange={setInput}
          onSend={handleSend}
          showBuilderButton={!showBuilder}
          onOpenBuilder={handleOpenBuilder}
        />
      </div>
    </div>
  );
}
