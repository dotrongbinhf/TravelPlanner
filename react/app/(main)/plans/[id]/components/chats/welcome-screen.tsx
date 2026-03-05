"use client";

import { Sparkles, Wand2 } from "lucide-react";
import { cn } from "@/lib/utils";

const SAMPLE_PROMPTS = [
  {
    city: "Hanoi",
    emoji: "🇻🇳",
    color: "from-red-400 to-rose-500",
    prompt:
      "Plan a 4-day trip to Hanoi with Old Quarter, temples and local street food",
  },
  {
    city: "Ho Chi Minh",
    emoji: "🇻🇳",
    color: "from-amber-400 to-orange-500",
    prompt:
      "Suggest a 3-day Ho Chi Minh City trip with Cu Chi Tunnels and nightlife",
  },
  {
    city: "Tokyo",
    emoji: "⛩️",
    color: "from-red-400 to-orange-500",
    prompt:
      "Suggest a week in Tokyo mixing traditional temples with modern culture",
  },
  {
    city: "Paris",
    emoji: "🗼",
    color: "from-rose-400 to-pink-500",
    prompt:
      "Plan a 5-day trip to Paris with must-see landmarks and local food spots",
  },
];

export function HowToAskGuide({
  onOpenBuilder,
}: {
  readonly onOpenBuilder: () => void;
}) {
  return (
    <div className="space-y-2.5 p-3">
      <p className="text-xs text-gray-600 leading-relaxed">
        For the best results, try telling the AI:
      </p>
      <div className="space-y-1.5">
        {[
          { icon: "📍", text: "Where — your destination" },
          { icon: "📅", text: "When — travel dates" },
          { icon: "👥", text: "Who — solo, couple, family, friends" },
          { icon: "✨", text: "Vibes — adventure, relaxation, culture..." },
          { icon: "💰", text: "Budget — low, mid-range, or luxury" },
          { icon: "🚗", text: "Transport — walking, transit, car..." },
        ].map((item) => (
          <div
            key={item.text}
            className="flex items-start gap-2 text-xs text-gray-700"
          >
            <span className="text-sm leading-none mt-0.5">{item.icon}</span>
            <span>{item.text}</span>
          </div>
        ))}
      </div>
      <div className="pt-1">
        <button
          onClick={onOpenBuilder}
          className="text-xs font-medium text-blue-600 hover:text-blue-700 hover:underline flex items-center gap-1"
        >
          <Wand2 className="w-3 h-3" />
          Or use Prompt Builder to fill in step by step →
        </button>
      </div>
    </div>
  );
}

export function SamplePromptsPopup({
  onPromptClick,
  onClose,
}: {
  readonly onPromptClick: (prompt: string) => void;
  readonly onClose: () => void;
}) {
  return (
    <div className="space-y-2 p-3">
      <p className="text-xs text-gray-600 leading-relaxed">
        Pick a destination to get started quickly:
      </p>
      <div className="space-y-1.5">
        {SAMPLE_PROMPTS.map((item) => (
          <button
            key={item.city}
            onClick={() => {
              onPromptClick(item.prompt);
              onClose();
            }}
            className="w-full flex items-center gap-2 p-2 rounded-lg border border-gray-200 bg-white hover:shadow-sm hover:border-blue-200 transition-all text-left"
          >
            <div
              className={cn(
                "w-8 h-8 rounded-lg bg-gradient-to-br flex items-center justify-center text-sm shrink-0",
                item.color,
              )}
            >
              {item.emoji}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-semibold text-gray-800">{item.city}</p>
              <p className="text-[10px] text-gray-400 line-clamp-1 leading-tight">
                {item.prompt}
              </p>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

export default function WelcomeScreen() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center px-6">
      <Sparkles className="w-10 h-10 text-blue-500 mb-3" />
      <h2 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-blue-500 bg-clip-text text-transparent mb-1">
        Where to next?
      </h2>
      <p className="text-gray-400 text-center">
        Ask me anything about travel planning
      </p>
    </div>
  );
}
