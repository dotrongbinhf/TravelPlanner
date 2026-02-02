import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { Ellipsis, LucideIcon } from "lucide-react";

export interface ActionOption {
  label: string;
  icon?: LucideIcon;
  onClick: () => void;
  variant?: "default" | "delete" | "edit";
}

interface ActionMenuProps {
  options: ActionOption[];
  triggerClassName?: string;
  ellipsisSize?: number;
  iconSize?: number;
}

export default function ActionMenu({
  options,
  triggerClassName,
  ellipsisSize = 16,
  iconSize = 16,
}: ActionMenuProps) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          className={cn(
            "p-1.5 cursor-pointer rounded-md text-gray-700 hover:text-gray-800 hover:bg-gray-200 transition-colors outline-none",
            "data-[state=open]:bg-gray-200 data-[state=open]:text-gray-800 data-[state=open]:opacity-100",
            triggerClassName,
          )}
          onClick={(e) => e.stopPropagation()}
        >
          <Ellipsis size={ellipsisSize} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-40">
        {options.map((option, index) => (
          <DropdownMenuItem
            key={index}
            onClick={(e) => {
              e.stopPropagation();
              option.onClick();
            }}
            className={cn("cursor-pointer rounded-md flex items-center gap-2")}
          >
            {option.icon && (
              <div
                className={cn(
                  "rounded-md",
                  option.variant === "delete" && "p-1.5 bg-red-400",
                  option.variant === "edit" && "p-1.5 bg-yellow-400",
                )}
              >
                <option.icon size={iconSize} className="text-white" />
              </div>
            )}
            <span className="text-gray-700 font-semibold">{option.label}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
