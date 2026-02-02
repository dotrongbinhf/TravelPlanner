import { ItineraryItem } from "@/types/itineraryItem";
import { Clock, MapPin, Pencil, Star, Trash, Home, Flag } from "lucide-react";
import ActionMenu from "@/components/action-menu";
import { cn } from "@/lib/utils";
import MarkerPin from "../maps/marker-pin";

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
}: ItineraryItemCardProps) {
  const { place, startTime, endTime } = item;

  return (
    <div
      id={`itinerary-item-${item.id}`}
      className="flex flex-col gap-1 w-full relative group/card"
    >
      {/* Time Header */}
      <button
        className="cursor-pointer flex items-center gap-1.5 text-xs font-semibold text-blue-600 bg-blue-50 w-fit px-2 py-1 rounded-md mb-1"
        onClick={onEdit}
        title="Click to edit"
      >
        <Clock size={12} className="shrink-0" />
        {/* Add time change to button to edit when start and end time is not set */}
        <span>
          {startTime && endTime ? `${startTime} - ${endTime}` : "Add time"}
        </span>
      </button>

      {/* Place Card */}
      <div
        className={cn(
          "flex gap-2 p-2 rounded-lg border border-2 bg-white transition-all relative cursor-pointer",
          isActive
            ? "ring-2 ring-offset-1 shadow-md"
            : "border-gray-100 hover:border-gray-200 hover:shadow-sm",
        )}
        style={{
          borderColor: isActive ? dayColor : undefined,
          boxShadow: isActive ? `0 0 0 3px ${dayColor}40` : undefined,
        }}
        onClick={onClick}
      >
        {/* Order Number Badge */}
        {/* Order Number Badge */}
        <div className="absolute -top-3 -left-3 z-20 filter drop-shadow-md">
          <MarkerPin width={24} height={34} color={dayColor}>
            {isFirst ? (
              <Home size={12} strokeWidth={3} />
            ) : isLast ? (
              <Flag size={12} strokeWidth={3} />
            ) : (
              <span className="text-xs font-bold">{orderNumber}</span>
            )}
          </MarkerPin>
        </div>

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

        {/* Thumbnail min-h-20 to uncomment*/}
        <div className="w-20 h-20 rounded-md overflow-hidden bg-gray-100 shrink-0 relative">
          {place?.thumbnail ? (
            <img
              src={place.thumbnail}
              alt={place.title}
              // className="absolute inset-0 w-full h-full object-cover"
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="absolute inset-0 flex items-center justify-center text-gray-400">
              <MapPin size={24} />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 flex flex-col gap-1 pr-6">
          {" "}
          {/* Added padding right for menu space */}
          <h4 className="font-semibold text-gray-900 truncate text-sm leading-tight">
            {place?.title || "Unknown Place"}
          </h4>
          {place?.address && (
            <p className="text-xs text-gray-500 truncate">{place.address}</p>
          )}
          {place?.category && (
            <span className="text-[10px] uppercase font-bold text-gray-500 bg-gray-100 px-1.5 py-0.5 rounded border shrink-0 tracking-wide w-fit">
              {place.category}
            </span>
          )}
          <div className="mt-auto flex items-center gap-2">
            {/* Rating */}
            {place?.reviewRating != null && (
              <div className="flex items-center gap-1 text-xs font-medium text-gray-700 bg-yellow-50 px-1.5 py-0.5 rounded border border-yellow-100">
                <span className="text-yellow-700 font-bold">
                  {place.reviewRating.toFixed(1)}
                </span>
                <Star size={10} className="fill-yellow-500 text-yellow-500" />
              </div>
            )}

            {/* Review Count */}
            {place?.reviewCount != null && (
              <span className="text-xs text-gray-400">
                ({place.reviewCount.toLocaleString()} reviews)
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
