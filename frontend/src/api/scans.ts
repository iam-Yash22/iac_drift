import { apiClient } from "./client";

export type Scan = {
  id: number;
  scan_id: string;
  account_id: number;
  status: ScanStatus;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type ScanStatus = "queued" | "running" | "completed" | "failed";

export const terminalScanStatuses: ScanStatus[] = ["completed", "failed"];

export async function listAccountScans(accountId: string | number): Promise<Scan[]> {
  const { data } = await apiClient.get<Scan[]>(
    `/api/v1/accounts/${accountId}/scans`,
  );
  return data;
}

export async function triggerScan(accountId: string | number): Promise<Scan> {
  const { data } = await apiClient.post<Scan>(
    `/api/v1/accounts/${accountId}/scans`,
  );
  return data;
}

export async function getScanStatus(
  accountId: string | number,
  scanId: string | number,
): Promise<Scan> {
  const { data } = await apiClient.get<Scan>(
    `/api/v1/accounts/${accountId}/scans/${scanId}`,
  );
  return data;
}
