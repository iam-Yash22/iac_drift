import { apiClient } from "./client";

export type LatestScan = {
  id: number;
  status: string;
  created_at: string | null;
  summary: unknown;
};

export type AccountScanStatus = {
  account_id: number;
  status: string | null;
};

export type DashboardSummary = {
  total_accounts: number;
  alert_counts: Record<string, number>;
  latest_scans: AccountScanStatus[];
};

export type SeverityHistoryPoint = {
  date: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  none: number;
};

export type SeverityHistory = {
  first_scan_at: string | null;
  points: SeverityHistoryPoint[];
};

export type AccountDashboard = {
  account_id: number;
  latest_scan: LatestScan | null;
  alert_counts: Record<string, number>;
};

export async function getDashboardSummary(): Promise<DashboardSummary> {
  const { data } = await apiClient.get<DashboardSummary>("/api/v1/dashboard/summary");
  return data;
}

export async function getSeverityHistory(accountId?: string | number): Promise<SeverityHistory> {
  const { data } = await apiClient.get<SeverityHistory>(
    "/api/v1/dashboard/severity-history",
    { params: accountId === undefined ? undefined : { account_id: accountId } },
  );
  return data;
}

export async function getAccountDashboard(accountId: string | number): Promise<AccountDashboard> {
  const { data } = await apiClient.get<AccountDashboard>(
    `/api/v1/accounts/${accountId}/dashboard`,
  );
  return data;
}
