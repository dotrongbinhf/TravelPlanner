export type ItineraryItem = {
  id: string;
  planId: string;
  placeId: string;
  date: Date;
  order: number;
  startTime: Date;
  endTime: Date;
  note?: string;
};
