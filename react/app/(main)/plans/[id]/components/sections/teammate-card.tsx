import { Teammate, TeammateRole, TEAMMATE_ROLES } from "@/types/teammate";
import { Check, Pencil, Trash2, X } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface TeammateCardProps {
  teammate: Teammate;
  isEditing: boolean;
  editRole: TeammateRole;
  onRoleChange: (role: TeammateRole) => void;
  onConfirm: () => void;
  onCancel: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isOwner?: boolean;
  containerRef?: React.RefObject<HTMLDivElement | null>;
}

export default function TeammateCard({
  teammate,
  isEditing,
  editRole,
  onRoleChange,
  onConfirm,
  onCancel,
  onEdit,
  onDelete,
  isOwner = false,
  containerRef,
}: TeammateCardProps) {
  const getInitials = (name: string) => {
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
      .slice(0, 2);
  };

  const getRoleBadgeColor = (role: TeammateRole) => {
    switch (role) {
      case "owner":
        return "bg-purple-100 text-purple-700 hover:bg-purple-100";
      case "editor":
        return "bg-blue-100 text-blue-700 hover:bg-blue-100";
      case "viewer":
        return "bg-gray-100 text-gray-700 hover:bg-gray-100";
    }
  };

  const getStatusBadgeColor = (status: "active" | "pending") => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-700 hover:bg-green-100";
      case "pending":
        return "bg-yellow-100 text-yellow-700 hover:bg-yellow-100";
    }
  };

  if (isEditing) {
    return (
      <div
        ref={containerRef}
        className="p-3 bg-gray-100 rounded-lg flex items-center justify-between border-2 border-blue-400 border-dashed"
      >
        <div className="flex items-center gap-3">
          <Avatar className="h-10 w-10">
            <AvatarImage src={teammate.avatar} alt={teammate.name} />
            <AvatarFallback className="bg-blue-500 text-white text-sm">
              {getInitials(teammate.name)}
            </AvatarFallback>
          </Avatar>

          <div className="flex flex-col">
            <span className="text-sm font-medium text-gray-700">
              {teammate.name}
            </span>
            <span className="text-xs text-gray-500">{teammate.email}</span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="px-3 py-1.5 text-sm border border-gray-300 rounded-md bg-white hover:bg-gray-50 transition-colors">
                {TEAMMATE_ROLES.find((r) => r.value === editRole)?.label}
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {TEAMMATE_ROLES.filter((r) => r.value !== "owner").map((role) => (
                <DropdownMenuItem
                  key={role.value}
                  onClick={() => onRoleChange(role.value)}
                  className="cursor-pointer"
                >
                  {role.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>

          <div className="flex gap-1">
            <button
              onClick={onCancel}
              className="cursor-pointer p-1.5 rounded-md bg-gray-300 hover:bg-gray-400 text-gray-700 transition-colors"
              title="Cancel"
            >
              <X size={14} />
            </button>
            <button
              onClick={onConfirm}
              className="cursor-pointer p-1.5 rounded-md bg-green-400 hover:bg-green-500 text-white transition-colors"
              title="Confirm"
            >
              <Check size={14} />
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="group p-3 bg-gray-100 rounded-lg flex items-center justify-between">
      <div className="flex items-center gap-3">
        <Avatar className="h-10 w-10">
          <AvatarImage src={teammate.avatar} alt={teammate.name} />
          <AvatarFallback className="bg-blue-500 text-white text-sm">
            {getInitials(teammate.name)}
          </AvatarFallback>
        </Avatar>

        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">
              {teammate.name}
            </span>
            {teammate.status === "pending" && (
              <Badge
                variant="secondary"
                className={getStatusBadgeColor("pending")}
              >
                Pending
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="secondary"
              className={getRoleBadgeColor(teammate.role)}
            >
              {TEAMMATE_ROLES.find((r) => r.value === teammate.role)?.label}
            </Badge>
          </div>
        </div>
      </div>

      {!isOwner && (
        <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            className="cursor-pointer rounded-md p-1.5 bg-yellow-400 hover:bg-yellow-500 text-white"
            onClick={onEdit}
            title="Edit role"
          >
            <Pencil size={14} />
          </button>
          <button
            className="cursor-pointer rounded-md p-1.5 bg-red-400 hover:bg-red-500 text-white"
            onClick={onDelete}
            title="Remove"
          >
            <Trash2 size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
