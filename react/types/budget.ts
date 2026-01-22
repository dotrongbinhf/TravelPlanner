export interface Expense {
  id: string;
  name: string;
  amount: number;
  category: ExpenseCategory;
}

export type ExpenseCategory =
  | "food"
  | "transport"
  | "accommodation"
  | "activities"
  | "shopping"
  | "other";

export interface Budget {
  totalBudget: number;
  expenses: Expense[];
}

export const EXPENSE_CATEGORIES: {
  value: ExpenseCategory;
  label: string;
  color: string;
}[] = [
  { value: "food", label: "Food & Drinks", color: "#FF6384" },
  { value: "transport", label: "Transport", color: "#36A2EB" },
  { value: "accommodation", label: "Accommodation", color: "#FFCE56" },
  { value: "activities", label: "Activities", color: "#4BC0C0" },
  { value: "shopping", label: "Shopping", color: "#9966FF" },
  { value: "other", label: "Other", color: "#FF9F40" },
];
