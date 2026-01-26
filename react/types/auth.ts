export type LoginRequest = {
  username: string;
  password: string;
};

export type LoginResponse = {
  accessToken: string;
  username: string;
  name: string;
  avatarUrl: string;
};

export type RegisterRequest = {
  username: string;
  password: string;
};

export type RegisterResponse = {
  accessToken: string;
};

export type RefreshTokenResponse = {
  accessToken: string;
};
