"use client";

import { AdvancedMarker } from "@vis.gl/react-google-maps";
import { useState } from "react";
import { cn } from "@/lib/utils";

interface AiExploreMarkerProps {
  position: { lat: number; lng: number };
  name: string;
  agentName?: string;
  isActive: boolean;
  onClick: () => void;
}

/** Color map for different agent types */
const AGENT_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  attraction_agent: { bg: "bg-violet-500/90", border: "border-violet-400", text: "text-white" },
  hotel_agent: { bg: "bg-blue-500/90", border: "border-blue-400", text: "text-white" },
  restaurant_agent: { bg: "bg-orange-500/90", border: "border-orange-400", text: "text-white" },
  default: { bg: "bg-indigo-500/90", border: "border-indigo-400", text: "text-white" },
};

function getAgentStyle(agentName?: string) {
  return AGENT_COLORS[agentName ?? ""] ?? AGENT_COLORS.default;
}

export default function AiExploreMarker({
  name,
  position,
  agentName,
  isActive,
  onClick,
}: AiExploreMarkerProps) {
  const [isHovered, setIsHovered] = useState(false);
  const style = getAgentStyle(agentName);

  // Truncate name for display
  const truncatedName = name.length > 14 ? name.substring(0, 12) + "…" : name;
  const showFullName = isHovered || isActive;

  return (
    <AdvancedMarker position={position} onClick={onClick}>
      <div
        className="relative flex flex-col items-center"
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Label pill */}
        <div
          className={cn(
            "relative flex items-center gap-1 px-2 py-1 rounded-full shadow-lg border backdrop-blur-sm cursor-pointer transition-all duration-300 ease-out",
            style.bg,
            style.border,
            style.text,
            isActive
              ? "scale-110 ring-2 ring-white ring-offset-1 shadow-xl z-20"
              : "hover:scale-105 hover:shadow-xl hover:z-20",
          )}
        >
          {/* Pulsing dot */}
          <div className="relative shrink-0">
            <div className="w-2 h-2 rounded-full bg-white/90" />
            <div className="absolute inset-0 w-2 h-2 rounded-full bg-white/60 animate-ping" />
          </div>

          {/* Name text */}
          <span
            className={cn(
              "text-[11px] font-semibold leading-tight whitespace-nowrap transition-all duration-300",
              showFullName ? "max-w-[200px]" : "max-w-[100px]",
            )}
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {showFullName ? name : truncatedName}
          </span>
        </div>

        {/* Pointer triangle */}
        <div
          className={cn(
            "w-0 h-0 -mt-[1px]",
            "border-l-[5px] border-l-transparent",
            "border-r-[5px] border-r-transparent",
            "border-t-[6px]",
          )}
          style={{
            borderTopColor:
              agentName === "attraction_agent"
                ? "rgb(139, 92, 246)"
                : agentName === "hotel_agent"
                  ? "rgb(59, 130, 246)"
                  : agentName === "restaurant_agent"
                    ? "rgb(249, 115, 22)"
                    : "rgb(99, 102, 241)",
          }}
        />
      </div>
    </AdvancedMarker>
  );
}
