import { InvitationStatus, PlanRole } from "@/api/collaborator/types";

export type Collaborator = {
  id: string; // CollaboratorId
  userId: string;
  planId: string;
  role: PlanRole;
  status: InvitationStatus;

  // User Info
  name?: string;
  username?: string;
  avatarUrl?: string;
};
