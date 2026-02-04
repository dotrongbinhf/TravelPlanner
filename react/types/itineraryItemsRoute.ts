export type RouteWaypoint = {
  id: string;
  lat: number;
  lng: number;
  order: number;
};

export type ItineraryItemsRoute = {
  id: string;
  startItineraryItemId: string;
  endItineraryItemId: string;
  waypoints: RouteWaypoint[];
};
