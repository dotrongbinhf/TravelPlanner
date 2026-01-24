import {
  ExpenseItem,
  ExpenseCategory,
  EXPENSE_CATEGORIES,
} from "@/types/budget";
import { Check, Pencil, Trash2, X } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface ExpenseCardProps {
  expenseItem?: ExpenseItem;
  isEditing: boolean;
  name: string;
  amount: string;
  category: ExpenseCategory;
  currencyLocale: string;
  currencySymbol: string;
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
  expenseItem,
  isEditing,
  name,
  amount,
  category,
  currencyLocale,
  currencySymbol,
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

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      onConfirm();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      onCancel();
    }
  };

  if (isEditing) {
    return (
      <div
        ref={containerRef}
        className="p-3 bg-gray-100 rounded-lg flex items-start justify-between border-2 border-blue-400 border-dashed"
      >
        <div className="flex items-center gap-3 flex-1 overflow-hidden">
          {/* Visual Dot */}
          <div className="w-3 h-3 rounded-full shrink-0" />

          <div className="flex flex-col gap-2 w-full min-w-0">
            {/* Name Input */}
            <input
              ref={nameInputRef}
              type="text"
              value={name}
              onChange={(e) => onNameChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Expense name..."
              className="font-medium text-sm bg-transparent rounded-sm p-1 border border-2 border-dashed border-gray-400 focus:border-blue-500 outline-none placeholder:text-gray-400 w-full min-w-0"
            />

            {/* Category Select - styled to look minimal */}
            <Select
              value={category.toString()}
              onValueChange={(value) =>
                onCategoryChange(Number(value) as ExpenseCategory)
              }
            >
              <SelectTrigger className="w-fit h-auto border border-2 border-gray-400 border-dashed data-[state=open]:border-blue-500 bg-transparent px-2 text-xs justify-start !focus:border-gray-400">
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent position="popper">
                {EXPENSE_CATEGORIES.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value.toString()}>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: cat.color }}
                      />
                      <span>{cat.label}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex flex-col items-center gap-3 ml-2 shrink-0">
          <div className="flex items-center">
            <span className="text-gray-800 text-sm font-semibold">
              {currencySymbol}
            </span>
            <input
              type="text"
              inputMode="numeric"
              value={amount}
              onChange={(e) => {
                const rawValue = e.target.value.replace(/[^\d]/g, "");
                const numValue = parseInt(rawValue) || 0;
                onAmountChange(numValue.toLocaleString(currencyLocale));
              }}
              onKeyDown={handleKeyDown}
              placeholder="0"
              className="w-30 text-sm font-semibold text-gray-800 bg-transparent p-1 rounded-sm border border-2 border-dashed border-gray-400 focus:border-blue-500 outline-none placeholder:text-gray-400"
            />
          </div>

          <div className="flex gap-1 w-full justify-end">
            <button
              onClick={onCancel}
              className="cursor-pointer p-1.5 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors shadow-sm"
              title="Cancel"
            >
              <X size={14} strokeWidth={2} />
            </button>
            <button
              onClick={onConfirm}
              className="cursor-pointer p-1.5 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors shadow-sm"
              title="Confirm"
            >
              <Check size={14} strokeWidth={2} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  const categoryInfo = getCategoryInfo(
    expenseItem?.category ?? ExpenseCategory.OTHER,
  );

  return (
    <div className="group p-3 bg-gray-100 rounded-lg flex items-center justify-between">
      <div className="flex items-center gap-3 flex-1">
        <div
          className="w-3 h-3 rounded-full"
          style={{ backgroundColor: categoryInfo.color }}
        />
        <div className="flex flex-col">
          <span className="text-sm font-medium text-gray-700">
            {expenseItem?.name}
          </span>
          <span className="text-xs text-gray-500">{categoryInfo.label}</span>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-gray-800">
          {currencySymbol}
          {expenseItem?.amount.toLocaleString(currencyLocale)}
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
