import { apiClient } from "./client";

export type AccountCreate = {
  name: string;
  account_id: string;
  role_arn: string;
  is_active?: boolean;
  metadata?: Record<string, unknown> | null;
};

export type Account = AccountCreate & {
  id: number;
  external_id: string;
  created_at: string | null;
  updated_at: string | null;
};

export async function listAccounts(): Promise<Account[]> {
  const { data } = await apiClient.get<Account[]>("/api/v1/accounts");
  return data;
}

export async function createAccount(payload: AccountCreate): Promise<Account> {
  const { data } = await apiClient.post<Account>("/api/v1/accounts", payload);
  return data;
}

export async function deleteAccount(accountId: number): Promise<void> {
  await apiClient.delete(`/api/v1/accounts/${accountId}`);
}

export async function uploadTerraformBaseline(
  accountId: string | number,
  payload: unknown,
): Promise<{ resources_parsed: number }> {
  const { data } = await apiClient.post<{ resources_parsed: number }>(
    `/api/v1/accounts/${accountId}/terraform-plan`,
    payload,
  );
  return data;
}
