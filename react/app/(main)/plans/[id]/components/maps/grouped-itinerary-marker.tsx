"use client";

import { AdvancedMarker } from "@vis.gl/react-google-maps";
import { useState, useRef, useEffect } from "react";
import { cn } from "@/lib/utils";
import MarkerPin from "./marker-pin";
import { ItineraryItem } from "@/types/itineraryItem";

interface GroupedItemInfo {
  item: ItineraryItem;
  dayIndex: number;
  itemIndex: number;
  orderNumber: number;
  dayColor: string;
}

interface GroupedItineraryMarkerProps {
  position: { lat: number; lng: number };
  items: GroupedItemInfo[];
  /** Color of the first item's day (primary color for the pin) */
  primaryColor: string;
  isActive: boolean;
  onItemSelect: (item: ItineraryItem, dayIndex: number, itemIndex: number) => void;
}

export default function GroupedItineraryMarker({
  position,
  items,
  primaryColor,
  isActive,
  onItemSelect,
}: GroupedItineraryMarkerProps) {
  const [showPopover, setShowPopover] = useState(false);
  const popoverRef = useRef<HTMLDivElement>(null);

  // Close popover on outside click
  useEffect(() => {
    if (!showPopover) return;
    const handler = (e: MouseEvent) => {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setShowPopover(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showPopover]);

  // Build display label: "1, 4" or "1, 4, 7"
  const label = items.map((i) => i.orderNumber).join(", ");

  // Determine pin size based on label length
  const pinWidth = label.length > 3 ? 42 : 36;
  const pinHeight = label.length > 3 ? 52 : 48;

  return (
    <AdvancedMarker
      position={position}
      onClick={() => {
        if (items.length === 1) {
          onItemSelect(items[0].item, items[0].dayIndex, items[0].itemIndex);
        } else {
          setShowPopover(!showPopover);
        }
      }}
    >
      <div className="relative flex flex-col items-center group">
        {/* Hover Tooltip */}
        {!showPopover && (
          <div className="absolute bottom-full mb-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200 z-50 pointer-events-none">
            <div className="bg-white px-2 py-1 rounded-md shadow-md border border-slate-200 text-xs font-bold text-slate-800 whitespace-nowrap text-center max-w-[150px] truncate">
              {items[0]?.item.place?.title || "Multiple Items"}
            </div>
            <div className="w-2 h-2 bg-white rotate-45 -mt-1.5 border-r border-b border-slate-200 mx-auto"></div>
          </div>
        )}

        {/* Marker Pin */}
        <div
          className={cn(
            "relative flex items-center justify-center cursor-pointer transition-transform duration-300 ease-out origin-bottom",
            isActive
              ? "z-20 scale-125"
              : "z-10 scale-100 hover:scale-110 hover:z-20",
          )}
        >
          <MarkerPin
            width={pinWidth}
            height={pinHeight}
            color={primaryColor}
            active={isActive}
          >
            <span
              className="font-bold leading-none text-white"
              style={{ fontSize: label.length > 4 ? "9px" : "11px" }}
            >
              {label}
            </span>
          </MarkerPin>
        </div>

        {/* Popover listing items */}
        {showPopover && items.length > 1 && (
          <div
            ref={popoverRef}
            className="absolute bottom-full mb-2 bg-white rounded-xl shadow-xl border border-gray-200 p-1.5 min-w-[160px] max-w-[220px] z-50 animate-in fade-in slide-in-from-bottom-2 duration-200"
          >
            <div className="text-[10px] font-bold text-gray-400 uppercase tracking-wider px-2 pt-1 pb-1.5">
              {items.length} items at this place
            </div>
            {items.map((gi) => (
              <button
                key={`${gi.item.id}-${gi.dayIndex}`}
                onClick={(e) => {
                  e.stopPropagation();
                  onItemSelect(gi.item, gi.dayIndex, gi.itemIndex);
                  setShowPopover(false);
                }}
                className="cursor-pointer w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-50 transition-colors text-left"
              >
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-white text-[10px] font-bold shrink-0"
                  style={{ backgroundColor: gi.dayColor }}
                >
                  {gi.orderNumber}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-gray-800 truncate">
                    {gi.item.place?.title || gi.item.note || "Item"}
                  </p>
                  <p className="text-[10px] text-gray-400 truncate">
                    Day {gi.dayIndex + 1}
                    {gi.item.startTime ? ` · ${gi.item.startTime}` : ""}
                  </p>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </AdvancedMarker>
  );
}
