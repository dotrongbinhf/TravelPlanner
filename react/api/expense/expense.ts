import { ExpenseItem } from "@/types/budget";
import API from "@/utils/api";
import { CreateExpenseRequest, UpdateExpenseRequest } from "./types";

const APP_CONFIG_URL = "/api/expenseItem";

export const createExpenseItem = async (
  planId: string,
  data: CreateExpenseRequest,
) => {
  const response = await API.post<ExpenseItem>(
    `${APP_CONFIG_URL}?planId=${planId}`,
    data,
  );
  return response.data;
};

export const updateExpenseItem = async (
  expenseItemId: string,
  data: UpdateExpenseRequest,
) => {
  const response = await API.patch<ExpenseItem>(
    `${APP_CONFIG_URL}/${expenseItemId}`,
    data,
  );
  return response.data;
};

export const deleteExpenseItem = async (expenseItemId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${expenseItemId}`);
  return response.data;
};
