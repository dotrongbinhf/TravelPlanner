import API from "@/utils/api";
import { CreateItineraryItemRequest, UpdateItineraryItemRequest } from "./type";
import { ItineraryItem } from "@/types/itineraryItem";

const APP_CONFIG_URL = "/api/itineraryItem";

export const createItineraryItem = async (
  itineraryDayId: string,
  data: CreateItineraryItemRequest,
) => {
  const response = await API.post<ItineraryItem>(
    `${APP_CONFIG_URL}?itineraryDayId=${itineraryDayId}`,
    data,
  );
  return response.data;
};

export const updateItineraryItem = async (
  itineraryItemId: string,
  data: UpdateItineraryItemRequest,
) => {
  const response = await API.patch<ItineraryItem>(
    `${APP_CONFIG_URL}/${itineraryItemId}`,
    data,
  );
  return response.data;
};

export const deleteItineraryItem = async (itineraryItemId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${itineraryItemId}`);
  return response.data;
};
