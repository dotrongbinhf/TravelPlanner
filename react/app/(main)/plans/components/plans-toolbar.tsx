"use client";

import { Search, X, ArrowUpDown, ArrowUp, ArrowDown, SlidersHorizontal, Calendar, Clock } from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { DateRangePicker } from "@/components/date-range-picker";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

// ── Types ────────────────────────────────────────────────────────
export type PlanStatus = "all" | "upcoming" | "past";
export type SortField = "startTime" | "createdAt" | "name";
export type SortOrder = "asc" | "desc";

export interface ToolbarState {
  search: string;
  status: PlanStatus;
  dateFrom: Date | null;
  dateTo: Date | null;
  sortField: SortField;
  sortOrder: SortOrder;
}

export const DEFAULT_TOOLBAR_STATE: ToolbarState = {
  search: "",
  status: "all",
  dateFrom: null,
  dateTo: null,
  sortField: "startTime",
  sortOrder: "desc",
};

const STATUS_OPTIONS: { value: PlanStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "upcoming", label: "Upcoming" },
  { value: "past", label: "Past" },
];

const SORT_FIELD_OPTIONS: { value: SortField; label: string }[] = [
  { value: "startTime", label: "Trip date" },
  { value: "createdAt", label: "Created date" },
  { value: "name", label: "Name" },
];

// ── Component ────────────────────────────────────────────────────
interface PlansToolbarProps {
  state: ToolbarState;
  onChange: (state: ToolbarState) => void;
}

export default function PlansToolbar({ state, onChange }: PlansToolbarProps) {
  const [localSearch, setLocalSearch] = useState(state.search);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Sync localSearch when parent resets
  useEffect(() => {
    setLocalSearch(state.search);
  }, [state.search]);

  const update = (patch: Partial<ToolbarState>) => {
    onChange({ ...state, ...patch });
  };

  const handleSearchInput = (value: string) => {
    setLocalSearch(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      update({ search: value });
    }, 400);
  };

  const handleClearSearch = () => {
    setLocalSearch("");
    update({ search: "" });
  };

  // Active filter label for the Filter button
  const getFilterLabel = () => {
    if (state.dateFrom && state.dateTo) return "Date range";
    if (state.status === "upcoming") return "Upcoming";
    if (state.status === "past") return "Past";
    return "Filter";
  };

  const hasActiveFilter =
    state.status !== "all" || state.dateFrom !== null || state.dateTo !== null;

  const sortFieldLabel =
    SORT_FIELD_OPTIONS.find((o) => o.value === state.sortField)?.label ?? "Trip date";

  return (
    <div className="flex items-center gap-2 flex-wrap">
      {/* ── Search Input ─────────────────────────────── */}
      <div className="relative min-w-[200px] max-w-[280px] flex-1">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
        <input
          type="text"
          value={localSearch}
          onChange={(e) => handleSearchInput(e.target.value)}
          placeholder="Search plans..."
          className="w-full h-10 pl-9 pr-8 py-2 text-sm border border-gray-200 shadow-sm rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all placeholder:text-gray-400"
        />
        {localSearch && (
          <button
            onClick={handleClearSearch}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded-full hover:bg-gray-100 transition-colors cursor-pointer"
          >
            <X className="w-3 h-3 text-gray-400" />
          </button>
        )}
      </div>

      {/* ── Filter Popover ───────────────────────────── */}
      <Popover>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            className={cn(
              "h-10 text-sm gap-2 cursor-pointer font-medium shadow-sm border-gray-200",
              hasActiveFilter &&
                "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 hover:text-blue-800 hover:border-blue-300",
            )}
          >
            <SlidersHorizontal className="w-4 h-4" />
            {getFilterLabel()}
            {hasActiveFilter && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  update({ status: "all", dateFrom: null, dateTo: null });
                }}
                className="ml-1 p-0.5 rounded-full hover:bg-blue-200/60 transition-colors cursor-pointer text-blue-600"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent
          align="start"
          className="w-[320px] p-0"
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          {/* Status section */}
          <div className="p-3 border-b border-gray-100">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Status
            </p>
            <div className="flex gap-1.5">
              {STATUS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() =>
                    update({
                      status: opt.value,
                      // Clear date range when selecting a status
                      ...(opt.value !== "all"
                        ? { dateFrom: null, dateTo: null }
                        : {}),
                    })
                  }
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium rounded-md transition-all cursor-pointer",
                    state.status === opt.value && !state.dateFrom
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200",
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {/* Date range section */}
          <div className="p-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">
              Date range
            </p>
            <DateRangePicker
              startDate={state.dateFrom}
              endDate={state.dateTo}
              onChange={(from, to) =>
                update({
                  dateFrom: from,
                  dateTo: to,
                  // Clear status when using date range
                  status: from && to ? "all" : state.status,
                })
              }
              className="text-xs h-[34px] w-full"
            />
          </div>
        </PopoverContent>
      </Popover>

      {/* ── Sort ─────────────────────────────────────── */}
      <div className="flex items-center gap-0.5">
        <Select
          value={state.sortField}
          onValueChange={(val: SortField) => update({ sortField: val })}
        >
          <SelectTrigger className="!h-10 text-sm w-[150px] rounded-r-none border-r-0 font-medium border-gray-200 shadow-sm bg-white">
            <div className="flex items-center gap-2">
              <ArrowUpDown className="w-4 h-4 text-gray-500 shrink-0" />
              <SelectValue />
            </div>
          </SelectTrigger>
          <SelectContent>
            {SORT_FIELD_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Button
          variant="outline"
          size="icon"
          className="h-10 w-10 rounded-l-none cursor-pointer shrink-0 border-gray-200 shadow-sm bg-white hover:bg-gray-50"
          onClick={() =>
            update({ sortOrder: state.sortOrder === "asc" ? "desc" : "asc" })
          }
          title={state.sortOrder === "asc" ? "Ascending" : "Descending"}
        >
          {state.sortOrder === "asc" ? (
            <ArrowUp className="w-4 h-4 text-gray-600" />
          ) : (
            <ArrowDown className="w-4 h-4 text-gray-600" />
          )}
        </Button>
      </div>
    </div>
  );
}
