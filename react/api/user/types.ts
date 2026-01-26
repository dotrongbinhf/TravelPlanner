import { User } from "@/types/user";

export type UpdateUserProfileRequest = {
  name?: string;
  email?: string;
};

export type ChangePasswordRequest = {
  currentPassword: string;
  newPassword: string;
};
