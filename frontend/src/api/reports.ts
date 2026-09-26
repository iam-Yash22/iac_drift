import { apiClient } from "./client";
import type { LatestScan } from "./dashboard";

export type ReportRequest = {
  report_type: string;
  format?: string;
  account_id?: number | null;
  resource_id?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  filters?: Record<string, unknown> | null;
};

export type Report = {
  id: number;
  report_type: string;
  format: string;
  status: string;
  account_id: number | null;
  resource_id: number | null;
  created_at: string | null;
  completed_at: string | null;
  download_url: string | null;
  metadata: Record<string, unknown> | null;
};

export type DriftedResource = {
  resource_id: string;
  resource_type: string;
  is_drifted: boolean;
  severity: string;
  diffs: Record<string, { desired: unknown; actual: unknown }>;
  summary: string;
  is_known_exception?: boolean;
};

export type AccountReport = {
  account_id: number;
  generated_at: string;
  latest_scan: LatestScan | null;
  drifted_resources: DriftedResource[];
  severity_counts: Record<string, number>;
};

export async function getAccountReport(
  accountId: string | number,
): Promise<AccountReport> {
  const { data } = await apiClient.get<AccountReport>(
    `/api/v1/accounts/${accountId}/report`,
  );
  return data;
}

export async function createAccountReport(
  accountId: string | number,
  payload: ReportRequest,
): Promise<Report> {
  const { data } = await apiClient.post<Report>(
    `/api/v1/accounts/${accountId}/reports`,
    payload,
  );
  return data;
}
