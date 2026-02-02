"use client";

import * as React from "react";
import {
  format,
  isValid,
  setHours,
  setMinutes,
  isBefore,
  isAfter,
  addMinutes,
  subMinutes,
  startOfMinute,
} from "date-fns";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { X, Calendar as CalendarIcon } from "lucide-react";

export enum TimePickerType {
  START,
  END,
}

type TimePickerProps = {
  value?: Date;
  onChange?: (date: Date | undefined) => void;
  placeholder?: string;
  className?: string;
  triggerClassName?: string;
  label?: string;
  description?: string;
  minDateTime?: Date;
  maxDateTime?: Date;
  type?: TimePickerType;
  readonly?: boolean;
  needTrigger?: boolean;
  externalOpen?: boolean;
  setExternalOpen?: (isOpen: boolean) => void;
  showDate?: boolean; // New prop to control calendar visibility
  disabled?: boolean;
};

export function TimePicker({
  value,
  onChange,
  placeholder = "dd/MM/yyyy HH:mm",
  className,
  triggerClassName,
  label,
  description,
  minDateTime,
  maxDateTime,
  type,
  readonly,
  needTrigger = true,
  externalOpen,
  setExternalOpen,
  showDate = true, // Default to true
  disabled,
}: TimePickerProps) {
  const [open, setOpen] = React.useState(false);
  const isValidDate = value && isValid(value);
  const currentDate = isValidDate ? value : null;

  // Helper to check if a date/time is before minDateTime
  const isBeforeMin = (date: Date) =>
    minDateTime && isValid(minDateTime) ? isBefore(date, minDateTime) : false;

  // Helper to check if a date/time is after maxDateTime
  const isAfterMax = (date: Date) =>
    maxDateTime && isValid(maxDateTime) ? isAfter(date, maxDateTime) : false;

  const isOutOfRange = (date: Date) => isBeforeMin(date) || isAfterMax(date);

  const clampDate = (date: Date): Date => {
    if (minDateTime && isBefore(date, minDateTime)) {
      return type === TimePickerType.END
        ? addMinutes(minDateTime, 5)
        : minDateTime;
    }
    if (maxDateTime && isAfter(date, maxDateTime)) {
      return type === TimePickerType.START
        ? subMinutes(maxDateTime, 5)
        : maxDateTime;
    }
    return date;
  };

  const handleDateChange = (date: Date | undefined) => {
    if (!date) {
      onChange?.(undefined);
      return;
    }

    // Preserve current time if modifying date, or set to min time if new date
    let newDate = date;
    if (currentDate) {
      newDate = setHours(newDate, currentDate.getHours());
      newDate = setMinutes(newDate, currentDate.getMinutes());
    }

    // Auto-adjust time if it falls out of range on the new day
    if (minDateTime && newDate.toDateString() === minDateTime.toDateString()) {
      if (isBefore(newDate, minDateTime)) {
        newDate = minDateTime; // Simplest clamp
        // Or keep the logic to round up to next 5 mins if exactly min
        newDate = addMinutes(newDate, 5 - (newDate.getMinutes() % 5));
      }
    }

    onChange?.(clampDate(newDate));
  };

  const handleHourChange = (hour: number) => {
    let newDate: Date;

    if (!minDateTime) {
      const base = currentDate ?? new Date();
      newDate = setHours(setMinutes(base, 0), hour);
    } else {
      const baseDate = currentDate ?? new Date(minDateTime);

      newDate = setHours(baseDate, hour);
      const minute = newDate.getMinutes();

      // Align to nearest 5 minutes
      let newMinute = Math.floor(minute / 5) * 5;
      newDate = setMinutes(newDate, newMinute);

      // If matches minDateTime and is before, bump to min minutes
      if (minDateTime && isBefore(newDate, minDateTime)) {
        // If hour matches, we must ensure minute is >= min minute
        if (newDate.getHours() === minDateTime.getHours()) {
          // round up minDateTime minutes to nearest 5
          const minMinutes = Math.ceil(minDateTime.getMinutes() / 5) * 5;
          newDate = setMinutes(newDate, minMinutes);
        } else {
          // If hour is different (shouldn't happen if isBefore check passed only due to minutes, but if hour was also before, clampDate covers it.
          // here we specifically handle the edge case where we just switched hour to minDateTime's hour)
          newDate = minDateTime;
          // Align minDateTime to 5 min grid if needed
          const minMinutes = Math.ceil(newDate.getMinutes() / 5) * 5;
          newDate = setMinutes(newDate, minMinutes);
        }
      }
    }

    onChange?.(clampDate(newDate));
  };

  const handleMinuteChange = (minute: number) => {
    const baseDate =
      currentDate ?? (minDateTime ? new Date(minDateTime) : new Date());
    let newDate = setMinutes(baseDate, minute);
    onChange?.(clampDate(newDate));
  };

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {label && <label className="text-base font-medium">{label}</label>}
      <Popover
        open={needTrigger ? open : externalOpen}
        onOpenChange={needTrigger ? setOpen : setExternalOpen}
      >
        <div className="relative w-full">
          <PopoverTrigger
            asChild
            className={cn(
              "py-[6px]",
              triggerClassName,
              (readonly || disabled) && "pointer-events-none",
            )}
          >
            <Button
              variant="outline"
              disabled={disabled}
              className={cn(
                "w-full px-3 justify-start text-left font-normal h-10",
                !isValidDate ? "text-muted-foreground" : "pr-10",
                readonly && "border-none shadow-none bg-transparent w-fit",
                needTrigger === false && "invisible",
              )}
            >
              {isValidDate ? (
                format(currentDate!, showDate ? "dd/MM/yyyy HH:mm" : "HH:mm")
              ) : (
                <span>{placeholder}</span>
              )}
              {!readonly && !isValidDate && (
                <CalendarIcon className="ml-auto h-4 w-4 opacity-50" />
              )}
            </Button>
          </PopoverTrigger>

          {isValidDate && !readonly && needTrigger && (
            <button
              type="button"
              className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 flex items-center justify-center rounded-md hover:bg-zinc-200 cursor-pointer"
              onClick={(e) => {
                e.stopPropagation();
                onChange?.(undefined);
              }}
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
        <PopoverContent className="w-auto p-0 z-[10000]" align="start">
          <div className="sm:flex">
            {/* Date Picker */}
            {showDate && (
              <Calendar
                mode="single"
                selected={currentDate ?? undefined}
                onSelect={handleDateChange}
                initialFocus
              />
            )}

            {/* Time Picker */}
            <div
              className={cn(
                "flex flex-col sm:flex-row gap-6 sm:gap-8 pr-4",
                showDate ? "ml-5" : "p-4",
              )}
            >
              <div>
                <div className="text-sm font-semibold mb-2 relative left-2 mt-4 sm:mt-0">
                  Hour
                </div>
                <div className="grid grid-cols-6 sm:grid-cols-4 gap-0.5">
                  {Array.from({ length: 24 }, (_, hour) => {
                    const testDate = currentDate
                      ? setHours(currentDate, hour)
                      : setHours(minDateTime || new Date(), hour);
                    // Simplify disabled logic for now to basic range check
                    let disabled = false;

                    // We need to check if ANY minute in this hour is valid
                    // For minDateTime: if testDate hour < minDateTime hour (same day) -> disable
                    // BUT we must be careful with edge cases.

                    // It's easier to check: is the END of this hour < minDateTime?
                    // or START of this hour > maxDateTime?

                    const startOfHour = setMinutes(testDate, 0);
                    const endOfHour = setMinutes(testDate, 59);

                    if (minDateTime && isBefore(endOfHour, minDateTime))
                      disabled = true;
                    if (maxDateTime && isAfter(startOfHour, maxDateTime))
                      disabled = true;

                    return (
                      <Button
                        key={hour}
                        size="icon"
                        variant={
                          currentDate && currentDate.getHours() === hour
                            ? "default"
                            : "ghost"
                        }
                        className={cn(
                          "aspect-square",
                          currentDate && currentDate.getHours() === hour
                            ? "bg-blue-600 text-white hover:bg-blue-600/90"
                            : "hover:bg-gray-200",
                        )}
                        onClick={() => handleHourChange(hour)}
                        disabled={disabled}
                      >
                        {hour.toString().padStart(2, "0")}
                      </Button>
                    );
                  })}
                </div>
              </div>
              <div>
                <div className="text-sm font-semibold mb-2 relative left-2 mt-4 sm:mt-0">
                  Minute
                </div>
                <div className="grid grid-cols-6 sm:grid-cols-4 gap-0.5">
                  {Array.from({ length: 12 }, (_, i) => i * 5).map((minute) => {
                    const testDate = currentDate
                      ? setMinutes(currentDate, minute)
                      : setMinutes(minDateTime || new Date(), minute);

                    let disabled = false;
                    if (minDateTime && isBefore(testDate, minDateTime))
                      disabled = true;
                    if (maxDateTime && isAfter(testDate, maxDateTime))
                      disabled = true;

                    return (
                      <Button
                        key={minute}
                        size="icon"
                        variant={
                          currentDate && currentDate.getMinutes() === minute
                            ? "default"
                            : "ghost"
                        }
                        className={cn(
                          "aspect-square",
                          currentDate && currentDate.getMinutes() === minute
                            ? "bg-blue-600 text-white hover:bg-blue-600/90"
                            : "hover:bg-gray-100",
                        )}
                        onClick={() => handleMinuteChange(minute)}
                        disabled={disabled}
                      >
                        {minute.toString().padStart(2, "0")}
                      </Button>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </PopoverContent>
      </Popover>
      {description && (
        <p className="text-sm text-muted-foreground">{description}</p>
      )}
    </div>
  );
}
