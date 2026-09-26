export const MAX_TERRAFORM_PLAN_BYTES = 5 * 1024 * 1024;

export type TerraformPlanPreview = {
  payload: Record<string, unknown>;
  resourceCount: number;
  sizeBytes: number;
};

export function getTerraformPlanSizeBytes(value: string): number {
  return new TextEncoder().encode(value).length;
}

export function countTerraformResources(payload: unknown): number {
  if (!payload || typeof payload !== "object") {
    return 0;
  }

  const document = payload as Record<string, unknown>;
  const directResources = Array.isArray(document.resources) ? document.resources.length : 0;
  const values = document.values;
  const rootModule = values && typeof values === "object"
    ? (values as Record<string, unknown>).root_module
    : undefined;
  const rootResources = rootModule && typeof rootModule === "object"
    ? (rootModule as Record<string, unknown>).resources
    : undefined;

  return directResources + (Array.isArray(rootResources) ? rootResources.length : 0);
}

export function parseTerraformPlan(value: string, sizeBytes = getTerraformPlanSizeBytes(value)): TerraformPlanPreview {
  if (sizeBytes > MAX_TERRAFORM_PLAN_BYTES) {
    throw new Error("This Terraform JSON exceeds the 5 MB size limit.");
  }

  if (!value.trim()) {
    throw new Error("Paste a Terraform JSON payload or choose a .json file.");
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(value) as unknown;
  } catch {
    throw new Error("This is not valid JSON. Paste a Terraform state payload before uploading.");
  }

  const resourceCount = countTerraformResources(parsed);
  if (resourceCount === 0) {
    throw new Error("This JSON does not contain any Terraform resources in a supported state format.");
  }

  return {
    payload: parsed as Record<string, unknown>,
    resourceCount,
    sizeBytes,
  };
}

export function formatTerraformPlanSize(sizeBytes: number): string {
  if (sizeBytes < 1024) return `${sizeBytes} B`;
  if (sizeBytes < 1024 * 1024) return `${(sizeBytes / 1024).toFixed(1)} KB`;
  return `${(sizeBytes / (1024 * 1024)).toFixed(2)} MB`;
}
