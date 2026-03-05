import { cn } from "@/lib/utils";
import { X } from "lucide-react";

export function ChipButton({
  label,
  selected,
  onClick,
  onRemove,
}: {
  readonly label: string;
  readonly selected: boolean;
  readonly onClick: () => void;
  readonly onRemove?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-all inline-flex items-center gap-1",
        selected
          ? "bg-blue-50 border-blue-300 text-blue-700 ring-1 ring-blue-200"
          : "bg-white border-gray-200 text-gray-600 hover:border-gray-300 hover:bg-gray-50",
      )}
    >
      {label}
      {onRemove && selected && (
        <X
          className="w-3 h-3 ml-0.5 hover:text-red-500"
          onClick={(e) => {
            e.stopPropagation();
            onRemove();
          }}
        />
      )}
    </button>
  );
}
