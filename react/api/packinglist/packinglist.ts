import API from "@/utils/api";
import { CreatePackingListRequest, UpdatePackingListRequest } from "./types";
import { PackingList } from "@/types/packingList";

const APP_CONFIG_URL = "/api/packinglist";

export const createPackingList = async (
  planId: string,
  data: CreatePackingListRequest,
) => {
  const response = await API.post<PackingList>(
    `${APP_CONFIG_URL}?planId=${planId}`,
    data,
  );
  return response.data;
};

export const updatePackingList = async (
  packingListId: string,
  data: UpdatePackingListRequest,
) => {
  const response = await API.patch<PackingList>(
    `${APP_CONFIG_URL}/${packingListId}`,
    data,
  );
  return response.data;
};

export const deletePackingList = async (packingListId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${packingListId}`);
  return response.data;
};
