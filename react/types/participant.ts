import { InvitationStatus, PlanRole } from "@/api/participant/types";

export type Participant = {
  id: string; // ParticipantId
  userId: string;
  planId: string;
  role: PlanRole;
  status: InvitationStatus;

  // User Info
  name?: string;
  username?: string;
  avatarUrl?: string;
};
