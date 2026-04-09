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

  const [isAdding, setIsAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [newCategory, setNewCategory] = useState<ExpenseCategory>(
    ExpenseCategory.OTHER,
  );

  const [newGroupName, setNewGroupName] = useState("");

  const [editingId, setEditingId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editGroupName, setEditGroupName] = useState("");
  const [editCategory, setEditCategory] = useState<ExpenseCategory>(
    ExpenseCategory.OTHER,
  );

  // Delete confirmation modal state
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [expenseToDelete, setExpenseToDelete] = useState<ExpenseItem | null>(
    null,
  );

  // Group editing state
  const [editingGroupKey, setEditingGroupKey] = useState<{
    category: number;
    oldGroupName: string;
  } | null>(null);
  const [editingGroupNewName, setEditingGroupNewName] = useState("");

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

  const handleAddExpense = () => {
    setIsAdding(true);
    setNewName("");
    setNewAmount("");
    setNewCategory(ExpenseCategory.OTHER);
    setNewGroupName("");
  };

  const handleConfirmAdd = async () => {
    if (!newName.trim()) {
      toast.error("Vui lòng nhập tên khoản phí");
      return;
    }
    const amountVal = parseInt(newAmount.replace(/[^\d]/g, "")) || 0;
    if (amountVal <= 0) {
      toast.error("Số tiền phải lớn hơn 0");
      return;
    }

    try {
      const newExpense = await createExpenseItem(planId, {
        name: newName.trim(),
        amount: amountVal,
        category: newCategory,
        groupName: newGroupName.trim() || undefined,
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
    setNewGroupName("");
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
    setEditGroupName(expense.groupName || "");
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
          groupName: editGroupName.trim() || undefined,
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
    setEditGroupName("");
  };

  const handleEditGroup = (catVal: number, groupName: string) => {
    setEditingGroupKey({ category: catVal, oldGroupName: groupName });
    setEditingGroupNewName(groupName);
  };

  const handleConfirmEditGroup = async () => {
    if (!editingGroupKey) return;
    const { oldGroupName, category } = editingGroupKey;
    const newName = editingGroupNewName.trim();
    if (!newName) {
      toast.error("Tên nhóm không được để trống");
      return;
    }

    const itemsInGroup = expenseItems.filter(
      (e) => e.category === category && e.groupName === oldGroupName,
    );

    try {
      const promises = itemsInGroup.map((item) =>
        updateExpenseItem(item.id, {
          name: item.name,
          amount: item.amount,
          category: item.category,
          groupName: newName,
        }),
      );
      const updatedItems = await Promise.all(promises);

      updateExpenseItems(
        expenseItems.map((e) => {
          const updated = updatedItems.find((u) => u.id === e.id);
          return updated || e;
        }),
      );
      toast.success("Đổi tên nhóm thành công");
    } catch (e) {
      toast.error("Lỗi khi sửa tên nhóm");
    }
    setEditingGroupKey(null);
  };

  const handleDeleteGroup = async (catVal: number, groupName: string) => {
    if (
      !confirm(
        `Bạn có chắc muốn xoá toàn bộ chi phí trong nhóm "${groupName}" không?`,
      )
    )
      return;
    const itemsInGroup = expenseItems.filter(
      (e) => e.category === catVal && e.groupName === groupName,
    );
    try {
      const promises = itemsInGroup.map((item) => deleteExpenseItem(item.id));
      await Promise.all(promises);
      updateExpenseItems(
        expenseItems.filter(
          (e) => !(e.category === catVal && e.groupName === groupName),
        ),
      );
      toast.success("Xoá nhóm thành công");
    } catch (e) {
      toast.error("Lỗi khi xoá nhóm");
    }
  };

  const getCategoryLabel = (cat: ExpenseCategory) => {
    return EXPENSE_CATEGORIES.find((c) => c.value === cat)?.label || "Other";
  };

  const categoryGroups = useMemo(() => {
    const categories = EXPENSE_CATEGORIES.map((cat) => {
      const items = expenseItems.filter((e) => e.category === cat.value);
      const total = items.reduce((sum, e) => sum + e.amount, 0);

      const noGroupItems = items.filter((e) => !e.groupName);
      const withGroupItems = items.filter((e) => !!e.groupName);

      const groups: Record<string, ExpenseItem[]> = {};
      withGroupItems.forEach((e) => {
        if (!groups[e.groupName!]) groups[e.groupName!] = [];
        groups[e.groupName!].push(e);
      });

      return {
        ...cat,
        items: noGroupItems,
        groups,
        total,
        allCount: items.length,
      };
    }).filter((c) => c.allCount > 0);
    return categories;
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
      // Ignore clicks inside Select dropdown portal
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
      // Ignore clicks inside Select dropdown portal
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

        <button
          className="cursor-pointer px-4 py-3 flex gap-2 items-center bg-green-400 hover:bg-green-500 text-white rounded-lg transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={handleAddExpense}
          disabled={isAdding || editingId !== null || isEditingBudget}
        >
          <Plus size={16} strokeWidth={3} />
          <span className="text-sm font-medium">Add expense</span>
        </button>
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
      {/* <ExpensePieChart expenseItems={expenseItems} /> */}
      <ExpenseChart
        expenseItems={expenseItems}
        currencySymbol={currencySymbol}
        currencyLocale={currencyLocale}
      />

      {/* Expenses List */}
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
                    </div>
                    <span className="font-bold text-gray-700 text-sm md:text-base">
                      {currencySymbol}
                      {cat.total.toLocaleString(currencyLocale)}
                    </span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-5 pb-5 pt-3 flex flex-col gap-4 bg-slate-50/40">
                  {Object.keys(cat.groups).length > 0 && (
                    <Accordion
                      type="multiple"
                      className="flex flex-col gap-3 w-full"
                    >
                      {Object.entries(cat.groups).map(([groupName, gItems]) => {
                        const groupTotal = gItems.reduce(
                          (s, e) => s + e.amount,
                          0,
                        );
                        return (
                          <AccordionItem
                            key={groupName}
                            value={groupName}
                            className="border-none bg-transparent"
                          >
                            <AccordionTrigger className="group px-1 py-1.5 hover:bg-transparent hover:no-underline transition-colors cursor-pointer">
                              <div className="flex justify-between items-center w-full pr-4">
                                {editingGroupKey?.oldGroupName === groupName &&
                                editingGroupKey?.category === cat.value ? (
                                  <div
                                    className="flex items-center gap-2 w-full max-w-[250px]"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <input
                                      value={editingGroupNewName}
                                      onChange={(e) =>
                                        setEditingGroupNewName(e.target.value)
                                      }
                                      className="text-[13px] uppercase tracking-wider font-bold text-gray-700 bg-white border border-blue-400 focus:border-blue-500 rounded p-1.5 w-full outline-none shadow-sm"
                                      autoFocus
                                      onKeyDown={(e) => {
                                        if (e.key === "Enter")
                                          handleConfirmEditGroup();
                                        if (e.key === "Escape")
                                          setEditingGroupKey(null);
                                      }}
                                    />
                                    <button
                                      onClick={handleConfirmEditGroup}
                                      className="text-green-600 hover:bg-green-100 p-1 rounded transition-colors"
                                    >
                                      <Check size={14} />
                                    </button>
                                    <button
                                      onClick={() => setEditingGroupKey(null)}
                                      className="text-gray-500 hover:bg-gray-200 p-1 rounded transition-colors"
                                    >
                                      <X size={14} />
                                    </button>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-3 w-fit mr-4">
                                    <h4 className="text-[13px] font-bold text-gray-600 uppercase tracking-widest truncate">
                                      {groupName}
                                    </h4>
                                    <div
                                      className="flex items-center opacity-0 group-hover:opacity-100 transition-opacity gap-1"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <button
                                        className="p-1.5 rounded-md bg-white hover:bg-slate-100 text-slate-500 hover:text-slate-700 border border-slate-200 transition-all shadow-sm"
                                        onClick={() =>
                                          handleEditGroup(cat.value, groupName)
                                        }
                                        title="Edit Group Name"
                                      >
                                        <Pencil size={12} />
                                      </button>
                                      <button
                                        className="p-1.5 rounded-md bg-white hover:bg-red-50 text-red-400 hover:text-red-600 border border-slate-200 hover:border-red-200 transition-all shadow-sm"
                                        onClick={() =>
                                          handleDeleteGroup(
                                            cat.value,
                                            groupName,
                                          )
                                        }
                                        title="Delete Group"
                                      >
                                        <Trash2 size={12} />
                                      </button>
                                      <button
                                        className="p-1.5 rounded-md bg-white hover:bg-slate-100 text-slate-500 hover:text-slate-700 border border-slate-200 transition-all shadow-sm hidden md:flex"
                                        title="Add New Expense"
                                        onClick={() => {
                                          setIsAdding(true);
                                          setNewCategory(cat.value);
                                          setNewGroupName(groupName);
                                          setNewName("");
                                          setNewAmount("");
                                          setTimeout(() => {
                                            nameInputRef.current?.focus();
                                            newExpenseRef.current?.scrollIntoView(
                                              {
                                                behavior: "smooth",
                                                block: "center",
                                              },
                                            );
                                          }, 100);
                                        }}
                                      >
                                        <Plus size={12} />
                                      </button>
                                    </div>
                                  </div>
                                )}
                                <span className="text-[13px] font-bold text-gray-600 ml-auto whitespace-nowrap bg-white px-2 py-0.5 rounded-md border border-gray-100">
                                  {currencySymbol}
                                  {groupTotal.toLocaleString(currencyLocale)}
                                </span>
                              </div>
                            </AccordionTrigger>
                            <AccordionContent className="pl-3 pr-1 pb-1 flex flex-col gap-2.5 border-l-2 border-slate-200 ml-1.5 mt-2">
                              {gItems.map((expense) => (
                                <ExpenseCard
                                  key={expense.id}
                                  expenseItem={expense}
                                  isEditing={editingId === expense.id}
                                  name={editName}
                                  amount={editAmount}
                                  category={editCategory}
                                  groupName={editGroupName}
                                  currencyLocale={currencyLocale}
                                  currencySymbol={currencySymbol}
                                  onNameChange={setEditName}
                                  onAmountChange={setEditAmount}
                                  onCategoryChange={setEditCategory}
                                  onGroupNameChange={setEditGroupName}
                                  onConfirm={handleConfirmEdit}
                                  onCancel={handleCancelEdit}
                                  onEdit={() => handleEditExpense(expense)}
                                  onDelete={() => handleDeleteExpense(expense)}
                                  nameInputRef={editNameInputRef}
                                  containerRef={editExpenseRef}
                                />
                              ))}
                            </AccordionContent>
                          </AccordionItem>
                        );
                      })}
                    </Accordion>
                  )}

                  {cat.items.length > 0 && (
                    <div className="flex flex-col gap-2.5 mt-1">
                      {cat.items.map((expense) => (
                        <ExpenseCard
                          key={expense.id}
                          expenseItem={expense}
                          isEditing={editingId === expense.id}
                          name={editName}
                          amount={editAmount}
                          category={editCategory}
                          groupName={editGroupName}
                          currencyLocale={currencyLocale}
                          currencySymbol={currencySymbol}
                          onNameChange={setEditName}
                          onAmountChange={setEditAmount}
                          onCategoryChange={setEditCategory}
                          onGroupNameChange={setEditGroupName}
                          onConfirm={handleConfirmEdit}
                          onCancel={handleCancelEdit}
                          onEdit={() => handleEditExpense(expense)}
                          onDelete={() => handleDeleteExpense(expense)}
                          nameInputRef={editNameInputRef}
                          containerRef={editExpenseRef}
                        />
                      ))}
                    </div>
                  )}
                </AccordionContent>
              </AccordionItem>
            ))}
          </Accordion>

          {isAdding && (
            <ExpenseCard
              isEditing={true}
              name={newName}
              amount={newAmount}
              category={newCategory}
              groupName={newGroupName}
              currencyLocale={currencyLocale}
              currencySymbol={currencySymbol}
              onNameChange={setNewName}
              onAmountChange={setNewAmount}
              onCategoryChange={setNewCategory}
              onGroupNameChange={setNewGroupName}
              onConfirm={handleConfirmAdd}
              onCancel={handleCancelAdd}
              nameInputRef={nameInputRef}
              containerRef={newExpenseRef}
            />
          )}

          {expenseItems.length === 0 && !isAdding && (
            <div className="p-6 bg-gray-50 rounded-lg text-center text-gray-400 text-sm">
              No expenses added yet. Click "Add expense" to get started.
            </div>
          )}
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
