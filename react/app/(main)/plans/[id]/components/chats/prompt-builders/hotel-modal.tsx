"use client";

import { useState, useEffect } from "react";
import { Hotel } from "lucide-react";
import { cn } from "@/lib/utils";
import { CustomDialog } from "@/components/custom-dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ChipButton } from "./chip-button";
import { HotelPreferences } from "@/types/prompt-builder";
import {
  HOTEL_STAR_OPTIONS,
  HOTEL_ROOM_OPTIONS,
  HOTEL_AMENITY_OPTIONS,
} from "@/constants/prompt-builder";

interface HotelModalProps {
  readonly open: boolean;
  readonly onOpenChange: (open: boolean) => void;
  readonly preferences: HotelPreferences;
  readonly onConfirm: (prefs: HotelPreferences) => void;
}

export function HotelModal({
  open,
  onOpenChange,
  preferences,
  onConfirm,
}: HotelModalProps) {
  const [local, setLocal] = useState<HotelPreferences>(preferences);

  // Update local state when modal opens
  useEffect(() => {
    if (open) {
      setLocal(preferences);
    }
  }, [open, preferences]);

  const toggleAmenity = (amenity: string) => {
    setLocal((prev) => ({
      ...prev,
      amenities: prev.amenities.includes(amenity)
        ? prev.amenities.filter((a) => a !== amenity)
        : [...prev.amenities, amenity],
    }));
  };

  return (
    <CustomDialog
      open={open}
      onOpenChange={onOpenChange}
      title="Hotel Preferences"
      description="Configure your hotel requirements or let us know if you already have one."
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
            {/* Star rating */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">
                Star Rating
              </label>
              <div className="flex gap-1.5">
                {HOTEL_STAR_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() =>
                      setLocal((prev) => ({
                        ...prev,
                        starRating:
                          prev.starRating === opt.value ? "" : opt.value,
                      }))
                    }
                    className={cn(
                      "flex-1 px-2 py-1.5 text-xs rounded-lg border transition-all font-medium",
                      local.starRating === opt.value
                        ? "bg-blue-50 border-blue-300 text-blue-700"
                        : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50",
                    )}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Room type */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">
                Room Type
              </label>
              <Select
                value={local.roomType}
                onValueChange={(v) =>
                  setLocal((prev) => ({ ...prev, roomType: v }))
                }
              >
                <SelectTrigger size="sm" className="w-full text-xs">
                  <SelectValue placeholder="Select room type" />
                </SelectTrigger>
                <SelectContent position="popper" side="bottom">
                  {HOTEL_ROOM_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Amenities */}
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-gray-700">
                Preferred Amenities
              </label>
              <div className="flex flex-wrap gap-1.5">
                {HOTEL_AMENITY_OPTIONS.map((amenity) => (
                  <ChipButton
                    key={amenity}
                    label={amenity}
                    selected={local.amenities.includes(amenity)}
                    onClick={() => toggleAmenity(amenity)}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </CustomDialog>
  );
}
