import { ItineraryDay } from "@/types/itineraryDay";
import {
  Check,
  Pencil,
  Plus,
  X,
  Clock,
  Trash,
  Map,
  Loader2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { format } from "date-fns";
import { cn } from "@/lib/utils";
import PlaceAutocomplete from "./place-autocomplete";
import { ItineraryItem } from "@/types/itineraryItem";
import {
  createItineraryItem,
  deleteItineraryItem,
  updateItineraryItem,
} from "@/api/itineraryItem/itineraryItem";
import toast from "react-hot-toast";
import { AxiosError } from "axios";

import { Button } from "@/components/ui/button";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import { CustomDialog } from "@/components/custom-dialog";
import ItineraryItemEditor from "./itinerary-item-editor";
import ItineraryItemCard from "./itinerary-item-card";
import ActionMenu from "@/components/action-menu";
import Image from "next/image";
import { useItineraryContext } from "../../../../../../contexts/ItineraryContext";
import { getDayColor } from "../../../../../../constants/day-colors";
import ItineraryItemCardSkeleton from "./itinerary-item-card-skeleton";
import { buildDisplayItems } from "./cross-day-utils";
import { getRoutesByDayId } from "@/api/itineraryItemsRoute/itineraryItemsRoute";
import { useEnsurePlace } from "@/hooks/use-ensure-place";
import { generateGoogleMapsLink } from "@/utils/map";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

function computeAutoStartTime(items: ItineraryItem[]): string {
  const timedItems = items.filter((i) => i.startTime);
  if (timedItems.length === 0) return "08:00";

  let maxEndMinutes = 0;

  for (const item of timedItems) {
    const [sH, sM] = item.startTime!.split(":").map(Number);
    let endMinutes = sH * 60 + sM;
    if (item.duration) {
      const [dH, dM] = item.duration.split(":").map(Number);
      endMinutes += dH * 60 + dM;
    }
    if (endMinutes > maxEndMinutes) maxEndMinutes = endMinutes;
  }

  // Add 1-hour buffer after the latest end time
  const nextMinutes = (maxEndMinutes + 60) % (24 * 60);
  const h = Math.floor(nextMinutes / 60);
  const m = nextMinutes % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

interface ItineraryDayCardProps {
  allItineraryDays: ItineraryDay[];
  itineraryDay: ItineraryDay;
  dayIndex: number;
  totalDays: number;
  planStartTime: Date;
  onEditTitle: (dayId: string, newTitle: string) => Promise<void>;
  onAddItem: (item: ItineraryItem) => void;
  onUpdateItem: (item: ItineraryItem) => void;
  onDeleteItem: (itemId: string, dayId: string) => void;
  onDeleteDay: (dayId: string) => void;
}

export default function ItineraryDayCard({
  allItineraryDays,
  itineraryDay,
  dayIndex,
  totalDays,
  planStartTime,
  onEditTitle,
  onAddItem,
  onUpdateItem,
  onDeleteItem,
  onDeleteDay,
}: ItineraryDayCardProps) {
  const { selectedPlace, selectPlaceFromItinerary, clearPlaceSelection } =
    useItineraryContext();
  const { ensurePlaceExists } = useEnsurePlace();
  const dayColor = getDayColor(dayIndex);

  // Build display items (includes cross-day splits)
  const sortedDays = useMemo(
    () => [...allItineraryDays].sort((a, b) => a.order - b.order),
    [allItineraryDays],
  );
  const displayItems = useMemo(
    () => buildDisplayItems(sortedDays, dayIndex, totalDays),
    [sortedDays, dayIndex, totalDays],
  );
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(itineraryDay.title);

  const [isOpenAddItem, setIsOpenAddItem] = useState(false);
  const [newItemNote, setNewItemNote] = useState("");
  const [newItemPlaceId, setNewItemPlaceId] = useState<string | null>(null);
  const [newItemPlaceName, setNewItemPlaceName] = useState("");
  const [isAddingItem, setIsAddingItem] = useState(false);

  const [editingItem, setEditingItem] = useState<ItineraryItem | null>(null);
  const [editedPlaceId, setEditedPlaceId] = useState<string | null>(null);
  const [editedPlaceName, setEditedPlaceName] = useState("");
  const [itemToDelete, setItemToDelete] = useState<ItineraryItem | null>(null);
  const [dayToDelete, setDayToDelete] = useState<string | null>(null);
  const [isGeneratingLink, setIsGeneratingLink] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const date = new Date(planStartTime);
  date.setDate(date.getDate() + itineraryDay.order);

  useEffect(() => {
    setTitle(itineraryDay.title);
  }, [itineraryDay.title]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isEditing]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isEditing &&
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        handleCancelUpdateItineraryDay();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isEditing]);

  const handleEditItineraryDay = () => {
    setIsEditing(true);
    setTitle(itineraryDay.title);
  };

  const handleConfirmUpdateItineraryDay = async () => {
    if (title.trim() !== itineraryDay.title) {
      await onEditTitle(itineraryDay.id, title.trim());
    }
    setIsEditing(false);
  };

  const handleCancelUpdateItineraryDay = () => {
    setIsEditing(false);
    setTitle(itineraryDay.title);
  };

  const handleAddItemClick = () => {
    setIsOpenAddItem(true);
    setNewItemNote("");
    setNewItemPlaceId(null);
    setNewItemPlaceName("");
  };

  const handleInlineSubmit = async () => {
    if (!newItemNote.trim() && !newItemPlaceId) return;
    
    setIsAddingItem(true);
    try {
      if (newItemPlaceId) {
        await ensurePlaceExists(newItemPlaceId);
      }

      const response = await createItineraryItem(itineraryDay.id, {
        placeId: newItemPlaceId ?? undefined,
        startTime: undefined,
        duration: undefined,
        note: newItemNote.trim() || undefined,
      });

      onAddItem(response);
      toast.success("Item added successfully");

      // Select the newly added item if it's a place. (Selection doesn't do much for note-only).
      const itemsCount = itineraryDay.itineraryItems?.length ?? 0;
      selectPlaceFromItinerary(response, dayIndex, itemsCount, "list");
      
      setIsOpenAddItem(false);
    } catch (error) {
      console.error("Error creating itinerary item:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data?.message ?? "Failed to add item");
      } else {
        toast.error("Failed to add item");
      }
    } finally {
      setIsAddingItem(false);
    }
  };

  const handleSelectItineraryDayId = (itineraryDayId: string) => {
    if (!editingItem) return;
    const newItineraryItem = { ...editingItem };
    newItineraryItem.itineraryDayId = itineraryDayId;
    setEditingItem(newItineraryItem);
  };

  const handleSelectStartTime = (date: Date | undefined) => {
    if (!editingItem) return;
    const newItineraryItem = { ...editingItem };
    newItineraryItem.startTime = date ? format(date, "HH:mm") : "";
    setEditingItem(newItineraryItem);
  };

  const handleSelectDuration = (duration: string) => {
    if (!editingItem) return;
    const newItineraryItem = { ...editingItem };
    newItineraryItem.duration = duration;
    setEditingItem(newItineraryItem);
  };

  const convertTimeOnlyStringToDate = (time?: string): Date | undefined => {
    if (!time) return undefined;
    const [hours, minutes] = time.split(":");
    const date = new Date();
    date.setHours(parseInt(hours), parseInt(minutes), 0, 0);
    return date;
  };

  const handleConfirmUpdateItineraryItem = async (
    itineraryDayId: string,
    startTime?: string,
    duration?: string,
    note?: string,
    placeId?: string | null,
  ) => {
    if (!editingItem) return;

    try {
      const response = await updateItineraryItem(editingItem.id, {
        itineraryDayId,
        startTime,
        duration,
        note,
        placeId,
      });

      onUpdateItem(response);
      toast.success("Updated Itinerary Item");
      setEditingItem(null);
    } catch (error) {
      console.error("Error updating item:", error);
      toast.error("Failed to update item");
    }
  };

  const handleConfirmDeleteItineraryItem = async () => {
    if (!itemToDelete) return;

    try {
      await deleteItineraryItem(itemToDelete.id);
      onDeleteItem(itemToDelete.id, itineraryDay.id);
      clearPlaceSelection();
      toast.success("Item deleted successfully");
      setItemToDelete(null);
    } catch (error) {
      console.error("Error deleting item:", error);
      toast.error("Failed to delete item");
    }
  };

  const handleConfirmDeleteItineraryDay = async () => {
    if (!dayToDelete) return;
    await onDeleteDay(dayToDelete);
    setDayToDelete(null);
  };

  const handleOpenGoogleMaps = async () => {
    // 1. To make sure overnight places from yesterday connect to this day's
    // itinerary properly, we reconstruct a list with cross-day items correctly identified
    const mapItems: (typeof displayItems)[0]["item"][] = [];

    // Check displayItems representing ghost items (cross-day-end) OR cross-day starts
    displayItems.forEach((di) => {
      // Only include ghost items (yesterday's overnight) and today's normal/cross-day items.
      // It's just the items array, which already contains the right sequence
      mapItems.push(di.item);
    });

    if (!mapItems || mapItems.length < 2) return;

    setIsGeneratingLink(true);
    try {
      // Get routes that might span these items
      const routes = await getRoutesByDayId(itineraryDay.id);
      const link = generateGoogleMapsLink(mapItems, routes, "driving");
      if (link) {
        window.open(link, "_blank", "noopener,noreferrer");
      }
    } catch (error) {
      console.error("Failed to fetch routes for Google Maps link:", error);
      // Fallback without custom routes
      const link = generateGoogleMapsLink(mapItems, [], "driving");
      if (link) {
        window.open(link, "_blank", "noopener,noreferrer");
      }
    } finally {
      setIsGeneratingLink(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        {isEditing ? (
          <div
            ref={containerRef}
            className="flex items-center gap-2 border-2 rounded-lg border-blue-400 border-dashed p-1 flex-1 w-full"
          >
            <span className="font-bold text-blue-500 shrink-0">
              Day {itineraryDay.order + 1}
            </span>
            <span className="text-gray-500 font-medium shrink-0">
              ({format(date, "dd/MM/yyyy")}):
            </span>
            <input
              ref={inputRef}
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Enter day title..."
              className="flex-1 font-semibold bg-transparent border-none outline-none placeholder:text-gray-400 min-w-0"
              onKeyDown={(e) => {
                if (e.key === "Enter") handleConfirmUpdateItineraryDay();
                if (e.key === "Escape") handleCancelUpdateItineraryDay();
              }}
            />
            <div className="flex gap-1 shrink-0">
              <button
                onClick={handleCancelUpdateItineraryDay}
                className="cursor-pointer p-2 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
                title="Cancel"
              >
                <X size={14} />
              </button>
              <button
                onClick={handleConfirmUpdateItineraryDay}
                className="cursor-pointer p-2 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
                title="Confirm"
              >
                <Check size={14} />
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 flex-1">
            <h3 className="flex items-center gap-1">
              <span className="text-blue-500 font-bold">
                Day {itineraryDay.order + 1}
              </span>
              <span className="font-medium text-gray-600">
                ({format(date, "dd/MM/yyyy")}):
              </span>
              <span
                className={cn(
                  "font-semibold",
                  !itineraryDay.title && "text-gray-400 font-normal",
                )}
              >
                {itineraryDay.title || "No Title"}
              </span>
            </h3>

            <div className="flex items-center gap-1">
              {displayItems && displayItems.length >= 2 && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <button
                        onClick={handleOpenGoogleMaps}
                        disabled={isGeneratingLink}
                        className="cursor-pointer py-1.5 px-2 text-gray-500 hover:bg-gray-200 rounded-md transition-colors flex items-center justify-center"
                      >
                        {isGeneratingLink ? (
                          <Loader2
                            size={14}
                            className="animate-spin text-blue-500"
                          />
                        ) : (
                          <Image
                            src="/images/plans/google-maps.png"
                            alt="Google Maps"
                            width={14}
                            height={14}
                            className="object-contain"
                          />
                        )}
                      </button>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>Open in Google Maps</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
              <ActionMenu
                options={[
                  {
                    label: "Edit",
                    icon: Pencil,
                    onClick: handleEditItineraryDay,
                    variant: "edit",
                  },
                  {
                    label: "Delete",
                    icon: Trash,
                    onClick: () => setDayToDelete(itineraryDay.id),
                    variant: "delete",
                  },
                ]}
                iconSize={16}
                ellipsisSize={16}
                triggerClassName="[data-state=open]:opacity-100"
              />
            </div>
          </div>
        )}
      </div>

      {/* Items List */}
      {displayItems.length > 0 && (
        <div className="flex flex-col gap-3">
          {displayItems.map((di, index) => {
            const isCrossDayEnd = di.displayType === "cross-day-end";
            const itemDayColor = getDayColor(di.sourceDayIndex);
            return (
              <ItineraryItemCard
                key={`${di.item.id}-${di.displayType}`}
                item={di.item}
                orderNumber={di.orderNumber}
                dayColor={itemDayColor}
                isFirst={di.isOverallFirst}
                isLast={di.isOverallLast}
                isActive={
                  !!selectedPlace.placeId &&
                  !!di.item.place?.placeId &&
                  selectedPlace.placeId === di.item.place.placeId &&
                  selectedPlace.dayIndex === dayIndex
                }
                onEdit={() => {
                  if (!isCrossDayEnd) {
                    setEditingItem(di.item);
                    setEditedPlaceId(di.item.place?.placeId ?? null);
                    setEditedPlaceName(di.item.place?.title ?? "");
                  }
                }}
                onDelete={() => !isCrossDayEnd && setItemToDelete(di.item)}
                onClick={() =>
                  selectPlaceFromItinerary(
                    di.item,
                    dayIndex,
                    di.orderNumber - 1,
                  )
                }
                displayType={di.displayType}
                displayStartTime={di.displayStartTime}
                displayEndTime={di.displayEndTime}
                isBed={di.isBed}
              />
            );
          })}

          {isAddingItem && <ItineraryItemCardSkeleton />}
        </div>
      )}

      <div className="flex flex-col gap-2 relative">
        {isOpenAddItem ? (
          <div className="relative z-10 bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
            <div className="flex justify-between items-center pb-2 border-b border-gray-100">
              <h4 className="font-semibold text-sm text-gray-700">Add New Item</h4>
              <button onClick={() => setIsOpenAddItem(false)} className="text-gray-400 hover:text-gray-600 transition-colors">
                <X size={16} />
              </button>
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wider">Note (Optional)</label>
              <textarea
                value={newItemNote}
                onChange={(e) => setNewItemNote(e.target.value)}
                placeholder="Write a note, instructions, or free-text activity..."
                className="w-full min-h-[60px] text-sm p-2.5 rounded-lg border border-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 resize-y outline-none transition-all"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-gray-500 mb-1.5 block uppercase tracking-wider">Place (Optional)</label>
              {newItemPlaceId ? (
                <div className="flex justify-between items-center p-3 bg-blue-50 border border-blue-100 rounded-lg">
                  <div className="flex items-center gap-2 overflow-hidden">
                    <Map size={16} className="text-blue-500 shrink-0" />
                    <span className="text-sm font-medium text-blue-800 truncate">{newItemPlaceName}</span>
                  </div>
                  <button onClick={() => { setNewItemPlaceId(null); setNewItemPlaceName(""); }} className="text-blue-400 hover:text-blue-600 transition-colors ml-2 shrink-0">
                    <X size={16} />
                  </button>
                </div>
              ) : (
                <PlaceAutocomplete
                  onPlaceSelect={(p) => {
                    if (p.place_id && p.description) {
                      setNewItemPlaceId(p.place_id);
                      setNewItemPlaceName(p.description);
                    }
                  }}
                  onClose={() => {}}
                />
              )}
            </div>
            <div className="flex justify-end pt-2">
              <Button
                disabled={isAddingItem || (!newItemNote.trim() && !newItemPlaceId)}
                onClick={handleInlineSubmit}
                size="sm"
                className="bg-blue-600 hover:bg-blue-700 text-white font-medium px-4"
              >
                {isAddingItem ? (
                  <><Loader2 size={14} className="mr-2 animate-spin" /> Saving...</>
                ) : (
                  "Save Item"
                )}
              </Button>
            </div>
          </div>
        ) : (
          <button
            className="cursor-pointer px-4 py-3 flex gap-2 items-center justify-center rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:border-blue-400 hover:text-blue-500 hover:bg-blue-50 transition-all duration-200"
            onClick={handleAddItemClick}
          >
            <Plus size={16} strokeWidth={3} />
            <span className="text-sm font-medium">Add An Item</span>
          </button>
        )}
      </div>

      {editingItem && (
        <CustomDialog
          open={!!editingItem}
          onOpenChange={(open) => !open && setEditingItem(null)}
          title="Edit Item"
          confirmLabel="Confirm"
          children={
            <ItineraryItemEditor
              selectedDayId={editingItem.itineraryDayId}
              setSelectedDayId={handleSelectItineraryDayId}
              itineraryDays={allItineraryDays}
              planStartTime={planStartTime}
              startTime={convertTimeOnlyStringToDate(editingItem.startTime)}
              duration={editingItem.duration || ""}
              note={editingItem.note || ""}
              setStartTime={handleSelectStartTime}
              setDuration={handleSelectDuration}
              setNote={(n) => {
                if (editingItem) setEditingItem({ ...editingItem, note: n });
              }}
              placeId={editedPlaceId}
              setPlaceId={setEditedPlaceId}
              placeName={editedPlaceName}
              setPlaceName={setEditedPlaceName}
            />
          }
          onConfirm={() =>
            handleConfirmUpdateItineraryItem(
              editingItem.itineraryDayId,
              editingItem.startTime,
              editingItem.duration,
              editingItem.note ?? undefined,
              editedPlaceId,
            )
          }
        />
      )}

      <ConfirmDeleteModal
        open={!!itemToDelete}
        onOpenChange={(open) => !open && setItemToDelete(null)}
        title="Delete Itinerary Item"
        description={`Are you sure you want to delete "${itemToDelete?.place?.title || "this item"}"? This action cannot be undone.`}
        onConfirm={handleConfirmDeleteItineraryItem}
      />

      <ConfirmDeleteModal
        open={!!dayToDelete}
        onOpenChange={(open) => !open && setDayToDelete(null)}
        title="Delete Itinerary Day"
        description={`Are you sure you want to delete "Day ${itineraryDay.order + 1}" and all its items? This action cannot be undone.`}
        onConfirm={handleConfirmDeleteItineraryDay}
      />
    </div>
  );
}
