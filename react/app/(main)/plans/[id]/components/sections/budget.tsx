"use client";

import { cn } from "@/lib/utils";
import {
  ExpenseItem,
  ExpenseCategory,
  EXPENSE_CATEGORIES,
} from "@/types/budget";
import {
  Plus,
  DollarSign,
  Pencil,
  TrendingDown,
  Wallet,
  Check,
  X,
  Trash2,
} from "lucide-react";
import {
  Dispatch,
  forwardRef,
  SetStateAction,
  useEffect,
  useRef,
  useState,
  useMemo,
} from "react";
import {
  getLocaleFromCurrencyCode,
  getSymbolFromCurrencyCode,
} from "@/utils/curency";
import ExpenseCard from "./expense-card";
import ExpensePieChart from "./expense-pie-chart";
import { ExpenseChart } from "./chart-pie-simple";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import {
  createExpenseItem,
  updateExpenseItem,
  deleteExpenseItem,
} from "@/api/expense/expense";
import { updatePlanBasicInfo } from "@/api/plan/plan";
import { CurrencyInput } from "@/components/currency-input";
import { CustomDialog } from "@/components/custom-dialog";
import { Plan } from "@/types/plan";
import toast from "react-hot-toast";
import { AxiosError } from "axios";
import { ConfirmDeleteModal } from "@/components/confirm-delete-modal";

interface BudgetProps {
  className?: string;
  planId: string;
  totalBudget: number;
  currencyCode: string;
  expenseItems: ExpenseItem[];
  updateExpenseItems: (expenseItems: ExpenseItem[]) => void;
  updateBudgetAndCurrencyCode: (budget: number, currencyCode: string) => void;
}

const Budget = forwardRef<HTMLDivElement, BudgetProps>(function Budget(
  {
    className,
    planId,
    totalBudget,
    currencyCode,
    expenseItems,
    updateExpenseItems,
    updateBudgetAndCurrencyCode,
  },
  ref,
) {
  const currencySymbol = getSymbolFromCurrencyCode(currencyCode);
  const currencyLocale = getLocaleFromCurrencyCode(currencyCode);
  const [isEditingBudget, setIsEditingBudget] = useState(false);
  const [editBudgetValue, setEditBudgetValue] = useState("");
  const [editCurrency, setEditCurrency] = useState(currencyCode);
  const budgetInputRef = useRef<HTMLInputElement>(null);
  const budgetContainerRef = useRef<HTMLDivElement>(null);

  // Adding state — category is set by the "+" button
  const [isAdding, setIsAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [newCategory, setNewCategory] = useState<ExpenseCategory>(
    ExpenseCategory.OTHER,
  );

  // Editing state
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editCategory, setEditCategory] = useState<ExpenseCategory>(
    ExpenseCategory.OTHER,
  );

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [expenseToDelete, setExpenseToDelete] = useState<ExpenseItem | null>(
    null,
  );

  const newExpenseRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const editExpenseRef = useRef<HTMLDivElement>(null);
  const editNameInputRef = useRef<HTMLInputElement>(null);

  const totalSpend = expenseItems.reduce((sum, e) => sum + e.amount, 0);
  const remaining = totalBudget - totalSpend;

  const handleEditBudget = () => {
    setIsEditingBudget(true);
    setEditBudgetValue(totalBudget.toString());
    setEditCurrency(currencyCode);
  };

  const handleConfirmBudget = async () => {
    const budget = parseInt(editBudgetValue) || 0;
    if (budget <= 0) {
      toast.error("Budget must be greater than 0");
      return;
    }
    try {
      await updatePlanBasicInfo(planId, {
        budget,
        currencyCode: editCurrency,
      });
      updateBudgetAndCurrencyCode(budget, editCurrency);
      toast.success("Updated Budget");
      setIsEditingBudget(false);
      setEditBudgetValue("");
    } catch (error) {
      console.error("Update budget failed:", error);
      if (error instanceof AxiosError) {
        toast.error(error.response?.data?.message ?? "Update Failed");
      } else {
        toast.error("Unexpected Error");
      }
    }
  };

  const handleCancelBudget = () => {
    setIsEditingBudget(false);
    setEditBudgetValue("");
    setEditCurrency(currencyCode);
  };

  const handleAddExpenseForCategory = (category: ExpenseCategory) => {
    setIsAdding(true);
    setNewName("");
    setNewAmount("");
    setNewCategory(category);
  };

  const handleConfirmAdd = async () => {
    if (!newName.trim()) {
      toast.error("Please enter an expense name");
      return;
    }
    const amountVal = parseInt(newAmount.replace(/[^\d]/g, "")) || 0;
    if (amountVal <= 0) {
      toast.error("Amount must be greater than 0");
      return;
    }

    try {
      const newExpense = await createExpenseItem(planId, {
        name: newName.trim(),
        amount: amountVal,
        category: newCategory,
      });
      updateExpenseItems([...expenseItems, newExpense]);
      toast.success("Created New Expense");
      handleCancelAdd();
    } catch (error) {
      console.error("Error creating expense:", error);
      toast.error("Failed to create expense");
    }
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setNewName("");
    setNewAmount("");
    setNewCategory(ExpenseCategory.OTHER);
  };

  const handleDeleteExpense = (expense: ExpenseItem) => {
    setExpenseToDelete(expense);
    setDeleteModalOpen(true);
  };

  const handleConfirmDelete = async () => {
    if (!expenseToDelete) return;
    try {
      await deleteExpenseItem(expenseToDelete.id);
      updateExpenseItems(
        expenseItems.filter((e) => e.id !== expenseToDelete.id),
      );
      toast.success("Deleted Expense");
    } catch (error) {
      console.error("Error deleting expense:", error);
      toast.error("Failed to delete expense");
    } finally {
      setExpenseToDelete(null);
    }
  };

  const handleEditExpense = (expense: ExpenseItem) => {
    setEditingId(expense.id);
    setEditName(expense.name);
    setEditAmount(expense.amount.toLocaleString(currencyLocale));
    setEditCategory(expense.category);
  };

  const handleConfirmEdit = async () => {
    const rawValue = editAmount.replace(/[^\d]/g, "");
    const amount = parseInt(rawValue) || 0;
    if (editingId && editName.trim() && amount > 0) {
      try {
        const updatedExpense = await updateExpenseItem(editingId, {
          name: editName.trim(),
          amount,
          category: editCategory,
        });
        updateExpenseItems(
          expenseItems.map((e) => (e.id === editingId ? updatedExpense : e)),
        );
        toast.success("Updated Expense");
        handleCancelEdit();
      } catch (error) {
        console.error("Error updating expense:", error);
        toast.error("Failed to update expense");
      }
    }
    handleCancelEdit();
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditAmount("");
    setEditCategory(ExpenseCategory.OTHER);
  };

  // Build ALL categories (always show all 6)
  const categoryGroups = useMemo(() => {
    return EXPENSE_CATEGORIES.map((cat) => {
      const items = expenseItems.filter((e) => e.category === cat.value);
      const total = items.reduce((sum, e) => sum + e.amount, 0);
      return {
        ...cat,
        items,
        total,
        count: items.length,
      };
    });
  }, [expenseItems]);

  useEffect(() => {
    if (isEditingBudget && budgetInputRef.current) {
      budgetInputRef.current.focus();
    }
  }, [isEditingBudget]);

  useEffect(() => {
    if (isAdding && nameInputRef.current) {
      nameInputRef.current.focus();
    }
  }, [isAdding]);

  useEffect(() => {
    if (editingId && editNameInputRef.current) {
      editNameInputRef.current.focus();
    }
  }, [editingId]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        isEditingBudget &&
        budgetContainerRef.current &&
        !budgetContainerRef.current.contains(event.target as Node)
      ) {
        handleCancelBudget();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isEditingBudget]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (
        target.closest('[data-slot="select-content"]') ||
        target.closest("[data-radix-popper-content-wrapper]")
      ) {
        return;
      }

      if (isAdding && newExpenseRef.current) {
        const rect = newExpenseRef.current.getBoundingClientRect();
        const isInsideRect =
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom;

        if (!newExpenseRef.current.contains(target) && !isInsideRect) {
          handleCancelAdd();
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isAdding]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement;
      if (
        target.closest('[data-slot="select-content"]') ||
        target.closest("[data-radix-popper-content-wrapper]")
      ) {
        return;
      }

      if (editingId && editExpenseRef.current) {
        const rect = editExpenseRef.current.getBoundingClientRect();
        const isInsideRect =
          event.clientX >= rect.left &&
          event.clientX <= rect.right &&
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom;

        if (!editExpenseRef.current.contains(target) && !isInsideRect) {
          handleCancelEdit();
        }
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [editingId]);

  return (
    <section
      ref={ref}
      id="budget"
      data-section-id="budget"
      className={cn(className, "flex flex-col gap-4")}
    >
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-gray-800">Budget</h2>
      </div>

      {/* Summary Cards */}
      <div className="flex flex-wrap gap-4">
        {/* Total Budget */}
        <div className="group p-4 rounded-lg bg-blue-50 border border-blue-200 flex flex-col gap-2 flex-1 min-w-max">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2 min-h-6">
              <Wallet size={18} className="text-blue-500" />
              <span className="text-sm text-blue-600 font-medium">Budget</span>
            </div>
            {!isEditingBudget && (
              <button
                className="cursor-pointer rounded-md p-1.5 bg-yellow-400 hover:bg-yellow-500 text-white opacity-0 group-hover:opacity-100 transition-opacity"
                onClick={handleEditBudget}
                title="Edit budget"
              >
                <Pencil size={12} />
              </button>
            )}
          </div>
          <span className="text-xl font-bold text-blue-700">
            {currencySymbol}
            {totalBudget.toLocaleString(currencyLocale)}
          </span>
        </div>

        <div className="p-4 rounded-lg bg-red-50 border border-red-200 flex flex-col gap-2 flex-1 min-w-max">
          <div className="flex items-center gap-2">
            <TrendingDown size={18} className="text-red-500" />
            <span className="text-sm text-red-600 font-medium">Spent</span>
          </div>
          <span className="text-xl font-bold text-red-700">
            {currencySymbol}
            {totalSpend.toLocaleString(currencyLocale)}
          </span>
        </div>

        <div
          className={cn(
            "p-4 rounded-lg flex flex-col gap-2 flex-1 min-w-max",
            remaining >= 0
              ? "bg-green-50 border border-green-200"
              : "bg-orange-50 border border-orange-200",
          )}
        >
          <div className="flex items-center gap-2">
            <DollarSign
              size={18}
              className={remaining >= 0 ? "text-green-500" : "text-orange-500"}
            />
            <span
              className={cn(
                "text-sm font-medium",
                remaining >= 0 ? "text-green-600" : "text-orange-600",
              )}
            >
              Remaining
            </span>
          </div>
          <span
            className={cn(
              "text-xl font-bold",
              remaining >= 0 ? "text-green-700" : "text-orange-700",
            )}
          >
            {currencySymbol}
            {remaining.toLocaleString(currencyLocale)}
          </span>
        </div>
      </div>

      {/* Edit Budget Dialog */}
      <CustomDialog
        open={isEditingBudget}
        onOpenChange={(open) => {
          if (!open) handleCancelBudget();
        }}
        title="Edit Budget"
        description="Update the budget amount and currency for this plan"
        cancelLabel="Cancel"
        confirmLabel="Save"
        onCancel={handleCancelBudget}
        onConfirm={handleConfirmBudget}
        isDisabled={!editBudgetValue || editBudgetValue === "0"}
      >
        <div className="py-2">
          <label className="text-sm font-medium text-gray-700">Budget</label>
          <div className="mt-1">
            <CurrencyInput
              value={editBudgetValue}
              currency={editCurrency}
              onValueChange={setEditBudgetValue}
              onCurrencyChange={setEditCurrency}
              autoFocus={true}
            />
          </div>
        </div>
      </CustomDialog>

      {/* Pie Chart */}
      <ExpenseChart
        expenseItems={expenseItems}
        currencySymbol={currencySymbol}
        currencyLocale={currencyLocale}
      />

      {/* Expenses List — always show all 6 categories */}
      <div className="flex flex-col gap-3">
        <h3 className="font-semibold text-base text-gray-800">Expenses</h3>

        <div className="flex flex-col gap-3">
          <Accordion type="multiple" className="flex flex-col gap-3">
            {categoryGroups.map((cat) => (
              <AccordionItem
                key={cat.value}
                value={cat.value.toString()}
                className="border border-gray-100 rounded-xl bg-white shadow-sm overflow-hidden transition-all hover:border-gray-200"
              >
                <AccordionTrigger className="px-5 py-4 hover:bg-slate-50/50 hover:no-underline data-[state=open]:border-b data-[state=open]:border-gray-50 transition-colors">
                  <div className="flex items-center justify-between w-full pr-4">
                    <div className="flex items-center gap-3">
                      <span
                        className="w-3.5 h-3.5 rounded-full shadow-sm"
                        style={{ backgroundColor: cat.color }}
                      ></span>
                      <span className="font-semibold text-gray-800 text-sm md:text-base">
                        {cat.label}
                      </span>
                      <span className="text-xs text-gray-400 font-medium">
                        ({cat.count})
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-gray-700 text-sm md:text-base">
                        {currencySymbol}
                        {cat.total.toLocaleString(currencyLocale)}
                      </span>
                      <button
                        className="p-1.5 rounded-md bg-white hover:bg-green-50 text-green-500 hover:text-green-600 border border-gray-200 hover:border-green-200 transition-all shadow-sm opacity-0 group-hover:opacity-100 hover:!opacity-100"
                        title={`Add ${cat.label} expense`}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleAddExpenseForCategory(cat.value);
                          setTimeout(() => {
                            nameInputRef.current?.focus();
                            newExpenseRef.current?.scrollIntoView({
                              behavior: "smooth",
                              block: "center",
                            });
                          }, 100);
                        }}
                      >
                        <Plus size={14} />
                      </button>
                    </div>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-5 pb-5 pt-3 flex flex-col gap-2.5 bg-slate-50/40">
                  {cat.items.length > 0 ? (
                    cat.items.map((expense) => (
                      <ExpenseCard
                        key={expense.id}
                        expenseItem={expense}
                        isEditing={editingId === expense.id}
                        name={editName}
                        amount={editAmount}
                        currencyLocale={currencyLocale}
                        currencySymbol={currencySymbol}
                        onNameChange={setEditName}
                        onAmountChange={setEditAmount}
                        onConfirm={handleConfirmEdit}
                        onCancel={handleCancelEdit}
                        onEdit={() => handleEditExpense(expense)}
                        onDelete={() => handleDeleteExpense(expense)}
                        nameInputRef={editNameInputRef}
                        containerRef={editExpenseRef}
                      />
                    ))
                  ) : (
                    <div className="py-3 text-center text-gray-400 text-xs">
                      No expenses yet
                    </div>
                  )}

                  {/* Inline add form when adding to this category */}
                  {isAdding && newCategory === cat.value && (
                    <ExpenseCard
                      isEditing={true}
                      name={newName}
                      amount={newAmount}
                      currencyLocale={currencyLocale}
                      currencySymbol={currencySymbol}
                      onNameChange={setNewName}
                      onAmountChange={setNewAmount}
                      onConfirm={handleConfirmAdd}
                      onCancel={handleCancelAdd}
                      nameInputRef={nameInputRef}
                      containerRef={newExpenseRef}
                    />
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>
        </div>
      </div>

      <ConfirmDeleteModal
        open={deleteModalOpen}
        onOpenChange={setDeleteModalOpen}
        title="Delete Expense"
        description={`Are you sure you want to delete "${expenseToDelete?.name || "this expense"}" ? This action cannot be undone !`}
        onConfirm={handleConfirmDelete}
      />
    </section>
  );
});

export default Budget;
