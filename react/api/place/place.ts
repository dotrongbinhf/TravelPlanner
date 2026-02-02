import { Place } from "@/types/place";
import API from "@/utils/api";

const APP_CONFIG_URL = "/api/place";

export const getPlaceByPlaceId = async (placeId: string) => {
  const response = await API.get<Place>(`${APP_CONFIG_URL}/${placeId}`);
  return response.data;
};
