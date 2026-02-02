"use client";

import { useState, useRef, useEffect } from "react";
import { DateRange, RangeKeyDict } from "react-date-range";
import { Calendar, Check, X } from "lucide-react";
import "react-date-range/dist/styles.css";
import "react-date-range/dist/theme/default.css";
import { formatDateRange } from "@/utils/date";
import { cn } from "@/lib/utils";

interface DateRangePickerProps {
  startDate: Date | null;
  endDate: Date | null;
  onChange: (startDate: Date | null, endDate: Date | null) => void;
  className?: string;
  iconStrokeWidth?: number;
  showActions?: boolean;
}

export function DateRangePicker({
  startDate,
  endDate,
  onChange,
  className,
  iconStrokeWidth,
  showActions = false,
}: DateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const [range, setRange] = useState([
    {
      startDate: startDate || new Date(),
      endDate: endDate || new Date(),
      key: "selection",
    },
  ]);

  useEffect(() => {
    setRange([
      {
        startDate: startDate || new Date(),
        endDate: endDate || new Date(),
        key: "selection",
      },
    ]);
  }, [startDate, endDate]);

  const handleCancel = () => {
    setIsOpen(false);
    setRange([
      {
        startDate: startDate || new Date(),
        endDate: endDate || new Date(),
        key: "selection",
      },
    ]);
  };

  const handleConfirm = () => {
    setIsOpen(false);
    const selection = range[0];
    onChange(selection.startDate || null, selection.endDate || null);
  };

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        if (showActions) {
          handleCancel();
        } else {
          setIsOpen(false);
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [startDate, endDate, range, showActions]);

  const handleSelect = (rangesByKey: RangeKeyDict) => {
    const selection = rangesByKey.selection;
    setRange([
      {
        startDate: selection.startDate || new Date(),
        endDate: selection.endDate || new Date(),
        key: "selection",
      },
    ]);
    if (!showActions) {
      onChange(selection.startDate || null, selection.endDate || null);
    }
  };

  const formatDateDisplay = () => {
    if (startDate && endDate) {
      return formatDateRange(startDate, endDate);
    }
    return "Select date range";
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          "w-full px-3 py-2 border border-gray-300 rounded-md flex items-center gap-2 text-left focus:outline-none focus:ring-2 focus:ring-blue-500 hover:border-gray-400 transition-colors cursor-pointer",
          className,
        )}
      >
        <Calendar
          className={"w-4 h-4 text-gray-500"}
          strokeWidth={iconStrokeWidth ?? 2}
        />
        <span
          className={startDate && endDate ? "text-gray-900" : "text-gray-500"}
        >
          {formatDateDisplay()}
        </span>
      </button>

      {isOpen && (
        <div className="absolute right-0 z-[100] mt-2 bg-white border border-gray-200 rounded-lg shadow-lg flex flex-col">
          <DateRange
            ranges={range}
            onChange={handleSelect}
            months={1}
            direction="horizontal"
            rangeColors={["#2563eb"]}
            showDateDisplay={false}
            className="rounded-t-lg"
            minDate={new Date()}
          />
          {showActions && (
            <div className="flex justify-end gap-1 p-2 border-t border-gray-100 bg-gray-50 rounded-b-lg">
              <button
                type="button"
                onClick={handleCancel}
                className="cursor-pointer p-2 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
                title="Cancel"
              >
                <X size={14} />
              </button>
              <button
                type="button"
                onClick={handleConfirm}
                className="cursor-pointer p-2 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
                title="Update"
              >
                <Check size={14} />
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
