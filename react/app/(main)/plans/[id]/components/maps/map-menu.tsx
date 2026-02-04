"use client";

import { useState, useRef, useEffect } from "react";
import {
  ChevronDown,
  Eye,
  EyeOff,
  Layers,
  Calendar,
  Route,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface MapMenuProps {
  showMarkers: boolean;
  setShowMarkers: (show: boolean) => void;
  showDirections: boolean;
  setShowDirections: (show: boolean) => void;
  filterMode: "all" | "byDay";
  setFilterMode: (mode: "all" | "byDay") => void;
  className?: string;
}

export default function MapMenu({
  showMarkers,
  setShowMarkers,
  showDirections,
  setShowDirections,
  filterMode,
  setFilterMode,
  className,
}: MapMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node) &&
        !triggerRef.current?.contains(event.target as Node)
      ) {
        setIsOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  return (
    <div className={cn("flex flex-col items-center", className)}>
      {/* Toggle Button */}
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          "h-8 w-8 rounded-full bg-white/95 backdrop-blur-sm shadow-lg border border-gray-200 hover:bg-white transition-transform",
          isOpen && "rotate-180",
        )}
        onClick={() => setIsOpen(!isOpen)}
        ref={triggerRef}
      >
        <ChevronDown size={16} className="text-gray-600" />
      </Button>

      {/* Menu Content */}
      {isOpen && (
        <div
          className="mt-2 bg-white/95 backdrop-blur-sm rounded-xl shadow-lg border border-gray-200 p-4 min-w-[200px] animate-in slide-in-from-top-2 duration-200"
          ref={menuRef}
        >
          <div className="space-y-4">
            {/* Show/Hide Markers */}
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                {showMarkers ? (
                  <Eye size={16} className="text-gray-600" />
                ) : (
                  <EyeOff size={16} className="text-gray-400" />
                )}
                <Label htmlFor="show-markers" className="text-sm font-medium">
                  Show Markers
                </Label>
              </div>
              <Switch
                id="show-markers"
                checked={showMarkers}
                onCheckedChange={setShowMarkers}
                className="data-[state=checked]:bg-blue-500"
              />
            </div>

            {/* Show/Hide Directions */}
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <Route
                  size={16}
                  className={showDirections ? "text-blue-500" : "text-gray-400"}
                />
                <Label
                  htmlFor="show-directions"
                  className="text-sm font-medium"
                >
                  Show Directions
                </Label>
              </div>
              <Switch
                id="show-directions"
                checked={showDirections}
                onCheckedChange={setShowDirections}
                className="data-[state=checked]:bg-blue-500"
              />
            </div>

            {/* Divider */}
            <div className="border-t border-gray-100" />

            {/* Filter Mode */}
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                <Layers size={16} />
                <span>Filter</span>
              </div>
              <div className="flex gap-2">
                <button
                  className={cn(
                    "cursor-pointer flex-1 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                    filterMode === "all"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200",
                  )}
                  onClick={() => setFilterMode("all")}
                >
                  All Days
                </button>
                <button
                  className={cn(
                    "cursor-pointer flex-1 px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center justify-center gap-1",
                    filterMode === "byDay"
                      ? "bg-blue-500 text-white"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200",
                  )}
                  onClick={() => setFilterMode("byDay")}
                >
                  <Calendar size={12} />
                  By Day
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
