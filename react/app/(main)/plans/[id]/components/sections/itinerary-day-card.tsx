import { ItineraryDay } from "@/types/itineraryDay";
import { Check, MapPin, Pencil, Plus, X, Clock, Trash } from "lucide-react";
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
import { TimePicker, TimePickerType } from "@/components/time-picker";
import { Button } from "@/components/ui/button";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import { CustomDialog } from "@/components/custom-dialog";
import ItineraryItemEditor from "./itinerary-item-editor";
import ItineraryItemCard from "./itinerary-item-card";
import ActionMenu from "@/components/action-menu";

interface ItineraryDayCardProps {
  allItineraryDays: ItineraryDay[];
  itineraryDay: ItineraryDay;
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
  planStartTime,
  onEditTitle,
  onAddItem,
  onUpdateItem,
  onDeleteItem,
  onDeleteDay,
}: ItineraryDayCardProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [title, setTitle] = useState(itineraryDay.title);

  const [isOpenAutocomplete, setIsOpenAutocomplete] = useState(false);
  const [creatingItem, setCreatingItem] = useState<{
    place: google.maps.places.PlaceResult;
    startTime: Date;
    endTime: Date;
  } | null>(null);

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

  const handlePlaceSelect = (place: google.maps.places.PlaceResult | null) => {
    if (!place) return;
    setIsOpenAutocomplete(false);

    // Default start time to 09:00 or current time if today
    // For simplicity, just use 09:00 and 10:00
    const start = new Date(date);
    start.setHours(9, 0, 0, 0);
    const end = new Date(date);
    end.setHours(10, 0, 0, 0);

    setCreatingItem({
      place,
      startTime: start,
      endTime: end,
    });
  };

  const handleCancelCreateItineraryItem = () => {
    setCreatingItem(null);
  };

  const handleConfirmCreateItineraryItem = async () => {
    if (!creatingItem) return;
    if (!creatingItem.place.place_id) {
      toast.error("Invalid place selected");
      return;
    }

    try {
      const response = await createItineraryItem(itineraryDay.id, {
        placeId: creatingItem.place.place_id,
        startTime: format(creatingItem.startTime, "HH:mm"),
        endTime: format(creatingItem.endTime, "HH:mm"),
      });

      onAddItem(response);
      toast.success("Itinerary item added successfully");
      setCreatingItem(null);
    } catch (error) {
      console.error("Error creating itinerary item:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data?.message ?? "Failed to create item");
      } else {
        toast.error("Failed to create item");
      }
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

  const convertTimeOnlyStringToDate = (timeOnlyString: string) => {
    const [hours, minutes] = timeOnlyString.split(":");
    const date = new Date();
    date.setHours(parseInt(hours), parseInt(minutes), 0, 0);
    return date;
  };

  const handleConfirmUpdateItineraryItem = async (
    itineraryDayId: string,
    startTime: string,
    endTime: string,
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
          .sort((a, b) => a.startTime.localeCompare(b.startTime))
          .map((item) => (
            <ItineraryItemCard
              key={item.id}
              item={item}
              onEdit={() => setEditingItem(item)}
              onDelete={() => setItemToDelete(item)}
            />
          ))}
      </div>

      <div className="flex flex-col gap-2 relative">
        {creatingItem ? (
          <div className="flex flex-col gap-4 p-4 border rounded-lg bg-blue-50/50 border-blue-100 mt-2">
            <div className="flex items-center gap-2 text-blue-700 font-medium">
              <MapPin size={18} />
              <span className="truncate">
                {creatingItem.place.name ||
                  creatingItem.place.formatted_address}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <TimePicker
                label="Start Time"
                value={creatingItem.startTime}
                onChange={(date) =>
                  date &&
                  setCreatingItem((prev) =>
                    prev ? { ...prev, startTime: date } : null,
                  )
                }
                type={TimePickerType.START}
              />
              <TimePicker
                label="End Time"
                value={creatingItem.endTime}
                onChange={(date) =>
                  date &&
                  setCreatingItem((prev) =>
                    prev ? { ...prev, endTime: date } : null,
                  )
                }
                type={TimePickerType.END}
              />
            </div>

            <div className="flex justify-end gap-2 mt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleCancelCreateItineraryItem}
              >
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleConfirmCreateItineraryItem}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                Add Item
              </Button>
            </div>
          </div>
        ) : isOpenAutocomplete ? (
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
