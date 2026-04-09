import { Place } from "@/types/place";

export type ItineraryItem = {
  id: string;
  itineraryDayId: string;
  place?: Place | null;
  startTime?: string; // TimeOnly HH:mm (optional)
  duration?: string; // TimeOnly HH:mm (optional)
  note?: string | null; // AI-generated or user note
  googleCalendarEventId?: string;
};
