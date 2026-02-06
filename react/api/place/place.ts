import { Place } from "@/types/place";
import API from "@/utils/api";

const APP_CONFIG_URL = "/api/place";

export const getPlaceByPlaceId = async (placeId: string) => {
  const response = await API.get<Place>(`${APP_CONFIG_URL}/${placeId}`);
  return response.data;
};

// Add Place - Fallback
export const createPlace = async (place: Partial<Place>) => {
  const response = await API.post<Place>(`${APP_CONFIG_URL}`, place);
  return response.data;
};
