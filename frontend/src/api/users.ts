import { apiClient } from "./client";

export type User = {
  id: number;
  username: string;
  email: string;
  role: string;
};

export type UserUpdate = {
  username?: string | null;
  email?: string | null;
  password?: string | null;
  role?: string | null;
};

/** Backend authorization requires the current user to have role=admin. */
export async function listUsers(): Promise<User[]> {
  const { data } = await apiClient.get<User[]>("/api/v1/users");
  return data;
}

export async function updateUser(
  userId: number,
  payload: UserUpdate,
): Promise<User> {
  const { data } = await apiClient.patch<User>(`/api/v1/users/${userId}`, payload);
  return data;
}

export async function createUser(payload: {
  username: string;
  email: string;
  password: string;
}): Promise<User> {
  const { data } = await apiClient.post<User>("/api/v1/users", payload);
  return data;
}

export async function deleteUser(userId: number): Promise<void> {
  await apiClient.delete(`/api/v1/users/${userId}`);
}
