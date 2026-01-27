import { Plan } from "@/types/plan";
import API from "@/utils/api";
import { CreatePlanRequest } from "./types";
import { PaginatedResult } from "@/types/paginated";

const APP_CONFIG_URL = "/api/plan";

export const getAllPlans = async () => {
  const response = await API.get<Plan[]>(`${APP_CONFIG_URL}`);
  return response.data;
};

export const getPlanById = async (planId: string) => {
  const response = await API.get<Plan>(`${APP_CONFIG_URL}/${planId}`);
  return response.data;
};

export const createPlan = async (data: CreatePlanRequest) => {
  const response = await API.post<any>(`${APP_CONFIG_URL}`, data);
  return response.data;
};

export const updatePlanBasicInfo = async (
  planId: string,
  data: Partial<CreatePlanRequest>,
) => {
  const response = await API.patch<Plan>(`${APP_CONFIG_URL}/${planId}`, data);
  return response.data;
};

export const updatePlanCoverImage = async (planId: string, image: File) => {
  const formData = new FormData();
  formData.append("coverImage", image);
  const response = await API.patch<{ coverImageUrl: string }>(
    `${APP_CONFIG_URL}/${planId}/cover-image`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return response.data;
};

export const getMyPlans = async (page: number = 1, pageSize: number = 10) => {
  const response = await API.get<PaginatedResult<Plan>>(
    `${APP_CONFIG_URL}/mine`,
    { params: { page, pageSize } },
  );
  return response.data;
};

export const getSharedPlans = async (
  page: number = 1,
  pageSize: number = 10,
) => {
  const response = await API.get<PaginatedResult<Plan>>(
    `${APP_CONFIG_URL}/shared`,
    { params: { page, pageSize } },
  );
  return response.data;
};

export const getPendingInvitations = async (
  page: number = 1,
  pageSize: number = 10,
) => {
  const response = await API.get<PaginatedResult<Plan>>(
    `${APP_CONFIG_URL}/pending`,
    { params: { page, pageSize } },
  );
  return response.data;
};

export const deletePlan = async (planId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${planId}`);
  return response.data;
};
