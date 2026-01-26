import { PlanRole } from "@/api/participant/types";

export const TEAMMATE_ROLES: { value: PlanRole; label: string }[] = [
  { value: PlanRole.Owner, label: "Owner" },
  { value: PlanRole.Editor, label: "Editor" },
  { value: PlanRole.Viewer, label: "Viewer" },
];
