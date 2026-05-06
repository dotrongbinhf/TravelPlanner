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
  Copy,
} from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { getInitials, getResizedImageUrl } from "@/utils/image";
import ActionMenu from "@/components/action-menu";
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
  onClone?: () => void;
}

export default function PlanCard({
  plan,
  variant,
  onAccept,
  onDecline,
  onDelete,
  onLeave,
  onClone,
}: PlanCardProps) {
  const acceptedCollaborators = (plan.collaborators || []).filter(
    (c) => c.status === 1, // Accepted
  );
  const displayCollaborators = acceptedCollaborators.slice(0, 3);
  const remainingCount = acceptedCollaborators.length - 3;

  const invitedByName = variant === "pending" ? plan.ownerUsername : null;

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
          <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 has-[[data-state=open]]:opacity-100 transition-opacity">
            <ActionMenu
              options={
                variant === "owned"
                  ? [
                      {
                        label: "Clone Plan",
                        icon: Copy,
                        onClick: () => {
                          onClone?.();
                        },
                        variant: "clone",
                      },
                      {
                        label: "Delete Plan",
                        icon: Trash2,
                        onClick: () => {
                          onDelete?.();
                        },
                        variant: "delete",
                      },
                    ]
                  : [
                      {
                        label: "Clone Plan",
                        icon: Copy,
                        onClick: () => {
                          onClone?.();
                        },
                        variant: "clone",
                      },
                      {
                        label: "Leave Plan",
                        icon: LogOut,
                        onClick: () => {
                          onLeave?.();
                        },
                        variant: "delete", // using delete variant for red/orange styling
                      },
                    ]
              }
              triggerClassName="bg-white/60 hover:bg-white/90 backdrop-blur-sm border border-white/40 shadow-none rounded-md p-1.5 text-gray-700 transition-all"
              iconSize={16}
              ellipsisSize={16}
            />
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
          {/* Members */}
          <div className="flex items-center mb-3">
            {/* Owner */}
            <div className="mr-3">
              {renderAvatar(
                plan.ownerAvatarUrl,
                plan.ownerName,
                plan.ownerUsername,
                getInitials(plan.ownerName, plan.ownerUsername),
                10,
                true, // isOwner
              )}
            </div>

            {/* Collaborators */}
            <div className="flex -space-x-4">
              {displayCollaborators.map((c, index) => (
                <div key={c.id}>
                  {renderAvatar(
                    c.avatarUrl,
                    c.name,
                    c.username,
                    getInitials(c.name, c.username),
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
                      <p>{remainingCount} more members</p>
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
