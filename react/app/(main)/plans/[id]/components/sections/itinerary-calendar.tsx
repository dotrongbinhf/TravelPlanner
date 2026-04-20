"use client";

import {
  useCallback,
  useMemo,
  useRef,
  useState,
  useEffect,
  useLayoutEffect,
} from "react";
import FullCalendar from "@fullcalendar/react";
import timeGridPlugin from "@fullcalendar/timegrid";
import dayGridPlugin from "@fullcalendar/daygrid";
import interactionPlugin from "@fullcalendar/interaction";
import { Pencil, Trash, Moon } from "lucide-react";
import { format } from "date-fns";
import toast from "react-hot-toast";
import type {
  EventClickArg,
  EventDropArg,
  DateSelectArg,
  EventInput,
} from "@fullcalendar/core";
import type { EventResizeDoneArg } from "@fullcalendar/interaction";

import { ItineraryDay } from "@/types/itineraryDay";
import { ItineraryItem } from "@/types/itineraryItem";
import { DAY_COLORS, getDayColor } from "@/constants/day-colors";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";
import { CustomDialog } from "@/components/custom-dialog";
import ActionMenu from "@/components/action-menu";
import {
  createItineraryItem,
  updateItineraryItem,
  deleteItineraryItem,
} from "@/api/itineraryItem/itineraryItem";
import { useItineraryContext } from "@/contexts/ItineraryContext";
import ItineraryItemEditor from "./itinerary-item-editor";
import PlaceAutocomplete from "./place-autocomplete";
import { useEnsurePlace } from "@/hooks/use-ensure-place";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import "./fullcalendar-custom.css";

interface ItineraryCalendarProps {
  itineraryDays: ItineraryDay[];
  startTime: Date | null;
  endTime: Date | null;
  onAddItem: (item: ItineraryItem) => void;
  onUpdateItem: (item: ItineraryItem) => void;
  onDeleteItem: (itemId: string, dayId: string) => void;
}

export default function ItineraryCalendar({
  itineraryDays,
  startTime,
  endTime,
  onAddItem,
  onUpdateItem,
  onDeleteItem,
}: Readonly<ItineraryCalendarProps>) {
  const calendarRef = useRef<FullCalendar>(null);
  const savedScrollTopRef = useRef<number | null>(null);
  const { selectPlaceFromItinerary, clearPlaceSelection, selectedPlace } =
    useItineraryContext();
  const { ensurePlaceExists } = useEnsurePlace();

  // Save/restore scroll position to prevent jumping on event updates
  const saveScrollPosition = useCallback(() => {
    // const scroller = calendarRef.current
    //   ?.getApi()
    //   .el.querySelector(".fc-scroller-liquid-absolute");
    // if (scroller) {
    //   savedScrollTopRef.current = scroller.scrollTop;
    //   console.log("Saved scroll position:", savedScrollTopRef.current);
    // }
  }, []);

  // useLayoutEffect(() => {
  //   if (savedScrollTopRef.current !== null) {
  //     const scroller = calendarRef.current
  //       ?.getApi()
  //       .el.querySelector(".fc-scroller-liquid-absolute");
  //     if (scroller) {
  //       scroller.scrollTop = savedScrollTopRef.current;
  //     }
  //     savedScrollTopRef.current = null;
  //   }
  // });

  // --- State ---
  const [activeCalendarItemId, setActiveCalendarItemId] = useState<
    string | null
  >(null);

  const [calendarEditingItem, setCalendarEditingItem] =
    useState<ItineraryItem | null>(null);
  const [calendarEditedPlaceId, setCalendarEditedPlaceId] = useState<string | null>(null);
  const [calendarEditedPlaceName, setCalendarEditedPlaceName] = useState("");
  const [calendarEditedNote, setCalendarEditedNote] = useState("");
  const [calendarDeletingItem, setCalendarDeletingItem] =
    useState<ItineraryItem | null>(null);
  const [calendarAddingDayId, setCalendarAddingDayId] = useState<string | null>(
    null,
  );
  const [calendarAddingTime, setCalendarAddingTime] = useState<{
    start: string;
    end: string;
    duration: string;
    startDate: Date;
    endDate: Date;
  } | null>(null);

  // Refs for stable event content renderer
  const activeItemIdRef = useRef<string | null>(null);
  const editItemRef = useRef<(item: ItineraryItem) => void>(() => {});
  const deleteItemRef = useRef<(item: ItineraryItem) => void>(() => {});

  editItemRef.current = (item) => {
    setCalendarEditingItem(item);
    setCalendarEditedPlaceId(item.place?.placeId ?? null);
    setCalendarEditedPlaceName(item.place?.title ?? "");
    setCalendarEditedNote(item.note ?? "");
  };
  deleteItemRef.current = (item) => setCalendarDeletingItem(item);

  // Synchronous active-item
  const setActiveItem = useCallback((id: string | null) => {
    activeItemIdRef.current = id;
    setActiveCalendarItemId(id);
  }, []);

  useEffect(() => {
    if (!selectedPlace.placeId) {
      setActiveItem(null);
    }
  }, [selectedPlace, setActiveItem]);

  // Event content renderer
  const renderEventContent = useMemo(() => {
    return function EventContentRenderer(eventInfo: {
      event: {
        id: string;
        title: string;
        extendedProps: Record<string, unknown>;
      };
      timeText: string;
    }) {
      const itemId = eventInfo.event.id;
      const isActive = activeItemIdRef.current === itemId;
      const itineraryItem = eventInfo.event.extendedProps?.itineraryItem as
        | ItineraryItem
        | undefined;
      const isDraft = !!eventInfo.event.extendedProps?.isDraft;
      const isRealEvent = !!itineraryItem?.id;

      const contentNode = (
        <div className="group/event flex items-start gap-1 px-1.5 py-0.5 h-full relative w-full overflow-hidden">
          <div className="flex-1 min-w-0 flex flex-col justify-start">
            <div className="text-[11px] font-bold opacity-90 leading-[1.1] flex items-center gap-0.5 flex-wrap">
              {eventInfo.timeText.split(" - ").map((part, index) => {
                const text = part.trim();
                const isMoon = text === "00:00" || text === "24:00";
                return (
                  <span key={index} className="flex items-center">
                    {index > 0 && <span className="mx-1">-</span>}
                    {isMoon ? (
                      <Moon className="w-3 h-3 inline-block" strokeWidth={3} />
                    ) : (
                      text
                    )}
                  </span>
                );
              })}
            </div>
            <p className="text-xs font-semibold whitespace-normal break-words leading-[1.1] mt-0.5 line-clamp-2">
              {eventInfo.event.title || "Untitled Activity"}
            </p>
          </div>
          {/* ActionMenu — visible on hover or when active (only for real events) */}
          {isRealEvent && !isDraft && (
            <div
              data-action="menu"
              className={`shrink-0 transition-opacity ${
                isActive
                  ? "opacity-100"
                  : "opacity-0 group-hover/event:opacity-100"
              }`}
            >
              <ActionMenu
                options={[
                  {
                    label: "Edit",
                    icon: Pencil,
                    variant: "edit",
                    onClick: () => editItemRef.current(itineraryItem),
                  },
                  {
                    label: "Delete",
                    icon: Trash,
                    variant: "delete",
                    onClick: () => deleteItemRef.current(itineraryItem),
                  },
                ]}
                triggerClassName="p-0.5 text-white hover:text-white hover:bg-white/20"
                ellipsisSize={12}
                iconSize={12}
                align="start"
              />
            </div>
          )}
        </div>
      );

      if (!isRealEvent) return contentNode;

      return (
        <TooltipProvider delayDuration={300}>
          <Tooltip>
            <TooltipTrigger asChild>{contentNode}</TooltipTrigger>
            <TooltipContent
              side="left"
              align="center"
              className="max-w-[280px] p-3 shadow-lg z-50 flex flex-col gap-1.5 bg-gray-900 border-gray-800"
            >
              <div className="text-[11px] font-mono text-gray-400">
                {eventInfo.timeText}
              </div>
              <div className="font-semibold text-sm leading-tight text-white">
                {itineraryItem?.place?.title || itineraryItem?.note || "Untitled Activity"}
              </div>
              {itineraryItem?.place?.title && itineraryItem?.note && (
                <div className="text-sm font-medium text-gray-300 whitespace-pre-wrap mt-0.5">
                  {itineraryItem.note}
                </div>
              )}
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    };
  }, []);

  const formatLocalDate = (date: Date): string => format(date, "yyyy-MM-dd");

  const findDayByDate = (date: Date): ItineraryDay | undefined => {
    if (!startTime) return undefined;
    const start = new Date(startTime);
    start.setHours(0, 0, 0, 0);
    const target = new Date(date);
    target.setHours(0, 0, 0, 0);
    const diffDays = Math.round(
      (target.getTime() - start.getTime()) / (1000 * 60 * 60 * 24),
    );
    return itineraryDays.find((d) => d.order === diffDays);
  };

  const getDurationString = (start: Date, end: Date) => {
    const diffMs = end.getTime() - start.getTime();
    const totalMinutes = Math.floor(diffMs / 60000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
  };

  const handleEventClick = (info: EventClickArg) => {
    const { itineraryItem, dayIndex, itemIndex } = info.event.extendedProps;
    if (!itineraryItem) return;

    // Ignore clicks on the ActionMenu trigger / dropdown
    const target = info.jsEvent.target as HTMLElement;
    if (target.closest('[data-action="menu"]')) return;

    const item = itineraryItem as ItineraryItem;

    // Single click toggles active state only — edit is in ActionMenu
    if (activeCalendarItemId === item.id) {
      setActiveItem(null);
      clearPlaceSelection();
    } else {
      setActiveItem(item.id);
      selectPlaceFromItinerary(
        item,
        dayIndex as number,
        itemIndex as number,
        "list",
      );
    }
  };

  const handleEventDrop = async (info: EventDropArg) => {
    const { itineraryItem } = info.event.extendedProps;
    if (!itineraryItem) return;

    const newDate = info.event.start;
    if (!newDate) {
      info.revert();
      return;
    }

    const targetDay = findDayByDate(newDate);
    if (!targetDay) {
      info.revert();
      toast.error("Cannot move to this date");
      return;
    }

    const newStartTime = format(newDate, "HH:mm");
    const newDuration = info.event.end
      ? getDurationString(newDate, info.event.end)
      : (itineraryItem as ItineraryItem).duration || "01:00";

    try {
      const response = await updateItineraryItem(
        (itineraryItem as ItineraryItem).id,
        {
          itineraryDayId: targetDay.id,
          startTime: newStartTime,
          duration: newDuration,
          placeId: (itineraryItem as ItineraryItem).place?.placeId ?? null,
          note: (itineraryItem as ItineraryItem).note ?? undefined,
        },
      );
      // saveScrollPosition();
      onUpdateItem(response);
      toast.success("Updated schedule");
    } catch (error) {
      info.revert();
      console.error("Error updating item:", error);
      toast.error("Failed to update schedule");
    }
  };

  const handleEventResize = async (info: EventResizeDoneArg) => {
    const { itineraryItem } = info.event.extendedProps;
    if (!itineraryItem) return;

    const newStart = info.event.start;
    const newEnd = info.event.end;
    if (!newStart || !newEnd) {
      info.revert();
      return;
    }

    const newStartTime = format(newStart, "HH:mm");
    const newDuration = getDurationString(newStart, newEnd);

    try {
      const response = await updateItineraryItem(
        (itineraryItem as ItineraryItem).id,
        {
          itineraryDayId: (itineraryItem as ItineraryItem).itineraryDayId,
          startTime: newStartTime,
          duration: newDuration,
          placeId: (itineraryItem as ItineraryItem).place?.placeId ?? null,
          note: (itineraryItem as ItineraryItem).note ?? undefined,
        },
      );
      // saveScrollPosition();
      onUpdateItem(response);
      toast.success("Updated time");
    } catch (error) {
      info.revert();
      console.error("Error updating item:", error);
      toast.error("Failed to update time");
    }
  };

  const handleDateSelect = (info: DateSelectArg) => {
    const targetDay = findDayByDate(info.start);
    if (!targetDay) return;

    setCalendarAddingDayId(targetDay.id);
    setCalendarAddingTime({
      start: format(info.start, "HH:mm"),
      end: format(info.end, "HH:mm"),
      duration: getDurationString(info.start, info.end),
      startDate: info.start,
      endDate: info.end,
    });
    info.view.calendar.unselect();
  };

  const handleCalendarPlaceSelect = async (
    prediction: google.maps.places.AutocompletePrediction,
  ) => {
    if (!prediction.place_id || !calendarAddingDayId || !calendarAddingTime)
      return;

    try {
      await ensurePlaceExists(prediction.place_id);

      const response = await createItineraryItem(calendarAddingDayId, {
        placeId: prediction.place_id,
        startTime: calendarAddingTime.start,
        duration: calendarAddingTime.duration,
      });
      // saveScrollPosition();

      const dayIndex = itineraryDays.findIndex(
        (d) => d.id === calendarAddingDayId,
      );
      const day = itineraryDays[dayIndex];
      let itemIndex = 0;
      if (day && day.itineraryItems) {
        const tempItems = [...day.itineraryItems, response].sort((a, b) =>
          (a.startTime ?? "").localeCompare(b.startTime ?? ""),
        );
        itemIndex = tempItems.findIndex((i) => i.id === response.id);
      }

      onAddItem(response);
      setActiveItem(response.id);
      selectPlaceFromItinerary(
        response,
        dayIndex !== -1 ? dayIndex : 0,
        itemIndex,
        "list",
      );
      toast.success("Added to itinerary");
    } catch (error) {
      console.error("Error creating itinerary item:", error);
      toast.error("Failed to add item");
    } finally {
      setCalendarAddingDayId(null);
      setCalendarAddingTime(null);
      calendarRef.current?.getApi().unselect();
    }
  };

  // Edit-dialog helpers
  const handleSelectCalendarEditDayId = (itineraryDayId: string) => {
    if (!calendarEditingItem) return;
    setCalendarEditingItem({ ...calendarEditingItem, itineraryDayId });
  };

  const handleSelectCalendarStartTime = (date: Date | undefined) => {
    if (!calendarEditingItem) return;
    setCalendarEditingItem({
      ...calendarEditingItem,
      startTime: date ? format(date, "HH:mm") : "",
    });
  };

  const handleSelectCalendarDuration = (duration: string) => {
    if (!calendarEditingItem) return;
    setCalendarEditingItem({
      ...calendarEditingItem,
      duration: duration,
    });
  };

  const convertTimeOnlyStringToDate = (time?: string): Date | undefined => {
    if (!time) return undefined;
    const [hours, minutes] = time.split(":");
    const d = new Date();
    d.setHours(Number.parseInt(hours), Number.parseInt(minutes), 0, 0);
    return d;
  };

  const handleConfirmCalendarEditItem = async () => {
    if (!calendarEditingItem) return;
    try {
      const response = await updateItineraryItem(calendarEditingItem.id, {
        itineraryDayId: calendarEditingItem.itineraryDayId,
        startTime: calendarEditingItem.startTime,
        duration: calendarEditingItem.duration,
        note: calendarEditedNote || undefined,
        placeId: calendarEditedPlaceId,
      });
      // saveScrollPosition();
      onUpdateItem(response);
      toast.success("Updated item");
      setCalendarEditingItem(null);
      setCalendarEditedPlaceId(null);
      setCalendarEditedPlaceName("");
      setCalendarEditedNote("");
    } catch (error) {
      console.error("Error updating item:", error);
      toast.error("Failed to update item");
    }
  };

  const handleConfirmCalendarDeleteItem = async () => {
    if (!calendarDeletingItem) return;
    try {
      await deleteItineraryItem(calendarDeletingItem.id);
      // saveScrollPosition();
      onDeleteItem(
        calendarDeletingItem.id,
        calendarDeletingItem.itineraryDayId,
      );
      clearPlaceSelection();
      toast.success("Item deleted");
      setCalendarDeletingItem(null);
    } catch (error) {
      console.error("Error deleting item:", error);
      toast.error("Failed to delete item");
    }
  };

  // Computed
  const tripDayCount = itineraryDays.length || 1;

  // Calculate initial scroll time once per trip schedule mount (to first event - 1 hour)
  const initialScrollTime = useMemo(() => {
    let scrollTime = "06:00:00";
    const firstDayWithEvents = itineraryDays.find(
      (day) => day.itineraryItems && day.itineraryItems.length > 0,
    );
    if (firstDayWithEvents) {
      const sortedItems = [...(firstDayWithEvents.itineraryItems || [])].sort(
        (a, b) => (a.startTime ?? "").localeCompare(b.startTime ?? ""),
      );
      const firstItem = sortedItems[0];
      if (firstItem?.startTime) {
        const [hours, minutes] = firstItem.startTime.split(":");
        const hourBefore = Math.max(0, parseInt(hours) - 1);
        scrollTime = `${String(hourBefore).padStart(2, "0")}:${minutes}:00`;
      }
    }
    return scrollTime;
  }, [itineraryDays]);

  const calendarEvents = useMemo(() => {
    const allEvents: EventInput[] = itineraryDays.flatMap((day, dayIndex) => {
      const dayDate = new Date(startTime || new Date());
      dayDate.setDate(dayDate.getDate() + day.order);
      const dayColor = getDayColor(dayIndex);

      const sortedItems = [...(day.itineraryItems || [])].sort((a, b) =>
        (a.startTime ?? "").localeCompare(b.startTime ?? ""),
      );

      return sortedItems.map((item, itemIndex) => {
        let start = new Date(dayDate);
        if (item.startTime) {
          const [h, m] = item.startTime.split(":").map(Number);
          start.setHours(h, m, 0, 0);
        } else {
          start.setHours(9, 0, 0, 0); // Default start
        }

        let end = new Date(start);
        if (item.duration) {
          const [h, m] = item.duration.split(":").map(Number);
          end.setHours(end.getHours() + h);
          end.setMinutes(end.getMinutes() + m);
        } else {
          end.setHours(end.getHours() + 1); // Default duration 1 hour
        }

        return {
          id: item.id,
          title: item.place?.title || item.note || "Untitled Activity",
          start: start,
          end: end,
          backgroundColor: dayColor,
          borderColor: dayColor,
          textColor: "#ffffff",
          extendedProps: {
            itineraryItem: item,
            dayIndex,
            itemIndex,
            place: item.place,
          },
        };
      });
    });

    // Inject "Draft" event if adding
    if (calendarAddingDayId && calendarAddingTime) {
      const day = itineraryDays.find((d) => d.id === calendarAddingDayId);
      if (day && startTime) {
        const dayDate = new Date(startTime);
        dayDate.setDate(dayDate.getDate() + day.order);
        const dateStr = formatLocalDate(dayDate);
        // Find day index
        const dayIndex = itineraryDays.findIndex(
          (d) => d.id === calendarAddingDayId,
        );
        const dayColor = getDayColor(dayIndex !== -1 ? dayIndex : 0);

        // Ensure draft-event end date reflects cross-day correctly
        const draftStart = new Date(dayDate);
        const [sH, sM] = calendarAddingTime.start.split(":").map(Number);
        draftStart.setHours(sH, sM, 0, 0);

        const draftEnd = new Date(draftStart);
        const [dH, dM] = calendarAddingTime.duration.split(":").map(Number);
        draftEnd.setHours(draftEnd.getHours() + dH, draftEnd.getMinutes() + dM);

        allEvents.push({
          id: "draft-event",
          title: "New Item...",
          start: draftStart,
          end: draftEnd,
          backgroundColor: dayColor,
          borderColor: dayColor,
          textColor: "#ffffff",
          classNames: ["fc-event-active"],
          extendedProps: {
            itineraryItem: {} as ItineraryItem,
            dayIndex,
            itemIndex: -1,
            place: null as any,
            isDraft: true,
          } as any,
        });
      }
    }

    return allEvents;
  }, [
    itineraryDays,
    startTime,
    activeCalendarItemId,
    calendarAddingDayId,
    calendarAddingTime,
  ]);

  const calendarValidRange = useMemo(() => {
    if (!startTime || !endTime) return undefined;
    const start = new Date(startTime);
    start.setDate(start.getDate() - 7);
    const end = new Date(endTime);
    end.setDate(end.getDate() + 8);
    return { start, end };
  }, [startTime, endTime]);

  // Highlight itinerary days, dim out-of-range days
  const getDayCellClassNames = useCallback(
    (arg: { date: Date }) => {
      if (!startTime || !endTime) return [];
      const cell = new Date(arg.date);
      cell.setHours(0, 0, 0, 0);
      const s = new Date(startTime);
      s.setHours(0, 0, 0, 0);
      const e = new Date(endTime);
      e.setHours(0, 0, 0, 0);

      // Out of range
      if (cell < s || cell > e) {
        return ["fc-day-out-of-range"];
      }

      // Within itinerary range - highlight
      const diffTime = cell.getTime() - s.getTime();
      const diffDays = Math.round(diffTime / (1000 * 60 * 60 * 24));
      return ["fc-day-in-range", `day-col-${diffDays}`];
    },
    [startTime, endTime],
  );

  // Highlight the active event card
  const getEventClassNames = useCallback(
    (arg: { event: { id: string } }) =>
      arg.event.id === activeCalendarItemId ? ["fc-event-active"] : [],
    [activeCalendarItemId],
  );

  // Custom navigation handlers for single-day movement
  const handlePrev = useCallback(() => {
    const calendarApi = calendarRef.current?.getApi();
    if (calendarApi) {
      const currentDate = calendarApi.getDate();
      currentDate.setDate(currentDate.getDate() - 1);
      calendarApi.gotoDate(currentDate);
    }
  }, []);

  const handleNext = useCallback(() => {
    const calendarApi = calendarRef.current?.getApi();
    if (calendarApi) {
      const currentDate = calendarApi.getDate();
      currentDate.setDate(currentDate.getDate() + 1);
      calendarApi.gotoDate(currentDate);
    }
  }, []);

  const handleToday = useCallback(() => {
    const calendarApi = calendarRef.current?.getApi();
    if (calendarApi) {
      calendarApi.today();
    }
  }, []);

  const headerToolbar = useMemo(
    () => ({
      left: "customPrev,customNext customToday",
      center: "title",
      right: "timeGridWeek,timeGridDay",
    }),
    [],
  );

  const buttonText = useMemo(
    () => ({
      timeGridWeek: "Week",
      timeGridDay: "Day",
    }),
    [],
  );

  const customButtons = useMemo(
    () => ({
      customPrev: { text: "‹", click: handlePrev },
      customNext: { text: "›", click: handleNext },
      customToday: { text: "Today", click: handleToday },
    }),
    [handlePrev, handleNext, handleToday],
  );

  const calendarViews = useMemo(
    () => ({
      timeGridWeek: {
        duration: { days: Math.min(7, tripDayCount) },
      },
    }),
    [tripDayCount],
  );

  const timeFormat = useMemo(
    () =>
      ({
        hour: "numeric",
        minute: "2-digit",
        hour12: false,
      }) as const,
    [],
  );

  // Render
  return (
    <>
      {/* Dynamic styles for drag-selection highlight colors */}
      <style jsx global>{`
        ${itineraryDays
          .map(
            (day) => `
          .day-col-${day.order} .fc-highlight {
            background-color: ${getDayColor(day.order)} !important;
            border: 2px solid ${getDayColor(day.order)} !important;
          }
          .day-col-${day.order} .fc-event-mirror {
            background-color: ${getDayColor(day.order)} !important;
            border-color: ${getDayColor(day.order)} !important;
          }
        `,
          )
          .join("")}
      `}</style>
      <div className="fullcalendar-custom h-[calc(100vh-12rem)] overflow-hidden">
        <FullCalendar
          key={tripDayCount} // remount when trip-day count changes
          ref={calendarRef}
          plugins={[timeGridPlugin, dayGridPlugin, interactionPlugin]}
          initialView="timeGridWeek"
          headerToolbar={headerToolbar}
          buttonText={buttonText}
          customButtons={customButtons}
          views={calendarViews}
          slotLabelFormat={timeFormat}
          eventTimeFormat={timeFormat}
          events={calendarEvents}
          height="100%"
          slotMinTime="00:00:00"
          slotMaxTime="24:00:00"
          slotDuration="00:30:00"
          slotLabelInterval="01:00:00"
          scrollTime={initialScrollTime}
          allDaySlot={false}
          nowIndicator={true}
          initialDate={startTime || new Date()}
          validRange={calendarValidRange}
          // Interactions
          editable={true}
          selectable={true}
          selectMirror={true}
          eventDurationEditable={true}
          eventStartEditable={true}
          eventResizableFromStart={true}
          snapDuration="00:15:00"
          // Handlers
          eventClick={handleEventClick}
          eventDrop={handleEventDrop}
          eventResize={handleEventResize}
          select={handleDateSelect}
          // Custom rendering
          eventContent={renderEventContent}
          eventClassNames={getEventClassNames}
          dayCellClassNames={getDayCellClassNames}
          stickyHeaderDates={true}
        />

        {/* Add Place Dialog */}
        {calendarAddingDayId && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30">
            <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-800">
                  Add Place
                  {calendarAddingDayId && startTime && calendarAddingTime && (
                    <span className="text-sm font-normal text-gray-500 ml-2">
                      {(() => {
                        const startD = calendarAddingTime.startDate;
                        const endD = calendarAddingTime.endDate;
                        // Check if they are on different dates
                        const isCrossDay =
                          startD.getDate() !== endD.getDate() ||
                          startD.getMonth() !== endD.getMonth() ||
                          startD.getFullYear() !== endD.getFullYear();

                        if (isCrossDay) {
                          return `${format(startD, "EEE d/M HH:mm")} - ${format(endD, "EEE d/M HH:mm")}`;
                        }
                        return `${format(startD, "EEE d/M")} ${calendarAddingTime.start} - ${calendarAddingTime.end}`;
                      })()}
                    </span>
                  )}
                </h3>
                <button
                  onClick={() => {
                    setCalendarAddingDayId(null);
                    setCalendarAddingTime(null);
                    calendarRef.current?.getApi().unselect();
                  }}
                  className="text-gray-400 hover:text-gray-600 transition-colors text-lg"
                >
                  ✕
                </button>
              </div>
              <PlaceAutocomplete
                onPlaceSelect={handleCalendarPlaceSelect}
                onClose={() => {
                  setCalendarAddingDayId(null);
                  setCalendarAddingTime(null);
                  calendarRef.current?.getApi().unselect();
                }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Edit Item Dialog */}
      {calendarEditingItem && (
        <CustomDialog
          open={!!calendarEditingItem}
          onOpenChange={(open) => {
            if (!open) {
              setCalendarEditingItem(null);
              setCalendarEditedPlaceId(null);
              setCalendarEditedPlaceName("");
              setCalendarEditedNote("");
            }
          }}
          title="Edit Item"
          confirmLabel="Confirm"
          onConfirm={handleConfirmCalendarEditItem}
        >
          <ItineraryItemEditor
            selectedDayId={calendarEditingItem.itineraryDayId}
            setSelectedDayId={handleSelectCalendarEditDayId}
            itineraryDays={itineraryDays}
            planStartTime={startTime || new Date()}
            startTime={convertTimeOnlyStringToDate(
              calendarEditingItem.startTime,
            )}
            duration={calendarEditingItem.duration || ""}
            setStartTime={handleSelectCalendarStartTime}
            setDuration={handleSelectCalendarDuration}
            note={calendarEditedNote}
            setNote={setCalendarEditedNote}
            placeId={calendarEditedPlaceId}
            setPlaceId={setCalendarEditedPlaceId}
            placeName={calendarEditedPlaceName}
            setPlaceName={setCalendarEditedPlaceName}
          />
        </CustomDialog>
      )}

      {/* Delete Item Confirmation */}
      <ConfirmDeleteModal
        open={!!calendarDeletingItem}
        onOpenChange={(open) => !open && setCalendarDeletingItem(null)}
        title="Delete Itinerary Item"
        description={`Are you sure you want to delete "${calendarDeletingItem?.place?.title || "this item"}"? This action cannot be undone.`}
        onConfirm={handleConfirmCalendarDeleteItem}
      />
    </>
  );
}
