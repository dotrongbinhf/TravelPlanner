export type CreateItineraryItemRequest = {
  placeId: string;
  startTime?: string;
  duration?: string;
};

export type UpdateItineraryItemRequest = {
  itineraryDayId: string;
  startTime?: string;
  duration?: string;
};
