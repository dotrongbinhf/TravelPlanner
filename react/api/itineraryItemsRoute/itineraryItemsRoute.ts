import API from "@/utils/api";
import {
  ItineraryItemsRoute,
  RouteWaypoint,
} from "@/types/itineraryItemsRoute";
import { UpdateItineraryItemsRouteRequest } from "./types";

const APP_CONFIG_URL = "/api/itineraryItemsRoute";

/**
 * Get all routes for items in a specific itinerary day
 */
export const getRoutesByDayId = async (dayId: string) => {
  const response = await API.get<ItineraryItemsRoute[]>(
    `${APP_CONFIG_URL}/day/${dayId}`,
  );
  return response.data;
};

/**
 * Get route for specific start and end itinerary items
 */
export const getRouteBetweenTwoItems = async (
  startItineraryItemId: string,
  endItineraryItemId: string,
) => {
  const response = await API.get<ItineraryItemsRoute>(
    `${APP_CONFIG_URL}/between/${startItineraryItemId}/${endItineraryItemId}`,
  );
  return response.data;
};

/**
 * Upsert route with waypoints (create or update based on start+end item IDs)
 */
export const upsertRoute = async (data: UpdateItineraryItemsRouteRequest) => {
  const response = await API.put<ItineraryItemsRoute>(APP_CONFIG_URL, data);
  return response.data;
};

/**
 * Delete a route by its ID
 */
export const deleteRoute = async (routeId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${routeId}`);
  return response.data;
};
