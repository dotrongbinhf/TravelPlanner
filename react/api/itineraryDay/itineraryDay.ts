import { ItineraryDay } from "@/types/itineraryDay";
import API from "@/utils/api";

const APP_CONFIG_URL = "/api/itineraryDay";

export const updateItineraryDay = async (
  dayId: string,
  data: Partial<ItineraryDay>,
) => {
  const response = await API.patch<ItineraryDay>(
    `${APP_CONFIG_URL}/${dayId}`,
    data,
  );
  return response.data;
};

export const deleteItineraryDay = async (dayId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${dayId}`);
  return response.data;
};
