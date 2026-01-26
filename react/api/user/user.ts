import API from "@/utils/api";
import { UpdateUserProfileRequest, ChangePasswordRequest } from "./types";
import { User } from "@/types/user";

const USER_API_URL = "/api/user";

export async function getUserProfile() {
  const res = await API.get<User>(`${USER_API_URL}/me`);
  return res.data;
}

export async function updateUserProfile(data: UpdateUserProfileRequest) {
  const res = await API.patch<User>(`${USER_API_URL}/me`, data);
  return res.data;
}

export async function changePassword(data: ChangePasswordRequest) {
  const res = await API.post(`${USER_API_URL}/me/change-password`, data);
  return res.data;
}

export const updateAvatar = async (image: File) => {
  const formData = new FormData();
  formData.append("avatar", image);
  const res = await API.patch<{ avatarUrl: string }>(
    `${USER_API_URL}/me/avatar`,
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
    },
  );
  return res.data;
};

export const findUserByNameOrUsername = async (query: string) => {
  const res = await API.get<User[]>(`${USER_API_URL}/find`, {
    params: {
      query,
    },
  });
  return res.data;
};
