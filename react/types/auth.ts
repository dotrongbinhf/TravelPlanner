import { User } from "./user";

export type LoginRequest = {
  username: string;
  password: string;
};

export type LoginResponse = {
  accessToken: string;
  user: User;
};

export type RegisterRequest = {
  username: string;
  password: string;
};

export type RegisterResponse = {
  accessToken: string;
  user: User;
};

export type RefreshTokenResponse = {
  accessToken: string;
};
