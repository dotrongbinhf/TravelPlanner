import API from "@/utils/api";
import { CreateItineraryItemRequest, UpdateItineraryItemRequest } from "./type";
import { ItineraryItem } from "@/types/itineraryItem";

const APP_CONFIG_URL = "/api/itineraryItem";

const convertHHmmToTimeSpan = (time?: string) => {
  if (!time) return undefined;
  if (time.length === 5) return `${time}:00`;
  return time;
};

export const createItineraryItem = async (
  itineraryDayId: string,
  data: CreateItineraryItemRequest,
) => {
  const payload = {
    placeId: data.placeId,
    startTime: data.startTime,
    duration: convertHHmmToTimeSpan(data.duration),
  } as CreateItineraryItemRequest;
  const response = await API.post<ItineraryItem>(
    `${APP_CONFIG_URL}?itineraryDayId=${itineraryDayId}`,
    payload,
  );
  return response.data;
};

export const updateItineraryItem = async (
  itineraryItemId: string,
  data: UpdateItineraryItemRequest,
) => {
  const payload = {
    itineraryDayId: data.itineraryDayId,
    startTime: data.startTime,
    duration: convertHHmmToTimeSpan(data.duration),
  } as UpdateItineraryItemRequest;
  const response = await API.patch<ItineraryItem>(
    `${APP_CONFIG_URL}/${itineraryItemId}`,
    payload,
  );
  return response.data;
};

export const deleteItineraryItem = async (itineraryItemId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${itineraryItemId}`);
  return response.data;
};
