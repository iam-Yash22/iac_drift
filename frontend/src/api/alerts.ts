import { apiClient } from "./client";

export type Alert = {
  id: number;
  account_id: number;
  scan_id: number | null;
  drift_record_id: number;
  resource_id: string;
  resource_type: string;
  severity: string;
  diffs: Record<string, unknown>;
  summary: string;
  created_at: string | null;
  updated_at: string | null;
};

export async function listAccountAlerts(
  accountId: string | number,
): Promise<Alert[]> {
  const { data } = await apiClient.get<Alert[]>(
    `/api/v1/accounts/${accountId}/alerts`,
  );
  return data;
}
