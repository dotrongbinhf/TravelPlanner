import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { getInitials, getResizedImageUrl } from "@/utils/image";
import { Collaborator } from "@/types/collaborator";
import { InvitationStatus, PlanRole } from "@/api/collaborator/types";
import { COLLABORATOR_ROLES } from "@/constants/collaborator";
import ActionMenu from "@/components/action-menu";
import { Trash } from "lucide-react";

interface CollaboratorCardProps {
  collaborator: Collaborator;
  onDelete?: (collaborator: Collaborator) => void;
}

export const getRoleBadgeColor = (role: PlanRole) => {
  switch (role) {
    case PlanRole.Owner:
      return "bg-purple-100 text-purple-700 hover:bg-purple-100";
    case PlanRole.Editor:
      return "bg-blue-100 text-blue-700 hover:bg-blue-100";
    case PlanRole.Viewer:
      return "bg-blue-100 text-blue-700 hover:bg-blue-100";
  }
};

export default function CollaboratorCard({
  collaborator,
  onDelete,
}: CollaboratorCardProps) {
  const getStatusBadgeColor = (status: InvitationStatus) => {
    switch (status) {
      case InvitationStatus.Accepted:
        return "bg-green-100 text-green-700 hover:bg-green-100";
      case InvitationStatus.Pending:
        return "bg-yellow-100 text-yellow-700 hover:bg-yellow-100";
      case InvitationStatus.Declined:
        return "bg-red-100 text-red-700 hover:bg-red-100";
    }
  };

  return (
    <div className="p-3 bg-gray-100 rounded-lg flex items-center justify-between group relative">
      <div className="flex items-center gap-3">
        <Avatar className="h-10 w-10">
          <AvatarImage
            src={getResizedImageUrl(collaborator.avatarUrl ?? "", 256, 256)}
            alt={collaborator.name}
          />
          <AvatarFallback className="bg-blue-500 text-white text-sm">
            {getInitials(collaborator.name, collaborator.username)}
          </AvatarFallback>
        </Avatar>

        <div className="flex flex-col">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-gray-700">
              {collaborator.name
                ? `${collaborator.name} (${collaborator.username})`
                : collaborator.username}
            </span>
            {collaborator.status === InvitationStatus.Pending && (
              <Badge
                variant="secondary"
                className={getStatusBadgeColor(InvitationStatus.Pending)}
              >
                Pending
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Badge
              variant="secondary"
              className={getRoleBadgeColor(collaborator.role)}
            >
              {COLLABORATOR_ROLES.find((r) => r.value === collaborator.role)?.label}
            </Badge>
          </div>
        </div>
      </div>

      {onDelete && (
        <div className="absolute right-3 opacity-0 group-hover:opacity-100 has-[[data-state=open]]:opacity-100 transition-opacity">
          <ActionMenu
            options={[
              {
                label: "Remove",
                icon: Trash,
                onClick: () => onDelete(collaborator),
                variant: "delete",
              },
            ]}
            iconSize={16}
            ellipsisSize={16}
          />
        </div>
      )}
    </div>
  );
}
