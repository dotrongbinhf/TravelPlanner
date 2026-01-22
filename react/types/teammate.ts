export type TeammateRole = "owner" | "editor" | "viewer";
export type TeammateStatus = "active" | "pending";

export interface Teammate {
  id: string;
  name: string;
  email: string;
  avatar?: string;
  role: TeammateRole;
  status: TeammateStatus;
}

export interface User {
  id: string;
  name: string;
  email: string;
  avatar?: string;
}

export const TEAMMATE_ROLES: { value: TeammateRole; label: string }[] = [
  { value: "owner", label: "Owner" },
  { value: "editor", label: "Editor" },
  { value: "viewer", label: "Viewer" },
];
