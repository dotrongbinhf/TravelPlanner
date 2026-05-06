import API from "@/utils/api";
import { InvitationStatus, InviteCollaboratorRequest } from "./types";
import { Collaborator } from "@/types/collaborator";

const APP_CONFIG_URL = "/api/collaborator";

export const inviteCollaborator = async (
  planId: string,
  data: InviteCollaboratorRequest,
) => {
  const response = await API.post<Collaborator>(
    `${APP_CONFIG_URL}/invite`,
    data,
    {
      params: { planId },
    },
  );
  return response.data;
};

// Delete collaborator || Leave Plan
export const deleteCollaborator = async (collaboratorId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${collaboratorId}`);
  return response.data;
};

// Accept/Decline Invitation
export const respondToInvitation = async (
  collaboratorId: string,
  status: InvitationStatus,
) => {
  const response = await API.post<Collaborator>(
    `${APP_CONFIG_URL}/${collaboratorId}/response`,
    { status },
  );
  return response.data;
};
