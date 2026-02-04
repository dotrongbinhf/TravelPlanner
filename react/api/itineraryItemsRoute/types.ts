export type UpdateRouteWaypointInput = {
  lat: number;
  lng: number;
  order: number;
};

export type UpdateItineraryItemsRouteRequest = {
  startItineraryItemId: string;
  endItineraryItemId: string;
  waypoints: UpdateRouteWaypointInput[];
};
