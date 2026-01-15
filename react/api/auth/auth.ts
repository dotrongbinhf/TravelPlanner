import {
  LoginRequest,
  LoginResponse,
  RefreshTokenResponse,
  RegisterRequest,
  RegisterResponse,
} from "@/types/auth";
import API from "@/utils/api";

const APP_CONFIG_URL = "/api/auth";

// Test for JWT refresh token
export async function getAllUsers() {
  const res = await API.get<any>(`${APP_CONFIG_URL}`);
  return res.data;
}

export async function login(data: LoginRequest) {
  const res = await API.post<LoginResponse>(`${APP_CONFIG_URL}/login`, data);
  return res.data;
}

export async function register(data: RegisterRequest) {
  const res = await API.post<RegisterResponse>(
    `${APP_CONFIG_URL}/register`,
    data
  );
  return res.data;
}

export async function refreshToken() {
  const res = await API.post<RefreshTokenResponse>(
    `${APP_CONFIG_URL}/refresh-token`
  );
  return res.data;
}

export async function logout() {
  const res = await API.post<any>(`${APP_CONFIG_URL}/logout`);
  return res.data;
}
