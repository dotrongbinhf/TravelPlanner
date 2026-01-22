"use client";

import { cn } from "@/lib/utils";
import { Expense, ExpenseCategory } from "@/types/budget";
import {
  CirclePlus,
  DollarSign,
  Pencil,
  TrendingDown,
  Wallet,
} from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import ExpenseCard from "./expense-card";
import ExpensePieChart from "./expense-pie-chart";

interface BudgetProps {
  className?: string;
}

const Budget = forwardRef<HTMLDivElement, BudgetProps>(function Budget(
  { className },
  ref,
) {
  const [totalBudget, setTotalBudget] = useState<number>(1000);
  const [isEditingBudget, setIsEditingBudget] = useState(false);
  const [editBudgetValue, setEditBudgetValue] = useState("");
  const budgetInputRef = useRef<HTMLInputElement>(null);
  const budgetContainerRef = useRef<HTMLDivElement>(null);

  const [expenses, setExpenses] = useState<Expense[]>([
    { id: "1", name: "Hotel booking", amount: 250, category: "accommodation" },
    { id: "2", name: "Flight tickets", amount: 350, category: "transport" },
    { id: "3", name: "Restaurant dinner", amount: 45, category: "food" },
    { id: "4", name: "Museum tickets", amount: 30, category: "activities" },
  ]);

  const [isAdding, setIsAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [newCategory, setNewCategory] = useState<ExpenseCategory>("other");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editCategory, setEditCategory] = useState<ExpenseCategory>("other");

  const newExpenseRef = useRef<HTMLDivElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const editExpenseRef = useRef<HTMLDivElement>(null);
  const editNameInputRef = useRef<HTMLInputElement>(null);

  const totalSpend = expenses.reduce((sum, e) => sum + e.amount, 0);
  const remaining = totalBudget - totalSpend;

  const handleEditBudget = () => {
    setIsEditingBudget(true);
    setEditBudgetValue(totalBudget.toString());
  };

  const handleConfirmBudget = () => {
    const value = parseFloat(editBudgetValue);
    if (!isNaN(value) && value >= 0) {
      setTotalBudget(value);
    }
    setIsEditingBudget(false);
    setEditBudgetValue("");
  };

  const handleCancelBudget = () => {
    setIsEditingBudget(false);
    setEditBudgetValue("");
  };

  const handleAddExpense = () => {
    setIsAdding(true);
    setNewName("");
    setNewAmount("");
    setNewCategory("other");
  };

  const handleConfirmAdd = () => {
    const amount = parseFloat(newAmount);
    if (newName.trim() && !isNaN(amount) && amount > 0) {
      const newExpense: Expense = {
        id: Date.now().toString(),
        name: newName.trim(),
        amount,
        category: newCategory,
      };
      setExpenses((prev) => [...prev, newExpense]);
    }
    handleCancelAdd();
  };

  const handleCancelAdd = () => {
    setIsAdding(false);
    setNewName("");
    setNewAmount("");
    setNewCategory("other");
  };

  const handleDeleteExpense = (expenseId: string) => {
    setExpenses((prev) => prev.filter((e) => e.id !== expenseId));
  };

  const handleEditExpense = (expense: Expense) => {
    setEditingId(expense.id);
    setEditName(expense.name);
    setEditAmount(expense.amount.toString());
    setEditCategory(expense.category);
  };

  const handleConfirmEdit = () => {
    const amount = parseFloat(editAmount);
    if (editingId && editName.trim() && !isNaN(amount) && amount > 0) {
      setExpenses((prev) =>
        prev.map((e) =>
          e.id === editingId
            ? { ...e, name: editName.trim(), amount, category: editCategory }
            : e,
        ),
      );
    }
    handleCancelEdit();
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditName("");
    setEditAmount("");
    setEditCategory("other");
  };

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
      if (
        isAdding &&
        newExpenseRef.current &&
        !newExpenseRef.current.contains(event.target as Node)
      ) {
        handleCancelAdd();
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [isAdding]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (
        editingId &&
        editExpenseRef.current &&
        !editExpenseRef.current.contains(event.target as Node)
      ) {
        handleCancelEdit();
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

        <button
          className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleAddExpense}
          disabled={isAdding || editingId !== null || isEditingBudget}
        >
          <CirclePlus size={16} />
          <span className="text-sm font-medium">Add expense</span>
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        {/* Total Budget */}
        <div
          ref={isEditingBudget ? budgetContainerRef : undefined}
          className={cn(
            "group p-4 rounded-lg bg-blue-50 border border-blue-200 flex flex-col gap-2",
            isEditingBudget && "border-2 border-blue-400 border-dashed",
          )}
        >
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-2">
              <Wallet size={18} className="text-blue-500" />
              <span className="text-sm text-blue-600 font-medium">
                Total Budget
              </span>
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
          {isEditingBudget ? (
            <div className="flex items-center gap-1">
              <span className="text-xl font-bold text-blue-700">$</span>
              <input
                ref={budgetInputRef}
                type="number"
                value={editBudgetValue}
                onChange={(e) => setEditBudgetValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleConfirmBudget();
                  if (e.key === "Escape") handleCancelBudget();
                }}
                min="0"
                step="0.01"
                className="text-xl font-bold text-blue-700 bg-transparent border-none outline-none w-full"
              />
            </div>
          ) : (
            <span className="text-xl font-bold text-blue-700">
              ${totalBudget.toFixed(2)}
            </span>
          )}
        </div>

        {/* Total Spend */}
        <div className="p-4 rounded-lg bg-red-50 border border-red-200 flex flex-col gap-2">
          <div className="flex items-center gap-2">
            <TrendingDown size={18} className="text-red-500" />
            <span className="text-sm text-red-600 font-medium">
              Total Spend
            </span>
          </div>
          <span className="text-xl font-bold text-red-700">
            ${totalSpend.toFixed(2)}
          </span>
        </div>

        {/* Remaining */}
        <div
          className={cn(
            "p-4 rounded-lg flex flex-col gap-2",
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
            ${remaining.toFixed(2)}
          </span>
        </div>
      </div>

      {/* Pie Chart */}
      <ExpensePieChart expenses={expenses} />

      {/* Expenses List */}
      <div className="flex flex-col gap-3">
        <h3 className="font-semibold text-base text-gray-800">Expenses</h3>

        <div className="flex flex-col gap-3">
          {expenses.map((expense) => (
            <ExpenseCard
              key={expense.id}
              expense={expense}
              isEditing={editingId === expense.id}
              name={editName}
              amount={editAmount}
              category={editCategory}
              onNameChange={setEditName}
              onAmountChange={setEditAmount}
              onCategoryChange={setEditCategory}
              onConfirm={handleConfirmEdit}
              onCancel={handleCancelEdit}
              onEdit={() => handleEditExpense(expense)}
              onDelete={() => handleDeleteExpense(expense.id)}
              nameInputRef={editNameInputRef}
              containerRef={editExpenseRef}
            />
          ))}

          {isAdding && (
            <ExpenseCard
              isEditing={true}
              name={newName}
              amount={newAmount}
              category={newCategory}
              onNameChange={setNewName}
              onAmountChange={setNewAmount}
              onCategoryChange={setNewCategory}
              onConfirm={handleConfirmAdd}
              onCancel={handleCancelAdd}
              nameInputRef={nameInputRef}
              containerRef={newExpenseRef}
            />
          )}

          {expenses.length === 0 && !isAdding && (
            <div className="p-6 bg-gray-50 rounded-lg text-center text-gray-400 text-sm">
              No expenses added yet. Click "Add expense" to get started.
            </div>
          )}
        </div>
      </div>
    </section>
  );
});

export default Budget;
