import { ItineraryDay } from "@/types/itineraryDay";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Map, X } from "lucide-react";
import PlaceAutocomplete from "./place-autocomplete";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format } from "date-fns";
import { TimePicker } from "@/components/time-picker";
import { useEffect } from "react";

interface ItineraryItemEditorProps {
  selectedDayId: string;
  setSelectedDayId: (id: string) => void;
  itineraryDays: ItineraryDay[];
  planStartTime: Date;
  startTime: Date | undefined;
  duration: string; // HH:mm
  setStartTime: (date: Date | undefined) => void;
  setDuration: (duration: string) => void;
  note?: string;
  setNote?: (note: string) => void;
  placeId?: string | null;
  setPlaceId?: (id: string | null) => void;
  placeName?: string;
  setPlaceName?: (name: string) => void;
}

export default function ItineraryItemEditor({
  selectedDayId,
  setSelectedDayId,
  itineraryDays,
  planStartTime,
  startTime,
  duration,
  setStartTime,
  setDuration,
  note,
  setNote,
  placeId,
  setPlaceId,
  placeName,
  setPlaceName,
}: ItineraryItemEditorProps) {
  useEffect(() => {
    if (!selectedDayId && itineraryDays.length > 0) {
      setSelectedDayId(itineraryDays[0].id);
    }
  }, [selectedDayId, itineraryDays, setSelectedDayId]);

  // Helper to convert duration string to Date object for TimePicker
  const getDurationDate = () => {
    if (!duration) return undefined;
    const [hours, minutes] = duration.split(":").map(Number);
    const date = new Date();
    date.setHours(hours);
    date.setMinutes(minutes);
    return date;
  };

  // Build a full DateTime from the selected day + a time-only Date
  const getStartTimeAsFullDate = () => {
    if (!startTime) return undefined;
    const selectedDate = getSelectedDayDate();
    if (!selectedDate) return undefined;
    const fullDate = new Date(selectedDate);
    fullDate.setHours(startTime.getHours(), startTime.getMinutes(), 0, 0);
    return fullDate;
  };

  // Calculate End Time Date object
  const getEndTimeDate = () => {
    if (!startTime || !duration) return undefined;
    const fullStart = getStartTimeAsFullDate();
    if (!fullStart) return undefined;

    const [hours, minutes] = duration.split(":").map(Number);
    const endDate = new Date(fullStart);
    endDate.setHours(fullStart.getHours() + hours);
    endDate.setMinutes(fullStart.getMinutes() + minutes);
    return endDate;
  };

  // Calculate the day offset of end time relative to start time's day
  const getEndTimeDayOffset = () => {
    if (!startTime || !duration) return 0;
    const [durHours, durMinutes] = duration.split(":").map(Number);
    const startMinutes = startTime.getHours() * 60 + startTime.getMinutes();
    const totalEndMinutes = startMinutes + durHours * 60 + durMinutes;
    return Math.floor(totalEndMinutes / (24 * 60));
  };

  const handleEndTimeChange = (date: Date | undefined) => {
    if (!date || !startTime) {
      if (!date) setDuration("");
      return;
    }

    // Use full start datetime (with correct day) for comparison
    const fullStart = getStartTimeAsFullDate();
    if (!fullStart) return;

    const diffInMs = date.getTime() - fullStart.getTime();
    if (diffInMs <= 0) {
      // End time is at or before start time - ignore
      return;
    }

    const diffInMinutes = Math.floor(diffInMs / (1000 * 60));
    const hours = Math.floor(diffInMinutes / 60);
    const minutes = diffInMinutes % 60;
    setDuration(
      `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`,
    );
  };

  // Calculate Max End Time (Start Time + 24h 00m), using full date
  const getMaxEndTime = () => {
    const fullStart = getStartTimeAsFullDate();
    if (!fullStart) return undefined;

    // Also cap at the end of the last itinerary day (23:55)
    const lastDay = itineraryDays[itineraryDays.length - 1];
    if (lastDay) {
      const lastDayEnd = new Date(planStartTime);
      lastDayEnd.setDate(lastDayEnd.getDate() + lastDay.order);
      lastDayEnd.setHours(23, 55, 0, 0);

      const startPlus24 = new Date(fullStart);
      startPlus24.setDate(startPlus24.getDate() + 1);

      // Return the earlier of startTime+24h or end of last day
      return startPlus24.getTime() < lastDayEnd.getTime()
        ? startPlus24
        : lastDayEnd;
    }

    const max = new Date(fullStart);
    max.setDate(max.getDate() + 1);
    return max;
  };

  const getEndTimeDayLabel = () => {
    const selectedDate = getSelectedDayDate();
    if (!selectedDate) return undefined;

    const endDate = getEndTimeDate();
    if (endDate) {
      const dayOffset = getEndTimeDayOffset();
      const endDay = new Date(selectedDate);
      endDay.setDate(endDay.getDate() + dayOffset);
      return format(endDay, "MMM dd");
    }

    // No end time yet, show the selected day's date
    return format(selectedDate, "MMM dd");
  };

  const canNextDay = () => {
    const maxEnd = getMaxEndTime();
    const selectedDay = itineraryDays.find((d) => d.id === selectedDayId);
    if (!selectedDay) return false;

    const endDate = getEndTimeDate();

    // When no end time yet (no duration), allow next day if selected day isn't last
    if (!endDate) {
      return selectedDay.order < itineraryDays.length - 1 && !!startTime;
    }

    if (!maxEnd) return false;

    const currentEndDayOffset = getEndTimeDayOffset();
    const endDayOrder = selectedDay.order + currentEndDayOffset;

    // Check if max end time allows going to next day
    const endDayStart = new Date(endDate);
    endDayStart.setHours(0, 0, 0, 0);
    const maxDayStart = new Date(maxEnd);
    maxDayStart.setHours(0, 0, 0, 0);

    return (
      endDayOrder < itineraryDays.length - 1 &&
      endDayStart.getTime() < maxDayStart.getTime()
    );
  };

  const canPrevDay = () => {
    return getEndTimeDayOffset() > 0;
  };

  const handleNextDay = () => {
    if (!startTime) return;

    const fullStart = getStartTimeAsFullDate();
    if (!fullStart) return;

    const endDate = getEndTimeDate();
    const maxEnd = getMaxEndTime();

    let newDate: Date;
    if (!endDate) {
      // No end time yet — set to 00:00 of the next day relative to startTime
      newDate = new Date(fullStart);
      newDate.setDate(newDate.getDate() + 1);
      newDate.setHours(0, 0, 0, 0);
    } else {
      newDate = new Date(endDate);
      newDate.setDate(newDate.getDate() + 1);
    }

    // If adding a day exceeds maxEnd, clamp to maxEnd
    if (maxEnd && newDate > maxEnd) {
      handleEndTimeChange(maxEnd);
    } else {
      handleEndTimeChange(newDate);
    }
  };

  const handlePrevDay = () => {
    const endDate = getEndTimeDate();
    if (!endDate) return;
    const fullStart = getStartTimeAsFullDate();
    const newDate = new Date(endDate);
    newDate.setDate(newDate.getDate() - 1);

    if (fullStart && newDate < fullStart) {
      handleEndTimeChange(
        new Date(Math.max(fullStart.getTime(), newDate.getTime())),
      );
    } else {
      handleEndTimeChange(newDate);
    }
  };

  const handleDurationChange = (date: Date | undefined) => {
    if (date) {
      setDuration(format(date, "HH:mm"));
    } else {
      setDuration("");
    }
  };

  const getSelectedDayDate = () => {
    if (!selectedDayId) return undefined;
    const day = itineraryDays.find((d) => d.id === selectedDayId);
    if (!day) return undefined;
    const date = new Date(planStartTime);
    date.setDate(date.getDate() + day.order);
    return date;
  };

  const getStartTimeDayLabel = () => {
    const date = getSelectedDayDate();
    return date ? format(date, "MMM dd") : undefined;
  };

  return (
    <div className="grid gap-5 py-4">
      <div className="grid grid-cols-4 items-center gap-4">
        <Label
          htmlFor="day-select"
          className="text-right font-medium text-gray-700"
        >
          Day
        </Label>
        <div className="col-span-3">
          <Select value={selectedDayId} onValueChange={setSelectedDayId}>
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a day" />
            </SelectTrigger>
            <SelectContent position="popper">
              {itineraryDays.map((day) => {
                const date = new Date(planStartTime);
                date.setDate(date.getDate() + day.order);
                return (
                  <SelectItem key={day.id} value={day.id}>
                    Day {day.order + 1} ({format(date, "MMM dd")})
                    {day.title ? ` - ${day.title}` : ""}
                  </SelectItem>
                );
              })}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="grid grid-cols-4 items-center gap-4">
        <Label className="text-right font-medium text-gray-700">
          Start Time
        </Label>
        <div className="col-span-3">
          <TimePicker
            value={startTime}
            onChange={setStartTime}
            placeholder="Start Time"
            showDate={false}
            dayLabel={getStartTimeDayLabel()}
            disabled={!selectedDayId}
          />
        </div>
      </div>
      <div className="grid grid-cols-4 items-center gap-4">
        <Label className="text-right font-medium text-gray-700">Duration</Label>
        <div className="col-span-3 flex items-center gap-2">
          <TimePicker
            value={getDurationDate()}
            onChange={handleDurationChange}
            placeholder="Duration"
            showDate={false}
            dayLabel=""
            className="w-full"
          />
        </div>
      </div>
      <div className="grid grid-cols-4 items-center gap-4">
        <Label className="text-right font-medium text-gray-700">End Time</Label>
        <div className="col-span-3 flex items-center gap-2">
          {/* End Time Picker */}
          <TimePicker
            value={getEndTimeDate()}
            onChange={handleEndTimeChange}
            placeholder="End Time"
            showDate={getEndTimeDayOffset() > 0}
            minDateTime={getStartTimeAsFullDate()}
            maxDateTime={getMaxEndTime()}
            dayLabel={getEndTimeDayLabel()}
            canPrevDay={canPrevDay()}
            canNextDay={canNextDay()}
            onPrevDay={handlePrevDay}
            onNextDay={handleNextDay}
            showCalendar={false}
            disabled={!startTime}
            className="w-full"
          />
        </div>
      </div>
      {setPlaceId && setPlaceName && (
        <div className="grid grid-cols-4 items-start gap-4">
          <Label className="text-right font-medium text-gray-700 mt-3">
            Place
          </Label>
          <div className="col-span-3">
            {placeId ? (
              <div className="flex justify-between items-center p-3 bg-blue-50 border border-blue-100 rounded-lg">
                <div className="flex items-center gap-2 overflow-hidden">
                  <Map size={16} className="text-blue-500 shrink-0" />
                  <span className="text-sm font-medium text-blue-800 truncate">
                    {placeName}
                  </span>
                </div>
                <button
                  onClick={() => {
                    setPlaceId(null);
                    setPlaceName("");
                  }}
                  className="text-blue-400 hover:text-blue-600 transition-colors ml-2 shrink-0 cursor-pointer"
                >
                  <X size={16} />
                </button>
              </div>
            ) : (
              <PlaceAutocomplete
                onPlaceSelect={(p) => {
                  if (p.place_id && p.description) {
                    setPlaceId(p.place_id);
                    setPlaceName(p.description);
                  }
                }}
                onClose={() => {}}
              />
            )}
          </div>
        </div>
      )}
      {setNote && (
        <div className="grid grid-cols-4 items-start gap-4">
          <Label className="text-right font-medium text-gray-700 mt-2">
            Note
          </Label>
          <div className="col-span-3">
            <Textarea
              value={note || ""}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Add a note (optional)..."
              className="w-full min-h-[80px]"
            />
          </div>
        </div>
      )}
    </div>
  );
}
