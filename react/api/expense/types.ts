import { ExpenseCategory } from "@/types/budget";

export type CreateExpenseRequest = {
  name: string;
  amount: number;
  category: ExpenseCategory;
};

export type UpdateExpenseRequest = {
  name: string;
  amount: number;
  category: ExpenseCategory;
};
