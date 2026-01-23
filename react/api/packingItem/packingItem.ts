import { PackingItem } from "@/types/packingItem";
import API from "@/utils/api";
import { CreatePackingItemRequest, UpdatePackingItemRequest } from "./types";

const APP_CONFIG_URL = "/api/packingItem";

export const createPackingItem = async (
  packingListId: string,
  data: CreatePackingItemRequest,
) => {
  const response = await API.post<PackingItem>(
    `${APP_CONFIG_URL}?packingListId=${packingListId}`,
    data,
  );
  return response.data;
};

export const updatePackingItem = async (
  packingItemId: string,
  data: UpdatePackingItemRequest,
) => {
  const response = await API.patch<PackingItem>(
    `${APP_CONFIG_URL}/${packingItemId}`,
    data,
  );
  return response.data;
};

export const deletePackingItem = async (packingItemId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${packingItemId}`);
  return response.data;
};
