export type CreateItineraryItemRequest = {
  placeId?: string;
  startTime?: string;
  duration?: string;
  note?: string;
};

export type UpdateItineraryItemRequest = {
  itineraryDayId: string;
  placeId?: string | null;
  startTime?: string;
  duration?: string;
  note?: string | null;
};
