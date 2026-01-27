"use client";

import { Plan } from "@/types/plan";
import {
  Calendar,
  Trash2,
  LogOut,
  Check,
  X,
  MoreHorizontal,
  Mail,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getInitials, getResizedImageUrl } from "@/utils/image";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { formatDateRange } from "@/utils/date";

interface PlanCardProps {
  plan: Plan;
  variant: "owned" | "shared" | "pending";
  onAccept?: () => void;
  onDecline?: () => void;
  onDelete?: () => void;
  onLeave?: () => void;
}

export default function PlanCard({
  plan,
  variant,
  onAccept,
  onDecline,
  onDelete,
  onLeave,
}: PlanCardProps) {
  const owner = plan.participants?.find((p) => p.userId === plan.ownerId);
  const others =
    plan.participants?.filter((p) => p.userId !== plan.ownerId) || [];
  const displayOthers = others.slice(0, 3);
  const remainingCount = others.length - 3;

  const invitedByName = variant === "pending" ? owner?.username : null;

  const renderAvatar = (
    avatarUrl: string | undefined,
    name: string | undefined,
    username: string | undefined,
    fallback: string,
    zIndex: number = 0,
    isOwner: boolean = false,
  ) => (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Avatar
            className={`w-8 h-8 border-2 ${isOwner ? "border-yellow-400" : "border-gray-200"}`}
            style={{ zIndex }}
          >
            <AvatarImage src={getResizedImageUrl(avatarUrl || "", 100, 100)} />
            <AvatarFallback className="bg-blue-500 text-white">
              {fallback}
            </AvatarFallback>
          </Avatar>
        </TooltipTrigger>
        <TooltipContent>
          <p>{username || name || "User"}</p>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );

  const cardContent = (
    <div className="relative group rounded-xl overflow-hidden bg-white border border-2 border-gray-300 shadow-lg transition-all duration-300 ease-out h-full flex flex-col hover:-translate-y-1 hover:shadow-lg hover:border-blue-500">
      {/* Cover Image */}
      <div className="relative h-[224px] w-full overflow-hidden">
        {plan.coverImageUrl ? (
          <img
            src={getResizedImageUrl(plan.coverImageUrl, 1024)}
            alt={plan.name}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full bg-gradient-to-br from-primary to-blue-700" />
        )}
        {/* Overlay gradient */}
        {/* <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent" /> */}

        {/* Action Menu */}
        {(variant === "owned" || variant === "shared") && (
          <div className="absolute top-2 right-2 z-10">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-full bg-white/90 hover:bg-white text-gray-700 shadow-sm border border-gray-100"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                  }}
                >
                  <MoreHorizontal className="w-5 h-5" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {variant === "owned" ? (
                  <DropdownMenuItem
                    className="text-red-600 focus:text-red-600 cursor-pointer"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onDelete?.();
                    }}
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete Plan
                  </DropdownMenuItem>
                ) : (
                  <DropdownMenuItem
                    className="text-orange-600 focus:text-orange-600 cursor-pointer"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onLeave?.();
                    }}
                  >
                    <LogOut className="w-4 h-4 mr-2" />
                    Leave Plan
                  </DropdownMenuItem>
                )}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-4 flex flex-col flex-1">
        <h3 className="font-semibold text-gray-900 text-lg line-clamp-1 mb-2">
          {plan.name}
        </h3>

        <div className="flex items-center gap-2 text-sm text-gray-500 mb-2">
          <Calendar className="w-4 h-4" />
          <span>{formatDateRange(plan.startTime, plan.endTime)}</span>
        </div>

        {variant === "pending" && invitedByName && (
          <div className="flex items-center gap-2 text-sm text-gray-500 mb-4 font-medium">
            <Mail className="w-4 h-4" />
            <span>Invited by {invitedByName}</span>
          </div>
        )}

        {/* Bottom Section */}
        <div className="mt-auto">
          {/* Participants */}
          <div className="flex items-center mb-3">
            {/* Owner */}
            {owner && (
              <div className="mr-3">
                {renderAvatar(
                  owner.avatarUrl,
                  owner.name,
                  owner.username,
                  getInitials(owner.name, owner.username),
                  10,
                  true, // isOwner
                )}
              </div>
            )}

            {/* Others */}
            <div className="flex -space-x-4">
              {displayOthers.map((p, index) => (
                <div key={p.id}>
                  {renderAvatar(
                    p.avatarUrl,
                    p.name,
                    p.username,
                    getInitials(p.name, p.username),
                    index,
                  )}
                </div>
              ))}
              {remainingCount > 0 && (
                <TooltipProvider>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div
                        className="w-8 h-8 rounded-full bg-gray-100 border-2 border-white flex items-center justify-center text-xs text-gray-500 font-medium"
                        style={{ zIndex: 10 }}
                      >
                        +{remainingCount}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent>
                      <p>{remainingCount} more participants</p>
                    </TooltipContent>
                  </Tooltip>
                </TooltipProvider>
              )}
            </div>
          </div>

          {variant === "pending" && (
            <div className="flex gap-2 w-full pt-2 border-t border-gray-100">
              <Button
                size="sm"
                variant="default"
                className="flex-1 bg-green-400 hover:bg-green-500"
                onClick={(e) => {
                  console.log("Accept clicked for plan:", plan.id);
                  e.preventDefault();
                  e.stopPropagation();
                  onAccept?.();
                }}
              >
                <Check className="w-4 h-4 mr-1" />
                Accept
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 border-red-300 text-red-600 hover:bg-red-100 hover:text-red-700"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onDecline?.();
                }}
              >
                <X className="w-4 h-4 mr-1" />
                Decline
              </Button>
            </div>
          )}
        </div>
      </div>
    </div>
  );

  if (variant === "pending") {
    return <div className="h-full">{cardContent}</div>;
  }

  return (
    <Link href={`/plans/${plan.id}`} className="block h-full">
      {cardContent}
    </Link>
  );
}
