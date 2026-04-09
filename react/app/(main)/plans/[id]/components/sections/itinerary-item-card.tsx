import { ItineraryItem } from "@/types/itineraryItem";
import {
  Clock,
  MapPin,
  Pencil,
  Star,
  Trash,
  Home,
  Flag,
  BedDouble,
  Moon,
  StickyNote,
} from "lucide-react";
import ActionMenu from "@/components/action-menu";
import { cn } from "@/lib/utils";
import MarkerPin from "../maps/marker-pin";
import { useMemo } from "react";
import { DisplayType } from "./cross-day-utils";

interface ItineraryItemCardProps {
  item: ItineraryItem;
  orderNumber: number;
  dayColor: string;
  isFirst: boolean;
  isLast: boolean;
  isActive: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onClick: () => void;
  /** Cross-day display metadata */
  displayType?: DisplayType;
  displayStartTime?: string;
  displayEndTime?: string;
  /** Whether to show Bed icon on the marker badge */
  isBed?: boolean;
}

export default function ItineraryItemCard({
  item,
  orderNumber,
  dayColor,
  isFirst,
  isLast,
  isActive,
  onEdit,
  onDelete,
  onClick,
  displayType = "normal",
  displayStartTime,
  displayEndTime,
  isBed = false,
}: ItineraryItemCardProps) {
  const { place, startTime, duration, note } = item;

  const getEndTime = (start?: string, dur?: string) => {
    if (!start || !dur) return undefined;
    const [sH, sM] = start.split(":").map(Number);
    const [dH, dM] = dur.split(":").map(Number);
    const totalMinutes = sH * 60 + sM + dH * 60 + dM;
    const endH = Math.floor(totalMinutes / 60) % 24;
    const endM = totalMinutes % 60;
    return `${String(endH).padStart(2, "0")}:${String(endM).padStart(2, "0")}`;
  };

  const calculatedEndTime = useMemo(
    () => getEndTime(startTime, duration),
    [startTime, duration],
  );

  // Determine what time text to display
  const timeDisplay = useMemo(() => {
    if (displayType === "cross-day-start") {
      return { start: displayStartTime || startTime, end: "moon" };
    }
    if (displayType === "cross-day-end") {
      return { start: "moon", end: displayEndTime || calculatedEndTime };
    }
    // Normal
    return { start: startTime, end: calculatedEndTime };
  }, [
    displayType,
    displayStartTime,
    displayEndTime,
    startTime,
    calculatedEndTime,
  ]);

  const isCrossDayEnd = displayType === "cross-day-end";

  // Determine marker icon
  const renderMarkerIcon = () => {
    if (isFirst) {
      return <Home size={12} strokeWidth={3} />;
    }
    if (isBed) {
      return <BedDouble size={12} strokeWidth={3} />;
    }
    if (isLast) {
      return <Flag size={12} strokeWidth={3} />;
    }
    return <span className="text-xs font-bold">{orderNumber}</span>;
  };

  return (
    <div
      id={`itinerary-item-${item.id}${isCrossDayEnd ? "-end" : ""}`}
      className={cn(
        "flex flex-col gap-1 w-full relative group/card",
        isCrossDayEnd && "opacity-70",
      )}
    >
      {/* Time Header */}
      <button
        className={cn(
          "cursor-pointer flex items-center gap-1.5 text-xs font-semibold w-fit px-2 py-1 rounded-md mb-1",
          displayType === "cross-day-start"
            ? "text-indigo-600 bg-indigo-50"
            : displayType === "cross-day-end"
              ? "text-purple-600 bg-purple-50"
              : "text-blue-600 bg-blue-50",
        )}
        onClick={!isCrossDayEnd ? onEdit : undefined}
        title={isCrossDayEnd ? "Overnight continuation" : "Click to edit"}
        disabled={isCrossDayEnd}
      >
        {/* <Clock size={12} className="shrink-0" /> */}
        <span className="flex items-center justify-center gap-1">
          {timeDisplay.start && timeDisplay.end ? (
            <>
              {timeDisplay.start === "moon" ? (
                <Moon size={14} className="shrink-0 inline-block" />
              ) : (
                timeDisplay.start
              )}
              {" - "}
              {timeDisplay.end === "moon" ? (
                <Moon size={14} className="shrink-0 inline-block" />
              ) : (
                timeDisplay.end
              )}
            </>
          ) : (
            "Add time"
          )}
        </span>
      </button>

      {/* Place Card */}
      <div
        className={cn(
          "flex flex-col gap-2 p-2 rounded-lg border border-2 bg-white transition-all relative cursor-pointer",
          isActive
            ? "ring-2 ring-offset-1 shadow-md"
            : "border-gray-100 hover:border-gray-200 hover:shadow-sm",
          isCrossDayEnd && "border-dashed",
        )}
        style={{
          borderColor: isActive ? dayColor : undefined,
          boxShadow: isActive ? `0 0 0 3px ${dayColor}40` : undefined,
        }}
        onClick={onClick}
      >
        {/* Order Number Badge */}
        <div className="absolute -top-3 -left-3 z-20 filter drop-shadow-md">
          <MarkerPin width={24} height={34} color={dayColor}>
            {renderMarkerIcon()}
          </MarkerPin>
        </div>

        {/* Action Menu - hidden for cross-day-end items */}
        {!isCrossDayEnd && (
          <div className="absolute top-2 right-2 z-10 opacity-0 group-hover/card:opacity-100 has-[[data-state=open]]:opacity-100 transition-opacity">
            <ActionMenu
              options={[
                {
                  label: "Edit",
                  icon: Pencil,
                  onClick: onEdit,
                  variant: "edit",
                },
                {
                  label: "Delete",
                  icon: Trash,
                  onClick: onDelete,
                  variant: "delete",
                },
              ]}
              iconSize={16}
              ellipsisSize={16}
            />
          </div>
        )}

        {/* Overnight badge for cross-day-end */}
        {isCrossDayEnd && (
          <div className="absolute top-2 right-2 z-10">
            <span className="text-[10px] font-semibold text-purple-500 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200">
              Overnight
            </span>
          </div>
        )}

        {/* Note Content Block */}
        {note && (
          <div
            className={cn(
              "pr-8 pl-1 pb-1 whitespace-pre-wrap",
              place
                ? "text-gray-600 text-sm font-medium mb-1"
                : "text-gray-800 text-sm font-medium pt-1",
            )}
          >
            {note}
          </div>
        )}

        {/* Place Block */}
        {place && (
          <div className="flex gap-2 mt-auto">
            {/* Thumbnail */}
            <div className="w-20 h-20 rounded-md overflow-hidden bg-gray-100 shrink-0 relative">
              {place.thumbnail ? (
                <img
                  src={place.thumbnail}
                  alt={place.title}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.src = "/images/plans/alternative-place.jpg";
                  }}
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center text-gray-400">
                  <MapPin size={24} />
                </div>
              )}
            </div>

            {/* Content */}
            <div className="flex-1 min-w-0 flex flex-col gap-1 pr-6 justify-center">
              <h4 className="font-semibold text-gray-900 truncate text-sm leading-tight">
                {place.title}
              </h4>
              
              {place.address && (
                <p className="text-xs text-gray-500 truncate">{place.address}</p>
              )}
              {place.category && (
                <span className="text-[10px] uppercase font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded border shrink-0 tracking-wide w-fit">
                  {place.category}
                </span>
              )}
              <div className="mt-1 flex items-center gap-2">
                {/* Rating */}
                {place.reviewRating != null && place.reviewRating > 0 && (
                  <div className="flex items-center gap-1 text-xs font-medium text-gray-700 bg-yellow-50 px-1.5 py-0.5 rounded border border-yellow-100">
                    <span className="text-yellow-700 font-bold">
                      {place.reviewRating.toFixed(1)}
                    </span>
                    <Star size={10} className="fill-yellow-500 text-yellow-500" />
                  </div>
                )}

                {/* Review Count */}
                {place.reviewCount != null && place.reviewCount > 0 && (
                  <span className="text-xs text-gray-400">
                    ({place.reviewCount.toLocaleString()} reviews)
                  </span>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Fallback if neither exists */}
        {!place && !note && (
          <div className="text-sm font-medium text-gray-500 italic pl-1 py-2">
            Empty item
          </div>
        )}
      </div>
    </div>
  );
}
