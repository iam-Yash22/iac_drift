import { apiClient } from "./client";

export type Resource = {
  id: number;
  account_id: number;
  resource_id: string;
  resource_type: string;
  name: string | null;
  arn: string | null;
  region: string | null;
  tags: Record<string, string> | null;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type DriftRecord = {
  id: number;
  resource_id: number;
  account_id: number | null;
  status: string;
  summary: string | null;
  details: Record<string, unknown> | null;
  detected_at: string | null;
  resolved_at: string | null;
};

export type ResourceListParams = {
  page?: number;
  per_page?: number;
  account_id?: string | number;
};

export async function listResources(
  params?: ResourceListParams,
): Promise<Resource[]> {
  const { data } = await apiClient.get<Resource[]>("/api/v1/resources", {
    params,
  });
  return data;
}

export async function listAccountResources(
  accountId: string | number,
  params?: Pick<ResourceListParams, "page" | "per_page">,
): Promise<Resource[]> {
  const { data } = await apiClient.get<Resource[]>(
    `/api/v1/accounts/${accountId}/resources`,
    { params },
  );
  return data;
}

export async function listDriftRecords(
  accountId?: string | number,
): Promise<DriftRecord[]> {
  const { data } = await apiClient.get<DriftRecord[]>("/api/v1/drift", {
    params: accountId === undefined ? undefined : { account_id: accountId },
  });
  return data;
}
