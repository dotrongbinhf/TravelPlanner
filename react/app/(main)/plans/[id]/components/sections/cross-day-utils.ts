import { ItineraryItem } from "@/types/itineraryItem";
import { ItineraryDay } from "@/types/itineraryDay";

export type DisplayType = "normal" | "cross-day-start" | "cross-day-end";

export interface DisplayItem {
  item: ItineraryItem;
  displayType: DisplayType;
  displayStartTime: string;
  displayEndTime: string;
  sourceDayIndex: number;
  isOverallLast: boolean;
  isOverallFirst: boolean;
  isBed: boolean;
  orderNumber: number;
}

const MOON = "🌙";

export function isCrossDayEvent(
  startTime?: string,
  duration?: string,
): boolean {
  if (!startTime || !duration) return false;
  const [sH, sM] = startTime.split(":").map(Number);
  const [dH, dM] = duration.split(":").map(Number);
  const totalMinutes = sH * 60 + sM + dH * 60 + dM;
  return totalMinutes >= 24 * 60;
}

function calcEndTime(startTime: string, duration: string): string {
  const [sH, sM] = startTime.split(":").map(Number);
  const [dH, dM] = duration.split(":").map(Number);
  const totalMinutes = sH * 60 + sM + dH * 60 + dM;
  const endH = Math.floor(totalMinutes / 60) % 24;
  const endM = totalMinutes % 60;
  return `${String(endH).padStart(2, "0")}:${String(endM).padStart(2, "0")}`;
}

export function buildDisplayItems(
  sortedDays: ItineraryDay[],
  dayIndex: number,
  totalDays: number,
): DisplayItem[] {
  const day = sortedDays[dayIndex];
  if (!day) return [];

  const isLastDay = dayIndex === totalDays - 1;
  const isFirstDay = dayIndex === 0;

  // Sort items by start time
  const sortedItems = [...(day.itineraryItems || [])].sort((a, b) =>
    (a.startTime ?? "").localeCompare(b.startTime ?? ""),
  );

  const displayItems: DisplayItem[] = [];

  // 1. Check previous day for cross-day items → inject cross-day-end at the top
  if (dayIndex > 0) {
    const prevDay = sortedDays[dayIndex - 1];
    const prevSortedItems = [...(prevDay.itineraryItems || [])].sort((a, b) =>
      (a.startTime ?? "").localeCompare(b.startTime ?? ""),
    );

    prevSortedItems.forEach((item) => {
      if (isCrossDayEvent(item.startTime, item.duration)) {
        const endTime = calcEndTime(item.startTime!, item.duration!);
        displayItems.push({
          item,
          displayType: "cross-day-end",
          displayStartTime: MOON,
          displayEndTime: endTime,
          sourceDayIndex: dayIndex - 1,
          isOverallFirst: false,
          isOverallLast: false,
          isBed: true, // cross-day-end keeps bed icon from previous day
          orderNumber: 0, // will be recalculated
        });
      }
    });
  }

  // 2. Add this day's items
  sortedItems.forEach((item, index) => {
    const crossDay = isCrossDayEvent(item.startTime, item.duration);
    const isLastInDay = index === sortedItems.length - 1;
    const isFirstInDay = index === 0 && displayItems.length === 0; // no cross-day-end items above

    if (crossDay) {
      // This item crosses midnight → show as cross-day-start
      displayItems.push({
        item,
        displayType: "cross-day-start",
        displayStartTime: item.startTime || "",
        displayEndTime: MOON,
        sourceDayIndex: dayIndex,
        isOverallFirst: isFirstDay && isFirstInDay,
        isOverallLast: false, // a cross-day-start is never the overall last
        isBed: isLastInDay && !isLastDay, // last in day, cross-day, and not last day → bed
        orderNumber: 0,
      });
    } else {
      // Normal item
      const endTime =
        item.startTime && item.duration
          ? calcEndTime(item.startTime, item.duration)
          : undefined;
      displayItems.push({
        item,
        displayType: "normal",
        displayStartTime: item.startTime || "",
        displayEndTime: endTime || "",
        sourceDayIndex: dayIndex,
        isOverallFirst: isFirstDay && isFirstInDay,
        isOverallLast: isLastDay && isLastInDay,
        isBed: false, // normal items are never bed markers
        orderNumber: 0,
      });
    }
  });

  // 3. Recalculate order numbers (skip cross-day-end ghost items)
  let orderCounter = 0;
  displayItems.forEach((di) => {
    if (di.displayType === "cross-day-end") {
      di.orderNumber = 0; // ghost items don't get a number
    } else {
      orderCounter++;
      di.orderNumber = orderCounter;
    }
  });

  // 4. Re-evaluate isOverallFirst for the actual first item
  //    (cross-day-end items from previous day should not be "overall first")
  if (displayItems.length > 0 && isFirstDay) {
    // Only the very first display item of day 0 can be overall first,
    // and only if it's not a cross-day-end
    displayItems.forEach((di) => {
      di.isOverallFirst = false;
    });
    const firstNonCrossDayEnd = displayItems.find(
      (di) => di.displayType !== "cross-day-end",
    );
    if (firstNonCrossDayEnd) {
      firstNonCrossDayEnd.isOverallFirst = true;
    }
  }

  return displayItems;
}
