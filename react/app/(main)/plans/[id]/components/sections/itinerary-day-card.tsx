import { ItineraryDay } from "@/types/itineraryDay";
import { Check, Pencil, Plus, X, Clock, Trash } from "lucide-react";
import { useEffect, useRef, useState } from "react";
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
import { useItineraryContext } from "../../../../../../contexts/ItineraryContext";
import { getDayColor } from "../../../../../../constants/day-colors";
import ItineraryItemCardSkeleton from "./itinerary-item-card-skeleton";

interface ItineraryDayCardProps {
  allItineraryDays: ItineraryDay[];
  itineraryDay: ItineraryDay;
  dayIndex: number;
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
  planStartTime,
  onEditTitle,
  onAddItem,
  onUpdateItem,
  onDeleteItem,
  onDeleteDay,
}: ItineraryDayCardProps) {
  const { selectedPlace, selectPlaceFromItinerary, clearPlaceSelection } =
    useItineraryContext();
  const dayColor = getDayColor(dayIndex);
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(itineraryDay.title);

  const [isOpenAutocomplete, setIsOpenAutocomplete] = useState(false);
  const [isAddingItem, setIsAddingItem] = useState(false);

  const [editingItem, setEditingItem] = useState<ItineraryItem | null>(null);
  const [itemToDelete, setItemToDelete] = useState<ItineraryItem | null>(null);
  const [dayToDelete, setDayToDelete] = useState<string | null>(null);

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

  const handleAddPlaceClick = () => {
    setIsOpenAutocomplete(true);
  };

  const handlePlaceSelect = async (
    prediction: google.maps.places.AutocompletePrediction,
  ) => {
    if (!prediction.place_id) return;
    setIsOpenAutocomplete(false);
    setIsAddingItem(true);

    try {
      const response = await createItineraryItem(itineraryDay.id, {
        placeId: prediction.place_id,
      });

      onAddItem(response);
      toast.success("Added to itinerary");

      // Select the newly added item
      const itemsCount = itineraryDay.itineraryItems?.length ?? 0;
      selectPlaceFromItinerary(response, dayIndex, itemsCount, "list");
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

  const handleSelectEndTime = (date: Date | undefined) => {
    if (!editingItem) return;
    const newItineraryItem = { ...editingItem };
    newItineraryItem.endTime = date ? format(date, "HH:mm") : "";
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
    endTime?: string,
  ) => {
    if (!editingItem) return;

    try {
      const response = await updateItineraryItem(editingItem.id, {
        itineraryDayId,
        startTime,
        endTime,
      });

      onUpdateItem(response);
      toast.success("Updated ItineraryItem");
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

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between group">
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
          <div className="flex items-center justify-between gap-2 flex-1 group">
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
              triggerClassName="opacity-0 group-hover:opacity-100 transition-opacity [data-state=open]:opacity-100"
            />
          </div>
        )}
      </div>

      {/* Items List */}
      <div className="flex flex-col gap-3">
        {[...(itineraryDay.itineraryItems || [])]
          .sort((a, b) => (a.startTime ?? "").localeCompare(b.startTime ?? ""))
          .map((item, index, sortedItems) => (
            <ItineraryItemCard
              key={item.id}
              item={item}
              orderNumber={index + 1}
              dayColor={dayColor}
              isFirst={index === 0}
              isLast={index === sortedItems.length - 1}
              isActive={
                selectedPlace.placeId === item.place.placeId &&
                selectedPlace.dayIndex === dayIndex
              }
              onEdit={() => setEditingItem(item)}
              onDelete={() => setItemToDelete(item)}
              onClick={() => selectPlaceFromItinerary(item, dayIndex, index)}
            />
          ))}

        {isAddingItem && <ItineraryItemCardSkeleton />}
      </div>

      <div className="flex flex-col gap-2 relative">
        {isOpenAutocomplete ? (
          <div className="relative z-10">
            <PlaceAutocomplete
              onPlaceSelect={handlePlaceSelect}
              onClose={() => setIsOpenAutocomplete(false)}
            />
          </div>
        ) : (
          <button
            className="cursor-pointer px-4 py-3 flex gap-2 items-center justify-center rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:border-green-400 hover:text-green-500 hover:bg-green-50 transition-all duration-200"
            onClick={handleAddPlaceClick}
          >
            <Plus size={16} strokeWidth={3} />
            <span className="text-sm font-medium">Add A Place</span>
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
              endTime={convertTimeOnlyStringToDate(editingItem.endTime)}
              setStartTime={handleSelectStartTime}
              setEndTime={handleSelectEndTime}
            />
          }
          onConfirm={() =>
            handleConfirmUpdateItineraryItem(
              editingItem.itineraryDayId,
              editingItem.startTime,
              editingItem.endTime,
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
