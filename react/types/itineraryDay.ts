import { ItineraryItem } from "./itineraryItem";

export type ItineraryDay = {
  id: string;
  planId: string;
  order: number;
  title: string;
  itineraryItems: ItineraryItem[];
};
