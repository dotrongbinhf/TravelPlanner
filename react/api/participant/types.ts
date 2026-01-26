export enum PlanRole {
  Owner = 0,
  Editor = 1,
  Viewer = 2,
}

export enum InvitationStatus {
  Pending = 0,
  Accepted = 1,
  Declined = 2,
}

export type InviteTeammateRequest = {
  userId: string;
  role: PlanRole;
};

export type RespondToInvitationRequest = {
  status: InvitationStatus;
};
