import { Expense, ExpenseCategory, EXPENSE_CATEGORIES } from "@/types/budget";
import { Check, Pencil, Trash2, X } from "lucide-react";

interface ExpenseCardProps {
  expense?: Expense;
  isEditing: boolean;
  name: string;
  amount: string;
  category: ExpenseCategory;
  onNameChange: (value: string) => void;
  onAmountChange: (value: string) => void;
  onCategoryChange: (value: ExpenseCategory) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  nameInputRef?: React.RefObject<HTMLInputElement | null>;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

export default function ExpenseCard({
  expense,
  isEditing,
  name,
  amount,
  category,
  onNameChange,
  onAmountChange,
  onCategoryChange,
  onConfirm,
  onCancel,
  onEdit,
  onDelete,
  nameInputRef,
  containerRef,
}: ExpenseCardProps) {
  const getCategoryInfo = (cat: ExpenseCategory) => {
    return (
      EXPENSE_CATEGORIES.find((c) => c.value === cat) || EXPENSE_CATEGORIES[5]
    );
  };

  if (isEditing) {
    return (
      <div
        ref={containerRef}
        className="p-3 bg-gray-100 rounded-lg flex flex-col gap-3 border-2 border-blue-400 border-dashed"
      >
        <div className="flex gap-3">
          <input
            ref={nameInputRef}
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="Expense name..."
            className="flex-1 font-medium text-sm bg-transparent border-none outline-none placeholder:text-gray-400"
          />
          <div className="flex items-center gap-1">
            <span className="text-gray-500 text-sm">$</span>
            <input
              type="number"
              value={amount}
              onChange={(e) => onAmountChange(e.target.value)}
              placeholder="0"
              min="0"
              step="0.01"
              className="w-24 text-sm bg-transparent border-none outline-none placeholder:text-gray-400 text-right"
            />
          </div>
        </div>

        <div className="flex justify-between items-center">
          <select
            value={category}
            onChange={(e) =>
              onCategoryChange(e.target.value as ExpenseCategory)
            }
            className="text-sm bg-white border border-gray-300 rounded-md px-2 py-1 outline-none focus:border-blue-400"
          >
            {EXPENSE_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </select>

          <div className="flex gap-1">
            <button
              onClick={onCancel}
              className="cursor-pointer p-2 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
              title="Cancel"
            >
              <X size={14} />
            </button>
            <button
              onClick={onConfirm}
              className="cursor-pointer p-2 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
              title="Confirm"
            >
              <Check size={14} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  const categoryInfo = getCategoryInfo(expense?.category || "other");

  return (
    <div className="group p-3 bg-gray-100 rounded-lg flex items-center justify-between">
      <div className="flex items-center gap-3 flex-1">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: categoryInfo.color }}
        />
        <div className="flex flex-col">
          <span className="text-sm font-medium text-gray-700">
            {expense?.name}
          </span>
          <span className="text-xs text-gray-500">{categoryInfo.label}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-gray-800">
          ${expense?.amount.toFixed(2)}
        </span>

        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            className="cursor-pointer rounded-md p-1.5 bg-yellow-400 hover:bg-yellow-500 text-white"
            onClick={onEdit}
            title="Edit"
          >
            <Pencil size={14} />
          </button>
          <button
            className="cursor-pointer rounded-md p-1.5 bg-red-400 hover:bg-red-500 text-white"
            onClick={onDelete}
            title="Delete"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
