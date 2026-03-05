import { cn } from "@/lib/utils";
import { Check, X } from "lucide-react";

export function ToggleOptionCard({
  icon,
  label,
  desc,
  active,
  configured,
  onClick,
  onRemove,
}: {
  readonly icon: React.ReactNode;
  readonly label: string;
  readonly desc: string;
  readonly active: boolean;
  readonly configured: boolean;
  readonly onClick: () => void;
  readonly onRemove?: (e: React.MouseEvent) => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex-1 flex items-center gap-2 p-2 rounded-lg border transition-all text-left relative group",
        active
          ? configured
            ? "bg-emerald-50 border-emerald-300 ring-1 ring-emerald-200"
            : "bg-blue-50 border-blue-300 ring-1 ring-blue-200"
          : "bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50",
      )}
    >
      <span className="flex-shrink-0">{icon}</span>
      <div className="min-w-0 flex-1">
        <p
          className={cn(
            "text-xs font-semibold",
            active
              ? configured
                ? "text-emerald-700"
                : "text-blue-700"
              : "text-gray-700",
          )}
        >
          {label}
        </p>
        <p className="text-[10px] text-gray-400">{desc}</p>
      </div>
      {active && configured && (
        <div className="flex-shrink-0 ml-1">
          <Check className="w-3.5 h-3.5 text-emerald-500 block group-hover:hidden" />
          {onRemove && (
            <div
              role="button"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(e);
              }}
              className="hidden group-hover:block p-0.5 -m-0.5 rounded text-gray-400 hover:text-red-500 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </div>
          )}
        </div>
      )}
    </button>
  );
}
