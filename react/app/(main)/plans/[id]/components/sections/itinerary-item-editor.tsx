import { ItineraryDay } from "@/types/itineraryDay";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { format } from "date-fns";
import { TimePicker, TimePickerType } from "@/components/time-picker";
import { useEffect } from "react";

interface ItineraryItemEditorProps {
  selectedDayId: string;
  setSelectedDayId: (id: string) => void;
  itineraryDays: ItineraryDay[];
  planStartTime: Date;
  startTime: Date | undefined;
  endTime: Date | undefined;
  setStartTime: (date: Date | undefined) => void;
  setEndTime: (date: Date | undefined) => void;
}

export default function ItineraryItemEditor({
  selectedDayId,
  setSelectedDayId,
  itineraryDays,
  planStartTime,
  startTime,
  endTime,
  setStartTime,
  setEndTime,
}: ItineraryItemEditorProps) {
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
        <Label className="text-right font-medium text-gray-700">From</Label>
        <div className="col-span-3">
          <TimePicker
            value={startTime}
            onChange={setStartTime}
            placeholder="Start Time"
            showDate={false}
            // minDateTime={getSelectedDate()}
            // maxDateTime={
            //   getSelectedDate()
            //     ? new Date(
            //         getSelectedDate()!.getTime() + 24 * 60 * 60 * 1000 - 1,
            //       )
            //     : undefined
            // }
            disabled={!selectedDayId}
          />
        </div>
      </div>
      <div className="grid grid-cols-4 items-center gap-4">
        <Label className="text-right font-medium text-gray-700">To</Label>
        <div className="col-span-3">
          <TimePicker
            value={endTime}
            onChange={setEndTime}
            placeholder="End Time"
            showDate={false}
            // minDateTime={startTime || getSelectedDate()}
            // maxDateTime={
            //   getSelectedDate()
            //     ? new Date(
            //         getSelectedDate()!.getTime() + 24 * 60 * 60 * 1000 - 1,
            //       )
            //     : undefined
            // }
            type={TimePickerType.END}
            disabled={!selectedDayId}
          />
        </div>
      </div>
    </div>
  );
}
