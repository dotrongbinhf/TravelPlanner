"use client";

import { DateRangePicker } from "@/components/date-range-picker";
import { forwardRef, useEffect } from "react";
import { updatePlanBasicInfo } from "@/api/plan/plan";
import toast from "react-hot-toast";
import { ItineraryDay } from "@/types/itineraryDay";
import ItineraryDayCard from "./itinerary-day-card";
import {
  updateItineraryDay,
  deleteItineraryDay,
} from "@/api/itineraryDay/itineraryDay";
import { ItineraryItem } from "@/types/itineraryItem";
import { useItineraryContext } from "../../../../../../contexts/ItineraryContext";

interface ItineraryProps {
  className?: string;
  planId: string;
  startTime: Date | null;
  endTime: Date | null;
  itineraryDays: ItineraryDay[];
  onChange: (startTime: Date | null, endTime: Date | null) => void;
  onItineraryDaysUpdate: (days: ItineraryDay[]) => void;
}

const Itinerary = forwardRef<HTMLDivElement, ItineraryProps>(function Itinerary(
  {
    className,
    planId,
    startTime,
    endTime,
    itineraryDays,
    onChange,
    onItineraryDaysUpdate,
  },
  ref,
) {
  const handleDateUpdate = async (start: Date | null, end: Date | null) => {
    if (!start || !end) return;
    try {
      const newPlan = await updatePlanBasicInfo(planId, {
        startTime: start,
        endTime: end,
      });
      onChange(start, end);
      onItineraryDaysUpdate(newPlan.itineraryDays ?? []);
      toast.success("Updated Plan Duration");
    } catch (error) {
      console.error("Error updating plan duration:", error);
      toast.error("Failed to update plan duration");
    }
  };

  const handleUpdateDayTitle = async (dayId: string, newTitle: string) => {
    try {
      await updateItineraryDay(dayId, { title: newTitle });
      onItineraryDaysUpdate(
        itineraryDays.map((day) =>
          day.id === dayId ? { ...day, title: newTitle } : day,
        ),
      );
      toast.success("Updated Day Title");
    } catch (error) {
      console.error("Error updating day title:", error);
      toast.error("Failed to update day title");
    }
  };

  const handleAddItem = (newItem: ItineraryItem) => {
    onItineraryDaysUpdate(
      itineraryDays.map((d) =>
        d.id === newItem.itineraryDayId
          ? {
              ...d,
              itineraryItems: [...(d.itineraryItems || []), newItem],
            }
          : d,
      ),
    );
  };

  const handleUpdateItem = (updatedItem: ItineraryItem) => {
    onItineraryDaysUpdate(
      itineraryDays.map((d) => {
        if (d.id === updatedItem.itineraryDayId) {
          const exists = d.itineraryItems?.some(
            (item) => item.id === updatedItem.id,
          );
          return {
            ...d,
            itineraryItems: exists
              ? d.itineraryItems?.map((item) =>
                  item.id === updatedItem.id ? updatedItem : item,
                )
              : [...(d.itineraryItems || []), updatedItem],
          };
        } else {
          return {
            ...d,
            itineraryItems: d.itineraryItems?.filter(
              (item) => item.id !== updatedItem.id,
            ),
          };
        }
      }),
    );
  };

  const handleDeleteItem = (itemId: string, dayId: string) => {
    onItineraryDaysUpdate(
      itineraryDays.map((d) =>
        d.id === dayId
          ? {
              ...d,
              itineraryItems: d.itineraryItems?.filter(
                (item) => item.id !== itemId,
              ),
            }
          : d,
      ),
    );
  };

  const handleDeleteDay = async (dayId: string) => {
    try {
      await deleteItineraryDay(dayId);
      const deletedDay = itineraryDays.find((d) => d.id === dayId);
      if (!deletedDay) return;

      onItineraryDaysUpdate(
        itineraryDays
          .filter((d) => d.id !== dayId)
          .map((d) =>
            d.order > deletedDay.order ? { ...d, order: d.order - 1 } : d,
          ),
      );

      // Adjust plan duration
      if (deletedDay.order === 0) {
        if (startTime && endTime) {
          const newStartTime = new Date(startTime);
          newStartTime.setDate(newStartTime.getDate() + 1);
          onChange(newStartTime, endTime);
        }
      } else {
        if (startTime && endTime) {
          const newEndTime = new Date(endTime);
          newEndTime.setDate(newEndTime.getDate() - 1);
          onChange(startTime, newEndTime);
        }
      }

      toast.success("Deleted Day");
    } catch (error) {
      console.error("Error deleting day:", error);
      toast.error("Failed to delete day");
    }
  };

  // Scroll to selected item
  const { selectedPlace } = useItineraryContext();
  useEffect(() => {
    if (
      selectedPlace.isFromItinerary &&
      selectedPlace.dayIndex !== null &&
      selectedPlace.itemIndex !== null &&
      selectedPlace.triggerSource === "map"
    ) {
      const sortedDays = [...itineraryDays].sort((a, b) => a.order - b.order);
      const day = sortedDays[selectedPlace.dayIndex];
      if (day) {
        const sortedItems = [...(day.itineraryItems || [])].sort((a, b) =>
          (a.startTime ?? "").localeCompare(b.startTime ?? ""),
        );
        const item = sortedItems[selectedPlace.itemIndex];
        if (item) {
          const element = document.getElementById(`itinerary-item-${item.id}`);
          if (element) {
            element.scrollIntoView({ behavior: "smooth", block: "center" });
          }
        }
      }
    }
  }, [selectedPlace, itineraryDays]);

  return (
    <section
      ref={ref}
      id="itinerary"
      data-section-id="itinerary"
      className={className}
    >
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-gray-800">Itinerary</h2>
        <DateRangePicker
          startDate={startTime}
          endDate={endTime}
          onChange={handleDateUpdate}
          className="font-medium"
          iconStrokeWidth={3}
          showActions={true}
        />
      </div>

      <div className="flex flex-col gap-6">
        {itineraryDays
          .sort((a, b) => a.order - b.order)
          .map((day, index) => (
            <ItineraryDayCard
              key={day.id}
              allItineraryDays={itineraryDays}
              itineraryDay={day}
              dayIndex={index}
              planStartTime={startTime || new Date()}
              onEditTitle={handleUpdateDayTitle}
              onAddItem={handleAddItem}
              onUpdateItem={handleUpdateItem}
              onDeleteItem={handleDeleteItem}
              onDeleteDay={handleDeleteDay}
            />
          ))}
      </div>
    </section>
  );
});

export default Itinerary;
