import API from "@/utils/api";
import { InvitationStatus, InviteTeammateRequest } from "./types";
import { Participant } from "@/types/participant";

const BASE_URL = "/api/participant";

export const inviteTeammate = async (
  planId: string,
  data: InviteTeammateRequest,
) => {
  // Check if API endpoint is correct. Usually it's POST /api/participant/invite
  const response = await API.post<Participant>(`${BASE_URL}/invite`, data, {
    params: { planId },
  });
  return response.data;
};

export const deleteParticipant = async (participantId: string) => {
  const response = await API.delete(`${BASE_URL}/${participantId}`);
  return response.data;
};
