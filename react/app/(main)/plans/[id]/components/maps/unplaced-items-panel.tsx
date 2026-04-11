"use client";

import { useState } from "react";
import { MapPinOff, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { getDayColor } from "@/constants/day-colors";
import MarkerPin from "./marker-pin";

export interface UnplacedItem {
  itemId: string;
  dayIndex: number;
  orderNumber: number;
  note?: string | null;
}

interface UnplacedItemsPanelProps {
  items: UnplacedItem[];
  filterMode: "all" | "byDay";
  selectedDayIndex: number;
  onItemClick: (dayIndex: number, itemId: string) => void;
}

export default function UnplacedItemsPanel({
  items,
  filterMode,
  selectedDayIndex,
  onItemClick,
}: UnplacedItemsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  // Filter items based on current filter mode
  const visibleItems =
    filterMode === "byDay"
      ? items.filter((i) => i.dayIndex === selectedDayIndex)
      : items;

  if (visibleItems.length === 0) return null;

  // Group by day
  const groupedByDay = visibleItems.reduce(
    (acc, item) => {
      if (!acc[item.dayIndex]) acc[item.dayIndex] = [];
      acc[item.dayIndex].push(item);
      return acc;
    },
    {} as Record<number, UnplacedItem[]>,
  );

  const dayIndices = Object.keys(groupedByDay)
    .map(Number)
    .sort((a, b) => a - b);

  return (
    <div className="flex flex-col gap-1">
      {/* Toggle Button */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className={cn(
          "cursor-pointer flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg shadow-lg border transition-all duration-200 text-xs font-semibold",
          "bg-amber-50 border-amber-200 text-amber-700 hover:bg-amber-100",
        )}
      >
        <MapPinOff size={13} className="shrink-0" />
        <span>
          {visibleItems.length} unplaced
        </span>
        {isExpanded ? (
          <ChevronUp size={12} className="shrink-0" />
        ) : (
          <ChevronDown size={12} className="shrink-0" />
        )}
      </button>

      {/* Expanded Panel */}
      {isExpanded && (
        <div className="bg-white/95 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200 p-2.5 min-w-[180px] max-w-[240px] max-h-[280px] overflow-y-auto custom-scrollbar animate-in slide-in-from-top-1 duration-200">
          <div className="space-y-2">
            {dayIndices.map((dayIndex) => (
              <div key={dayIndex} className="space-y-1">
                {/* Day header (only in "all" mode with multiple days) */}
                {(filterMode === "all" && dayIndices.length > 1) && (
                  <div className="flex items-center gap-1.5 px-1">
                    <div
                      className="w-2 h-2 rounded-full shrink-0"
                      style={{ backgroundColor: getDayColor(dayIndex) }}
                    />
                    <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">
                      Day {dayIndex + 1}
                    </span>
                  </div>
                )}

                {/* Items */}
                {groupedByDay[dayIndex].map((item) => (
                  <button
                    key={item.itemId}
                    onClick={() => onItemClick(item.dayIndex, item.itemId)}
                    className="cursor-pointer w-full flex items-center gap-2 px-1.5 py-1.5 rounded-lg hover:bg-gray-50 transition-colors text-left group"
                  >
                    {/* Mini marker badge */}
                    <div className="shrink-0 scale-75 origin-center">
                      <MarkerPin
                        width={20}
                        height={28}
                        color={getDayColor(item.dayIndex)}
                      >
                        <span className="text-[9px] font-bold">
                          {item.orderNumber}
                        </span>
                      </MarkerPin>
                    </div>
                    <span className="text-xs text-gray-600 truncate flex-1 group-hover:text-gray-900 transition-colors">
                      {item.note
                        ? item.note.length > 30
                          ? item.note.substring(0, 30) + "..."
                          : item.note
                        : "Empty item"}
                    </span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
