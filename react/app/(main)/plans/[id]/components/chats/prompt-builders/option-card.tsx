import { cn } from "@/lib/utils";

export function OptionCard({
  icon,
  label,
  desc,
  selected,
  onClick,
}: {
  readonly icon: React.ReactNode;
  readonly label: string;
  readonly desc: string;
  readonly selected: boolean;
  readonly onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex-1 flex items-center gap-2 p-2 rounded-lg border transition-all text-left",
        selected
          ? "bg-blue-50 border-blue-300 ring-1 ring-blue-200"
          : "bg-white border-gray-200 hover:border-gray-300 hover:bg-gray-50",
      )}
    >
      <span className="flex-shrink-0">{icon}</span>
      <div className="min-w-0">
        <p
          className={cn(
            "text-xs font-semibold",
            selected ? "text-blue-700" : "text-gray-700",
          )}
        >
          {label}
        </p>
        <p className="text-[10px] text-gray-400">{desc}</p>
      </div>
    </button>
  );
}
