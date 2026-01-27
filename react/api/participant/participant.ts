import API from "@/utils/api";
import { InvitationStatus, InviteTeammateRequest } from "./types";
import { Participant } from "@/types/participant";

const APP_CONFIG_URL = "/api/participant";

export const inviteTeammate = async (
  planId: string,
  data: InviteTeammateRequest,
) => {
  const response = await API.post<Participant>(
    `${APP_CONFIG_URL}/invite`,
    data,
    {
      params: { planId },
    },
  );
  return response.data;
};

// Delete participant || Leave Plan
export const deleteParticipant = async (participantId: string) => {
  const response = await API.delete(`${APP_CONFIG_URL}/${participantId}`);
  return response.data;
};

// Accept/Decline Invitation
export const respondToInvitation = async (
  participantId: string,
  status: InvitationStatus,
) => {
  const response = await API.post<Participant>(
    `${APP_CONFIG_URL}/${participantId}/response`,
    { status },
  );
  return response.data;
};
