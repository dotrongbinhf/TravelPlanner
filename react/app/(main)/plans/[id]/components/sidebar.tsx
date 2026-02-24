"use client";

import {
  Calendar,
  Wallet,
  Backpack,
  Users,
  StickyNote,
  LayoutDashboard,
  ChevronsLeft,
  ChevronsRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface SidebarProps {
  readonly activeSection: string;
  readonly onSectionClick: (sectionId: string) => void;
  readonly isCollapsed: boolean;
  readonly onToggleCollapse: () => void;
}

export const sectionItems = [
  { id: "overview", title: "Overview", icon: LayoutDashboard },
  { id: "itinerary", title: "Itinerary", icon: Calendar },
  { id: "budget", title: "Budget", icon: Wallet },
  { id: "packing-lists", title: "Packing Lists", icon: Backpack },
  { id: "teammates", title: "Participants", icon: Users },
  { id: "notes", title: "Notes", icon: StickyNote },
];

export default function Sidebar({
  activeSection,
  onSectionClick,
  isCollapsed,
  onToggleCollapse,
}: SidebarProps) {
  return (
    <TooltipProvider delayDuration={0}>
      <div
        className={cn(
          "h-full bg-white transition-all duration-300 ease-in-out flex flex-col relative",
          isCollapsed ? "w-15" : "w-[200px]",
        )}
      >
        {/* Toggle Button - Vertically centered on the right edge */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="outline"
              size="icon"
              onClick={onToggleCollapse}
              className="absolute top-1/2 -translate-y-1/2 right-0 z-10 h-6 w-6 rounded-full border bg-white shadow-sm bg-gray-50 hover:bg-gray-100 text-gray-600 opacity-60 hover:opacity-100"
            >
              {isCollapsed ? (
                <ChevronsRight className="h-4 w-4" />
              ) : (
                <ChevronsLeft className="h-4 w-4" />
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            {isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          </TooltipContent>
        </Tooltip>

        <nav className="flex flex-col gap-1 px-2 pt-2">
          {sectionItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeSection === item.id;

            const buttonContent = (
              <button
                key={item.id}
                onClick={() => onSectionClick(item.id)}
                className={cn(
                  "cursor-pointer flex items-center gap-3 rounded-lg font-medium transition-colors duration-200 whitespace-nowrap",
                  isCollapsed ? "px-3 py-3 justify-center" : "px-4 py-3",
                  isActive
                    ? "bg-blue-100 text-blue-700"
                    : "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
                )}
              >
                <Icon
                  size={20}
                  className={cn(
                    "flex-shrink-0",
                    isActive ? "text-blue-700" : "text-gray-500",
                  )}
                />
                {!isCollapsed && <span className="text-sm">{item.title}</span>}
              </button>
            );

            if (isCollapsed) {
              return (
                <Tooltip key={item.id}>
                  <TooltipTrigger asChild>{buttonContent}</TooltipTrigger>
                  <TooltipContent side="right" sideOffset={10}>
                    {item.title}
                  </TooltipContent>
                </Tooltip>
              );
            }

            return buttonContent;
          })}
        </nav>
      </div>
    </TooltipProvider>
  );
}
