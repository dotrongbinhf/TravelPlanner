import { Place } from "@/types/place";

export type ItineraryItem = {
  id: string;
  itineraryDayId: string;
  place: Place;
  startTime: string; // TimeOnly HH:mm
  endTime: string; // TimeOnly
};
