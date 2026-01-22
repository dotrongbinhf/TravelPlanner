"use client";

import { useState, useRef, useEffect } from "react";
import { DateRange, RangeKeyDict } from "react-date-range";
import { format } from "date-fns";
import { Calendar } from "lucide-react";
import "react-date-range/dist/styles.css";
import "react-date-range/dist/theme/default.css";

interface DateRangePickerProps {
  startDate: Date | null;
  endDate: Date | null;
  onChange: (startDate: Date | null, endDate: Date | null) => void;
}

export function DateRangePicker({
  startDate,
  endDate,
  onChange,
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
    const handleClickOutside = (event: MouseEvent) => {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelect = (rangesByKey: RangeKeyDict) => {
    const selection = rangesByKey.selection;
    setRange([
      {
        startDate: selection.startDate || new Date(),
        endDate: selection.endDate || new Date(),
        key: "selection",
      },
    ]);
    onChange(selection.startDate || null, selection.endDate || null);
  };

  const formatDateDisplay = () => {
    if (startDate && endDate) {
      return `${format(startDate, "MMM dd, yyyy")} - ${format(endDate, "MMM dd, yyyy")}`;
    }
    return "Select date range";
  };

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3 py-2 border border-gray-300 rounded-md flex items-center gap-2 text-left focus:outline-none focus:ring-2 focus:ring-blue-500 hover:border-gray-400 transition-colors cursor-pointer"
      >
        <Calendar className="w-4 h-4 text-gray-500" />
        <span
          className={startDate && endDate ? "text-gray-900" : "text-gray-500"}
        >
          {formatDateDisplay()}
        </span>
      </button>

      {isOpen && (
        <DateRange
          ranges={range}
          onChange={handleSelect}
          months={1}
          direction="horizontal"
          rangeColors={["#2563eb"]}
          showDateDisplay={false}
          className="absolute z-50 mt-2 bg-white border border-gray-200 rounded-lg shadow-lg"
          minDate={new Date()}
        />
      )}
    </div>
  );
}
