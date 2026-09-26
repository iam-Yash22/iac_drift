import { apiClient } from "./client";

export type AuthTokens = {
  access_token: string;
  token_type: string;
};

export type User = {
  username: string;
  email: string;
  role: string;
};

export type LoginCredentials = {
  username: string;
  password: string;
};

export async function login(credentials: LoginCredentials): Promise<AuthTokens> {
  const form = new URLSearchParams();
  form.set("username", credentials.username);
  form.set("password", credentials.password);

  const { data } = await apiClient.post<AuthTokens>("/api/v1/auth/login", form, {
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  return data;
}

export async function refreshAccessToken(
  refreshToken: string,
): Promise<AuthTokens> {
  const { data } = await apiClient.post<AuthTokens>("/api/v1/auth/refresh", null, {
    params: { refresh_token: refreshToken },
  });
  return data;
}

export async function getCurrentUser(): Promise<User> {
  const { data } = await apiClient.get<User>("/api/v1/auth/me");
  return data;
}
