export enum ExpenseCategory {
  FOOD = 0,
  TRANSPORT = 1,
  ACCOMMODATION = 2,
  ACTIVITIES = 3,
  SHOPPING = 4,
  OTHER = 5,
}

export type ExpenseItem = {
  id: string;
  category: ExpenseCategory;
  name: string;
  amount: number;
};

export type Budget = {
  totalBudget: number;
  expenseItems: ExpenseItem[];
};

export const EXPENSE_CATEGORIES: {
  value: ExpenseCategory;
  label: string;
  color: string;
}[] = [
  { value: ExpenseCategory.FOOD, label: "Food & Drinks", color: "#FF6384" },
  { value: ExpenseCategory.TRANSPORT, label: "Transport", color: "#36A2EB" },
  {
    value: ExpenseCategory.ACCOMMODATION,
    label: "Accommodation",
    color: "#FFCE56",
  },
  { value: ExpenseCategory.ACTIVITIES, label: "Activities", color: "#4BC0C0" },
  { value: ExpenseCategory.SHOPPING, label: "Shopping", color: "#9966FF" },
  { value: ExpenseCategory.OTHER, label: "Other", color: "#FF9F40" },
];
