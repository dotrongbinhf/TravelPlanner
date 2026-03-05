"use client";

import { useState, useEffect } from "react";
import { Plane } from "lucide-react";
import { cn } from "@/lib/utils";
import { CustomDialog } from "@/components/custom-dialog";
import { FlightPreferences } from "@/types/prompt-builder";
import {
  FLIGHT_CABIN_OPTIONS,
  FLIGHT_STOP_OPTIONS,
} from "@/constants/prompt-builder";

interface FlightModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly preferences: FlightPreferences;
  readonly onConfirm: (prefs: FlightPreferences) => void;
}

export function FlightModal({
  open,
  onOpenChange,
  preferences,
  onConfirm,
}: FlightModalProps) {
  const [local, setLocal] = useState<FlightPreferences>(preferences);

  // Update local state when modal opens
  useEffect(() => {
    if (open) {
      setLocal(preferences);
    }
  }, [open, preferences]);

  return (
    <CustomDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Flight Preferences"
      description="Configure your flight requirements or let us know if you already have tickets."
      onConfirm={() => onConfirm(local)}
      confirmLabel="Confirm"
    >
      <div className="space-y-4 py-2">
        {/* Already have or need search */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() =>
              setLocal((prev) => ({ ...prev, status: "already_have" }))
            }
            className={cn(
              "flex-1 px-3 py-2 rounded-lg border text-xs font-medium transition-all",
              local.status === "already_have"
                ? "bg-emerald-50 border-emerald-300 text-emerald-700 ring-1 ring-emerald-200"
                : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50",
            )}
          >
            ✅ Already booked
          </button>
          <button
            type="button"
            onClick={() =>
              setLocal((prev) => ({ ...prev, status: "need_search" }))
            }
            className={cn(
              "flex-1 px-3 py-2 rounded-lg border text-xs font-medium transition-all",
              local.status === "need_search"
                ? "bg-blue-50 border-blue-300 text-blue-700 ring-1 ring-blue-200"
                : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50",
            )}
          >
            🔍 Help me find
          </button>
        </div>

        {local.status === "need_search" && (
          <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-200">
            {/* Cabin class */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">
                Cabin Class
              </label>
              <div className="flex gap-1.5 flex-wrap">
                {FLIGHT_CABIN_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() =>
                      setLocal((prev) => ({
                        ...prev,
                        cabinClass:
                          prev.cabinClass === opt.value ? "" : opt.value,
                      }))
                    }
                    className={cn(
                      "px-2.5 py-1.5 text-xs rounded-lg border transition-all font-medium",
                      local.cabinClass === opt.value
                        ? "bg-blue-50 border-blue-300 text-blue-700"
                        : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50",
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Stops */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">Stops</label>
              <div className="flex gap-1.5">
                {FLIGHT_STOP_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() =>
                      setLocal((prev) => ({
                        ...prev,
                        stops: prev.stops === opt.value ? "" : opt.value,
                      }))
                    }
                    className={cn(
                      "flex-1 px-2 py-1.5 text-xs rounded-lg border transition-all font-medium",
                      local.stops === opt.value
                        ? "bg-blue-50 border-blue-300 text-blue-700"
                        : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50",
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Preferred airline */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">
                Preferred Airline (optional)
              </label>
              <input
                type="text"
                value={local.airline}
                onChange={(e) =>
                  setLocal((prev) => ({ ...prev, airline: e.target.value }))
                }
                placeholder="e.g. Vietnam Airlines, VietJet..."
                className="w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        )}
      </div>
    </CustomDialog>
  );
}
