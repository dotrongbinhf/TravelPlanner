"use client";

import { DateRangePicker } from "@/components/date-range-picker";
import { forwardRef, useEffect, useState, useCallback } from "react";
import { List, LayoutGrid, Loader2, CalendarRange } from "lucide-react";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import ItineraryCalendar from "./itinerary-calendar";
import { useGoogleCalendar } from "@/hooks/use-google-calendar";
import Image from "next/image";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { LogOut } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface ItineraryProps {
  className?: string;
  planId: string;
  startTime: Date | null;
  endTime: Date | null;
  itineraryDays: ItineraryDay[];
  lastSyncGoogleCalendarAt?: string;
  onChange: (startTime: Date | null, endTime: Date | null) => void;
  onItineraryDaysUpdate: (days: ItineraryDay[]) => void;
  onSyncComplete: (syncedAt: string) => void;
}

const Itinerary = forwardRef<HTMLDivElement, ItineraryProps>(function Itinerary(
  {
    className,
    planId,
    startTime,
    endTime,
    itineraryDays,
    lastSyncGoogleCalendarAt,
    onChange,
    onItineraryDaysUpdate,
    onSyncComplete,
  },
  ref,
) {
  const [viewMode, setViewMode] = useState<"list" | "calendar">("list");
  const {
    isConnected,
    isSyncing,
    googleEmail,
    googleAvatarUrl,
    connectGoogle,
    syncCalendar,
    disconnectAccount,
  } = useGoogleCalendar();

  const getLastSyncText = useCallback(() => {
    if (!lastSyncGoogleCalendarAt) return null;
    const syncDate = new Date(lastSyncGoogleCalendarAt);
    const now = new Date();
    const diffMs = now.getTime() - syncDate.getTime();
    const diffMinutes = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMinutes < 1) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  }, [lastSyncGoogleCalendarAt]);

  const [tooltipText, setTooltipText] = useState<string | null>(null);
  const handleTooltipOpen = () => {
    const syncText = getLastSyncText();
    if (isConnected) {
      setTooltipText(
        `Sync itinerary to Google Calendar${syncText ? ` (last: ${syncText})` : ""}`,
      );
    } else {
      setTooltipText("Connect & sync to Google Calendar");
    }
  };

  const handleSyncGoogleCalendar = async () => {
    try {
      if (!isConnected) {
        await connectGoogle();
      }
      const result = await syncCalendar(planId);
      if (result) {
        onSyncComplete(result.syncedAt);
        // Update google calendar event IDs in local state
        if (result.eventMappings.length > 0) {
          const mappingsMap = Object.fromEntries(
            result.eventMappings.map((m) => [
              m.itineraryItemId,
              m.googleCalendarEventId,
            ]),
          );
          onItineraryDaysUpdate(
            itineraryDays.map((day) => ({
              ...day,
              itineraryItems: day.itineraryItems?.map((item) =>
                mappingsMap[item.id]
                  ? {
                      ...item,
                      googleCalendarEventId: mappingsMap[item.id],
                    }
                  : item,
              ),
            })),
          );
        }
      }
    } catch {
      // Errors are handled in the hook
    }
  };

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
      if (deletedDay.order === 0 && startTime && endTime) {
        const newStartTime = new Date(startTime);
        newStartTime.setDate(newStartTime.getDate() + 1);
        onChange(newStartTime, endTime);
      } else if (startTime && endTime) {
        const newEndTime = new Date(endTime);
        newEndTime.setDate(newEndTime.getDate() - 1);
        onChange(startTime, newEndTime);
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
        <div className="flex items-center gap-3">
          <TooltipProvider>
            <Tabs
              value={viewMode}
              onValueChange={(v) => setViewMode(v as "list" | "calendar")}
              className="h-[42px]"
            >
              <TabsList className="h-full bg-gray-100 gap-1 p-1">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <TabsTrigger
                        value="list"
                        className="p-1.5 cursor-pointer transition-all data-[state=active]:bg-white data-[state=active]:text-black data-[state=active]:shadow-sm"
                      >
                        <List className="w-4 h-4" />
                      </TabsTrigger>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>List View</p>
                  </TooltipContent>
                </Tooltip>

                <Tooltip>
                  <TooltipTrigger asChild>
                    <span>
                      <TabsTrigger
                        value="calendar"
                        className="p-1.5 cursor-pointer transition-all data-[state=active]:bg-white data-[state=active]:text-black data-[state=active]:shadow-sm"
                      >
                        <CalendarRange className="w-4 h-4" />
                      </TabsTrigger>
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>Calendar View</p>
                  </TooltipContent>
                </Tooltip>
              </TabsList>
            </Tabs>
          </TooltipProvider>

          {/* Google Calendar Sync Button */}
          <TooltipProvider>
            <Tooltip onOpenChange={(open) => open && handleTooltipOpen()}>
              <TooltipTrigger asChild>
                <button
                  onClick={handleSyncGoogleCalendar}
                  disabled={isSyncing}
                  className="cursor-pointer flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-50 transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed h-[42px]"
                >
                  {isSyncing ? (
                    <Loader2 className="w-5 h-5 animate-spin text-gray-500" />
                  ) : (
                    <Image
                      src="/images/plans/google-calendar.png"
                      alt="Google Calendar"
                      width={20}
                      height={20}
                    />
                  )}
                  <span className="text-xs font-medium text-gray-700">
                    {isSyncing
                      ? "Syncing..."
                      : isConnected
                        ? "Sync"
                        : "Connect"}
                  </span>
                  {googleAvatarUrl && (
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <div
                          className="relative cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                        >
                          <TooltipProvider>
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <img
                                  src={googleAvatarUrl}
                                  alt={googleEmail ?? "Google"}
                                  className="w-6 h-6 rounded-full ring-1 ring-gray-200"
                                  referrerPolicy="no-referrer"
                                />
                              </TooltipTrigger>
                              <TooltipContent>
                                <p>{googleEmail}</p>
                              </TooltipContent>
                            </Tooltip>
                          </TooltipProvider>
                        </div>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem
                          className="text-red-600 focus:bg-red-50 focus:text-red-700 cursor-pointer"
                          onClick={(e) => {
                            e.stopPropagation();
                            disconnectAccount();
                          }}
                        >
                          <LogOut className="w-4 h-4 mr-2" />
                          Disconnect Account
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  )}
                </button>
              </TooltipTrigger>
              <TooltipContent>
                <p>{tooltipText ?? "Google Calendar"}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>

          <DateRangePicker
            startDate={startTime}
            endDate={endTime}
            onChange={handleDateUpdate}
            className="font-medium"
            iconStrokeWidth={3}
            showActions={true}
          />
        </div>
      </div>

      {viewMode === "list" ? (
        <div className="flex flex-col gap-6">
          {itineraryDays
            .toSorted((a, b) => a.order - b.order)
            .map((day, index) => (
              <ItineraryDayCard
                key={day.id}
                allItineraryDays={itineraryDays}
                itineraryDay={day}
                dayIndex={index}
                totalDays={itineraryDays.length}
                planStartTime={startTime || new Date()}
                onEditTitle={handleUpdateDayTitle}
                onAddItem={handleAddItem}
                onUpdateItem={handleUpdateItem}
                onDeleteItem={handleDeleteItem}
                onDeleteDay={handleDeleteDay}
              />
            ))}
        </div>
      ) : (
        <ItineraryCalendar
          itineraryDays={itineraryDays}
          startTime={startTime}
          endTime={endTime}
          onAddItem={handleAddItem}
          onUpdateItem={handleUpdateItem}
          onDeleteItem={handleDeleteItem}
        />
      )}
    </section>
  );
});

export default Itinerary;
