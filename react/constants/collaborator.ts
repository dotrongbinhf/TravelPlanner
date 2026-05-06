import { PlanRole } from "@/api/collaborator/types";

export const COLLABORATOR_ROLES: { value: PlanRole; label: string }[] = [
  { value: PlanRole.Owner, label: "Owner" },
  { value: PlanRole.Editor, label: "Editor" },
  { value: PlanRole.Viewer, label: "Viewer" },
];
