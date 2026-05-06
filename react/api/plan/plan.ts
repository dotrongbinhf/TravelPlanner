import { Plan } from "@/types/plan";
import API from "@/utils/api";
import { CreatePlanRequest } from "./types";
import { PaginatedResult } from "@/types/paginated";

const APP_CONFIG_URL = "/api/plan";

export interface PlanQueryParams {
  page?: number;
  pageSize?: number;
  search?: string;
  dateFrom?: string; // ISO date string
  dateTo?: string;
  status?: "upcoming" | "past";
  sortBy?: "startTime" | "createdAt" | "name";
  sortOrder?: "asc" | "desc";
}

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

export const getMyPlans = async (params: PlanQueryParams = {}) => {
  const response = await API.get<PaginatedResult<Plan>>(
    `${APP_CONFIG_URL}/mine`,
    { params },
  );
  return response.data;
};

export const getSharedPlans = async (params: PlanQueryParams = {}) => {
  const response = await API.get<PaginatedResult<Plan>>(
    `${APP_CONFIG_URL}/shared`,
    { params },
  );
  return response.data;
};

export const getPendingInvitations = async (params: PlanQueryParams = {}) => {
  const response = await API.get<PaginatedResult<Plan>>(
    `${APP_CONFIG_URL}/pending`,
    { params },
  );
  return response.data;
};

export const deletePlan = async (planId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${planId}`);
  return response.data;
};

export const applyAIPlan = async (planId: string, applyData: Record<string, unknown>) => {
  const response = await API.post<Plan>(`${APP_CONFIG_URL}/${planId}/apply-ai`, applyData);
  return response.data;
};

export const clonePlan = async (planId: string, name?: string) => {
  const response = await API.post<{ id: string; name: string }>(
    `${APP_CONFIG_URL}/${planId}/clone`,
    { name },
  );
  return response.data;
};
