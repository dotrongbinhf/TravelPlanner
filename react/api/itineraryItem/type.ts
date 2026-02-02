export type CreateItineraryItemRequest = {
  placeId: string;
  startTime: string;
  endTime: string;
};

export type UpdateItineraryItemRequest = {
  itineraryDayId: string;
  startTime: string;
  endTime: string;
};
