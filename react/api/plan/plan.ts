import { CreatePlanRequest, Plan } from "@/types/plan";
import API from "@/utils/api";

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
