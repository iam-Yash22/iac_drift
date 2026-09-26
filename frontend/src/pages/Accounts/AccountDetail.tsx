import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router";
import PageMeta from "@/components/common/PageMeta";
import Button from "@/components/ui/button/Button";
import Badge from "@/components/ui/badge/Badge";
import StatisticsChart from "@/components/ecommerce/StatisticsChart";
import {
  Table,
  TableBody,
  TableCell,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import FileInput from "@/components/form/input/FileInput";
import { useAuth } from "@/auth/AuthContext";
import { listAccounts, uploadTerraformBaseline } from "@/api/accounts";
import { listAccountAlerts } from "@/api/alerts";
import { getAccountDashboard, getSeverityHistory } from "@/api/dashboard";
import { getAccountReport } from "@/api/reports";
import { listAccountResources } from "@/api/resources";
import { getScanStatus, listAccountScans, terminalScanStatuses, triggerScan } from "@/api/scans";
import { ChevronDownIcon, ChevronUpIcon } from "@/icons";
import { formatUtcTimestamp } from "@/utils/date";
import {
  formatTerraformPlanSize,
  parseTerraformPlan,
} from "@/utils/terraformPlan";

function SectionMessage({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return (
    <p className={error
      ? "rounded-lg bg-error-50 p-4 text-sm text-error-700 dark:bg-error-500/10 dark:text-error-400"
      : "text-sm text-gray-500 dark:text-gray-400"}>
      {children}
    </p>
  );
}

function isNotFoundError(error: unknown) {
  return typeof error === "object" && error !== null && "response" in error &&
    (error as { response?: { status?: number } }).response?.status === 404;
}

function invalidateAccountDetailQueries(queryClient: ReturnType<typeof useQueryClient>, accountId: string) {
  queryClient.invalidateQueries({ queryKey: ["account", accountId] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "report"] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "resources"] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "alerts"] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "scans"] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "severity-history"] });
  queryClient.invalidateQueries({ queryKey: ["account", accountId, "scan-status"] });
  queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  queryClient.invalidateQueries({ queryKey: ["accounts"] });
}

export default function AccountDetail() {
  const { id } = useParams<{ id: string }>();
  const { role } = useAuth();
  const queryClient = useQueryClient();
  const accountId = id as string;
  const [baselineJson, setBaselineJson] = useState("");
  const [baselineFileName, setBaselineFileName] = useState("");
  const [baselineError, setBaselineError] = useState("");
  const [baselineResourceCount, setBaselineResourceCount] = useState<number | null>(null);
  const [baselineSizeBytes, setBaselineSizeBytes] = useState<number | null>(null);
  const [baselineUploadedAt, setBaselineUploadedAt] = useState<string | null>(null);
  const [isScanDetailsExpanded, setIsScanDetailsExpanded] = useState(true);
  const [isBaselineExpanded, setIsBaselineExpanded] = useState(true);
  const [isCurrentScanReportExpanded, setIsCurrentScanReportExpanded] = useState(true);
  const [isResourcesExpanded, setIsResourcesExpanded] = useState(true);
  const [isAlertsExpanded, setIsAlertsExpanded] = useState(true);
  const [severityStartDate, setSeverityStartDate] = useState("");
  const [severityEndDate, setSeverityEndDate] = useState("");
  const [alertSearch, setAlertSearch] = useState("");
  const [alertSeverity, setAlertSeverity] = useState("all");
  const [alertScan, setAlertScan] = useState("all");
  const [expandedScanIds, setExpandedScanIds] = useState<Record<number, boolean>>({});

  const accountQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: listAccounts,
    enabled: role === "admin",
  });
  const dashboardQuery = useQuery({
    queryKey: ["account", accountId, "dashboard"],
    queryFn: () => getAccountDashboard(accountId),
    enabled: Boolean(id),
  });
  const reportQuery = useQuery({
    queryKey: ["account", accountId, "report"],
    queryFn: () => getAccountReport(accountId),
    enabled: Boolean(id) && !dashboardQuery.isPending && !dashboardQuery.error,
  });
  const resourcesQuery = useQuery({
    queryKey: ["account", accountId, "resources"],
    queryFn: () => listAccountResources(accountId, { per_page: 100 }),
    enabled: Boolean(id) && !dashboardQuery.isPending && !dashboardQuery.error,
  });
  const alertsQuery = useQuery({
    queryKey: ["account", accountId, "alerts"],
    queryFn: () => listAccountAlerts(accountId),
    enabled: Boolean(id) && !dashboardQuery.isPending && !dashboardQuery.error,
  });
  const scansQuery = useQuery({
    queryKey: ["account", accountId, "scans"],
    queryFn: () => listAccountScans(accountId),
    enabled: Boolean(id) && !dashboardQuery.isPending && !dashboardQuery.error,
  });
  const severityHistoryQuery = useQuery({
    queryKey: ["account", accountId, "severity-history"],
    queryFn: () => getSeverityHistory(accountId),
    enabled: Boolean(id) && !dashboardQuery.isPending && !dashboardQuery.error,
  });
  const scanMutation = useMutation({
    mutationFn: () => triggerScan(accountId),
    onSuccess: () => {
      invalidateAccountDetailQueries(queryClient, accountId);
    },
  });
  const baselineUploadMutation = useMutation({
    mutationFn: (payload: unknown) => uploadTerraformBaseline(accountId, payload),
    onSuccess: () => {
      invalidateAccountDetailQueries(queryClient, accountId);
      setBaselineJson("");
      setBaselineFileName("");
      setBaselineResourceCount(null);
      setBaselineSizeBytes(null);
      setBaselineError("");
      setBaselineUploadedAt(new Date().toISOString());
    },
    onError: (error: unknown) => {
      const detail =
        typeof error === "object" && error && "response" in error &&
          typeof (error as { response?: { data?: { detail?: string } } }).response?.data?.detail === "string"
          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : null;
      setBaselineError(detail ?? "Unable to upload the Terraform baseline.");
    },
  });
  const scanStatusQuery = useQuery({
    queryKey: ["account", accountId, "scan-status", scanMutation.data?.scan_id],
    queryFn: () => getScanStatus(accountId, scanMutation.data?.scan_id as string),
    enabled: Boolean(scanMutation.data?.scan_id),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && terminalScanStatuses.includes(status) ? false : 2000;
    },
  });

  useEffect(() => {
    const status = scanStatusQuery.data?.status;
    if (!status || !terminalScanStatuses.includes(status)) {
      return;
    }

    invalidateAccountDetailQueries(queryClient, accountId);
  }, [accountId, queryClient, scanStatusQuery.data?.status]);

  if (isNotFoundError(dashboardQuery.error)) {
    return (
      <>
        <PageMeta title="Account not found | IaC DriftWatch" description="The requested account could not be found." />
        <div className="space-y-4 rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">Account not found</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            The requested account does not exist or is no longer available.
          </p>
          <Link to="/accounts" className="text-sm font-medium text-brand-500 hover:text-brand-600">
            Back to accounts
          </Link>
        </div>
      </>
    );
  }

  const account = accountQuery.data?.find((item) => String(item.id) === accountId);
  const latestScanStatus = dashboardQuery.data?.latest_scan?.status;
  const driftCount = reportQuery.data?.drifted_resources.length;
  const resourceCount = resourcesQuery.data?.length;
  const severityHistoryPoints = severityHistoryQuery.data?.points ?? [];
  const firstScanDate = typeof severityHistoryPoints[0]?.date === "string"
    ? severityHistoryPoints[0].date.slice(0, 10)
    : "";
  const selectedSeverityPoints = severityHistoryPoints.filter((point) => {
    const date = typeof point.date === "string" ? point.date.slice(0, 10) : "";
    if (!date) {
      return false;
    }
    return (!severityStartDate || date >= severityStartDate) && (!severityEndDate || date <= severityEndDate);
  });
  const latestSeverityCounts = reportQuery.data?.severity_counts ?? {};
  const alertScanOptions = [...new Set((scansQuery.data ?? []).map((scan) => scan.id))].sort((left, right) => right - left);
  const filteredAlerts = (alertsQuery.data ?? [])
    .filter((alert) => {
      const search = alertSearch.trim().toLowerCase();
      const matchesSearch = !search || alert.resource_id.toLowerCase().includes(search);
      const matchesSeverity = alertSeverity === "all" || alert.severity.trim().toLowerCase() === alertSeverity;
      const matchesScan = alertScan === "all" || String(alert.scan_id) === alertScan;
      return matchesSearch && matchesSeverity && matchesScan;
    })
    .sort((left, right) => {
      if (!left.created_at) return 1;
      if (!right.created_at) return -1;
      return new Date(right.created_at).getTime() - new Date(left.created_at).getTime();
    });
  const filteredScanCount = new Set(filteredAlerts.map((alert) => alert.scan_id).filter((scanId): scanId is number => scanId !== null)).size;
  const latestScan = scansQuery.data?.[0] ?? null;
  const scanGroups = (scansQuery.data ?? [])
    .filter((scan) => alertScan === "all" || String(scan.id) === alertScan)
    .sort((left, right) => right.id - left.id)
    .map((scan) => ({
      scan,
      alerts: filteredAlerts.filter((alert) => alert.scan_id === scan.id),
    }));

  useEffect(() => {
    if (!scansQuery.data) {
      return;
    }

    setExpandedScanIds((current) => {
      const next: Record<number, boolean> = {};
      for (const scan of scansQuery.data) {
        next[scan.id] = false;
      }
      return { ...next, ...current };
    });
  }, [scansQuery.data]);

  const severityBadgeColor = (severity: string | null | undefined) => {
    switch ((severity ?? "unknown").trim().toLowerCase()) {
      case "critical":
        return "error" as const;
      case "high":
        return "warning" as const;
      case "medium":
        return "primary" as const;
      case "low":
        return "success" as const;
      default:
        return "info" as const;
    }
  };

  const normalizedSeverityLabel = (severity: string | null | undefined) => {
    const value = (severity ?? "unknown").trim().toLowerCase();
    if (value === "critical" || value === "high" || value === "medium" || value === "low") {
      return value;
    }
    return "low";
  };

  const alertBadgeColor = (severity: string) => severityBadgeColor(severity);

  const parseBaselineJson = (value: string) => {
    setBaselineError("");
    try {
      const preview = parseTerraformPlan(value);
      setBaselineResourceCount(preview.resourceCount);
      setBaselineSizeBytes(preview.sizeBytes);
      return preview.payload;
    } catch (error) {
      setBaselineError(error instanceof Error ? error.message : "Unable to parse Terraform JSON.");
      setBaselineResourceCount(null);
      setBaselineSizeBytes(null);
      return null;
    }
  };

  const handleBaselineFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const nextValue = await file.text();
    baselineUploadMutation.reset();
    setBaselineFileName(file.name);
    setBaselineJson(nextValue);
    try {
      const preview = parseTerraformPlan(nextValue, file.size);
      setBaselineResourceCount(preview.resourceCount);
      setBaselineSizeBytes(preview.sizeBytes);
      setBaselineError("");
    } catch (error) {
      setBaselineResourceCount(null);
      setBaselineSizeBytes(null);
      setBaselineError(error instanceof Error ? error.message : "Unable to parse Terraform JSON.");
    }
  };

  const handleBaselineSubmit = () => {
    const parsed = parseBaselineJson(baselineJson);
    if (!parsed) {
      return;
    }
    if (!window.confirm("Replaces this account's ENTIRE baseline. Resources not in this file will show as 'no baseline' (critical) on the next scan.")) {
      return;
    }
    baselineUploadMutation.mutate(parsed);
  };

  const handleTriggerScan = () => {
    scanMutation.reset();
    queryClient.removeQueries({
      queryKey: ["account", accountId, "scan-status"],
    });
    scanMutation.mutate();
  };

  return (
    <>
      <PageMeta title="Account details | IaC DriftWatch" description="Account dashboard" />
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <Link to="/accounts" className="text-sm text-brand-500 hover:text-brand-600">
              Accounts
            </Link>
            <h1 className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
              {account?.name ?? `Account ${accountId}`}
            </h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {account ? `Account status: ${account.is_active ? "Active" : "Inactive"}` : "Account details"}
            </p>
          </div>
          <Button
            onClick={handleTriggerScan}
            disabled={scanMutation.isPending || scanStatusQuery.isFetching}
          >
            {scanMutation.isPending
              ? "Triggering..."
              : scanStatusQuery.isFetching
                ? "Scan in progress..."
                : "Trigger Scan"}
          </Button>
        </div>

        {scanMutation.error && <SectionMessage error>Unable to trigger scan.</SectionMessage>}
        {scanMutation.data && (
          <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
            <button
              type="button"
              className="flex w-full items-center justify-between text-left"
              onClick={() => setIsScanDetailsExpanded((expanded) => !expanded)}
              aria-expanded={isScanDetailsExpanded}
            >
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Scan details</h2>
              {isScanDetailsExpanded ? <ChevronUpIcon className="size-5 text-gray-500" /> : <ChevronDownIcon className="size-5 text-gray-500" />}
            </button>
            {isScanDetailsExpanded && <>
            <SectionMessage error={scanStatusQuery.data?.status === "failed"}>
              {scanStatusQuery.data?.status === "failed"
              ? scanStatusQuery.data.error ?? "Scan failed."
              : scanStatusQuery.data?.status === "completed"
                ? `Scan ${scanMutation.data.scan_id} completed.`
                : `Scan ${scanMutation.data.scan_id} is ${scanStatusQuery.data?.status ?? "queued"}.`}
            </SectionMessage>
            <pre className="max-h-120 overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-300">
              {JSON.stringify(scanStatusQuery.data ?? scanMutation.data, null, 2)}
            </pre>
            </>}
          </section>
        )}
        {scanStatusQuery.error && (
          <SectionMessage error>Unable to read scan status.</SectionMessage>
        )}

        {role === "admin" && (
          <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
            <button
              type="button"
              className="flex w-full items-center justify-between text-left"
              onClick={() => setIsBaselineExpanded((expanded) => !expanded)}
              aria-expanded={isBaselineExpanded}
            >
              <span>
                <span className="block text-lg font-semibold text-gray-900 dark:text-white">Terraform baseline</span>
                <span className="mt-1 block text-sm text-gray-500 dark:text-gray-400">
                  Upload a Terraform state payload to replace this account&apos;s baseline.
                </span>
              </span>
              {isBaselineExpanded ? <ChevronUpIcon className="size-5 text-gray-500" /> : <ChevronDownIcon className="size-5 text-gray-500" />}
            </button>
            {isBaselineExpanded && <>
            {baselineFileName && <Badge color="info">{baselineFileName}</Badge>}

            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_220px]">
              <div className="space-y-3">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                  JSON file
                </label>
                <FileInput accept=".json,application/json" onChange={handleBaselineFileChange} />
              </div>

              <div className="flex items-end">
                <Button
                  variant="outline"
                  onClick={() => {
                    setBaselineJson("");
                    setBaselineFileName("");
                    setBaselineError("");
                    setBaselineResourceCount(null);
                    setBaselineSizeBytes(null);
                    setBaselineUploadedAt(null);
                  }}
                  className="w-full"
                  disabled={baselineUploadMutation.isPending}
                >
                  Clear
                </Button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                Paste Terraform JSON
              </label>
              <textarea
                value={baselineJson}
                onChange={(event) => {
                  const nextValue = event.target.value;
                  baselineUploadMutation.reset();
                  setBaselineJson(nextValue);
                  if (!baselineFileName) {
                    setBaselineFileName("Pasted JSON");
                  }
                  parseBaselineJson(nextValue);
                }}
                className="min-h-40 w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-sm text-gray-700 shadow-theme-xs outline-none transition focus:border-brand-300 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
                placeholder={`{
  "resources": [ ... ],
  "values": {
    "root_module": {
      "resources": [ ... ]
    }
  }
}`}
              />
            </div>

            {baselineResourceCount !== null && (
              <p className="text-sm text-gray-600 dark:text-gray-300">
                Preview: {baselineFileName || "Pasted JSON"} · {formatTerraformPlanSize(baselineSizeBytes ?? 0)} · {baselineResourceCount} Terraform resource entries detected.
              </p>
            )}
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Accepted shapes: top-level <code>resources</code> or <code>values.root_module.resources</code>.
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">CI/CD (Jenkins) ingestion: planned</p>
            {baselineError && <SectionMessage error>{baselineError}</SectionMessage>}
            {baselineUploadMutation.isSuccess && (
              <SectionMessage>
                Baseline updated successfully. {baselineUploadMutation.data.resources_parsed} resources were parsed{baselineUploadedAt ? ` at ${formatUtcTimestamp(baselineUploadedAt)}.` : "."}
              </SectionMessage>
            )}
            {baselineUploadMutation.isError && !baselineError && (
              <SectionMessage error>Unable to upload the Terraform baseline.</SectionMessage>
            )}

            <Button
              className="w-full sm:w-auto"
              onClick={handleBaselineSubmit}
              disabled={baselineUploadMutation.isPending || !baselineJson.trim()}
            >
              {baselineUploadMutation.isPending ? "Uploading..." : "Upload baseline"}
            </Button>
            {baselineUploadMutation.isSuccess && (
              <Button variant="outline" onClick={handleTriggerScan} disabled={scanMutation.isPending || scanStatusQuery.isFetching}>
                Run a scan
              </Button>
            )}
            </>}
          </section>
        )}

        {scansQuery.data && scansQuery.data.length > 0 && (
          <section className="space-y-4 rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Latest scan #{latestScan?.id ?? scansQuery.data[0].id} · {scansQuery.data.length} scans
            </h2>
          </section>
        )}

        <section className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Account dashboard</h2>
          {dashboardQuery.isLoading && <SectionMessage>Loading dashboard data...</SectionMessage>}
          {dashboardQuery.error && <SectionMessage error>Unable to load dashboard data.</SectionMessage>}
          {dashboardQuery.data && (
            <>
            <div className="grid gap-6 md:grid-cols-2">
              <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
                <p className="text-sm text-gray-500 dark:text-gray-400">Latest scan status</p>
                <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
                  {latestScanStatus ?? "Not scanned"}
                </p>
                {dashboardQuery.data.latest_scan?.created_at && (
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                    {formatUtcTimestamp(dashboardQuery.data.latest_scan.created_at)}
                  </p>
                )}
              </div>
              <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
                <p className="text-sm text-gray-500 dark:text-gray-400">All-time alerts (historical)</p>
                <div className="mt-4 space-y-2">
                  {Object.entries(dashboardQuery.data.alert_counts).map(([severity, count]) => (
                    <div key={severity} className="flex justify-between text-sm text-gray-700 dark:text-gray-300">
                      <span>{severity}</span>
                      <span>{count}</span>
                    </div>
                  ))}
                  {Object.keys(dashboardQuery.data.alert_counts).length === 0 && (
                    <p className="text-sm text-gray-500">No alerts recorded.</p>
                  )}
                </div>
              </div>
            </div>
            </>
          )}
        </section>

        <section className="space-y-4">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setIsResourcesExpanded((expanded) => !expanded)}
            aria-expanded={isResourcesExpanded}
          >
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Resource inventory</h2>
            {isResourcesExpanded ? <ChevronUpIcon className="size-5 text-gray-500" /> : <ChevronDownIcon className="size-5 text-gray-500" />}
          </button>
          {isResourcesExpanded && <>
          {resourcesQuery.isLoading && <SectionMessage>Loading resource records...</SectionMessage>}
          {resourcesQuery.error && <SectionMessage error>Unable to load resource records.</SectionMessage>}
          {resourcesQuery.data && resourcesQuery.data.length === 0 && (
            <SectionMessage>No resource records are available.</SectionMessage>
          )}
          {resourcesQuery.data && resourcesQuery.data.length > 0 && (
            <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
              <div className="max-w-full overflow-x-auto">
                <Table>
                  <TableHeader className="border-b border-gray-100 dark:border-white/5">
                    <TableRow>
                      {['Resource', 'Type', 'Region', 'Status'].map((heading) => (
                        <TableCell key={heading} isHeader className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                          {heading}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                    {resourcesQuery.data.map((resource) => (
                      <TableRow key={resource.id}>
                        <TableCell className="px-5 py-4 text-sm text-gray-800 dark:text-white/90">
                          {resource.name ?? resource.resource_id}
                        </TableCell>
                        <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                          {resource.resource_type}
                        </TableCell>
                        <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                          {resource.region ?? "Unavailable"}
                        </TableCell>
                        <TableCell className="px-5 py-4 text-sm">
                          <Badge color={resource.is_active ? "success" : "error"}>
                            {resource.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </div>
          )}
          </>}
        </section>

        <section className="space-y-4">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setIsCurrentScanReportExpanded((expanded) => !expanded)}
            aria-expanded={isCurrentScanReportExpanded}
          >
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Current scan report</h2>
            {isCurrentScanReportExpanded ? <ChevronUpIcon className="size-5 text-gray-500" /> : <ChevronDownIcon className="size-5 text-gray-500" />}
          </button>
          {isCurrentScanReportExpanded && <>
          {reportQuery.isLoading && <SectionMessage>Loading drift report...</SectionMessage>}
          {reportQuery.error && <SectionMessage error>Unable to load drift report.</SectionMessage>}
          {reportQuery.data && (
            <>
              <div className="grid gap-6 md:grid-cols-2">
                <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
                  <p className="text-sm text-gray-500 dark:text-gray-400">Current resource count</p>
                  <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
                    {resourceCount ?? "Unavailable"}
                  </p>
                  <p className="mt-1 text-xs text-gray-500">Records returned by the resource endpoint; no total field is provided.</p>
                </div>
                <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
                  <p className="text-sm text-gray-500 dark:text-gray-400">Drifted resource count</p>
                  <p className="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{driftCount ?? 0}</p>
                </div>
              </div>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Latest scan: {reportQuery.data.latest_scan
                  ? `Latest scan #${reportQuery.data.latest_scan.id} · ${new Date(reportQuery.data.latest_scan.created_at ?? reportQuery.data.generated_at).toLocaleString(undefined, {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })}`
                  : "Unavailable"}
              </p>
              <pre className="max-h-120 overflow-auto rounded-lg border border-gray-200 bg-gray-50 p-4 text-xs text-gray-700 dark:border-gray-800 dark:bg-gray-950 dark:text-gray-300">
                {JSON.stringify(scanStatusQuery.data?.result ?? reportQuery.data, null, 2)}
              </pre>

              {reportQuery.data.drifted_resources.length > 0 ? (
                <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
                  <div className="max-w-full overflow-x-auto">
                    <Table>
                      <TableHeader className="border-b border-gray-100 dark:border-white/5">
                        <TableRow>
                          {['Resource ID', 'Type', 'Severity', 'Summary'].map((heading) => (
                            <TableCell key={heading} isHeader className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                              {heading}
                            </TableCell>
                          ))}
                        </TableRow>
                      </TableHeader>
                      <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                        {reportQuery.data.drifted_resources.map((drift, index) => (
                          <TableRow key={`${reportQuery.data.latest_scan?.id ?? "latest"}-${index}`}>
                            <TableCell className="px-5 py-4 text-sm text-gray-800 dark:text-white/90">
                              {drift.resource_id || "Unknown"}
                            </TableCell>
                            <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                              {drift.resource_type || "Unknown"}
                            </TableCell>
                            <TableCell className="px-5 py-4 text-sm">
                              <Badge color={severityBadgeColor(normalizedSeverityLabel(drift.severity))}>
                                {normalizedSeverityLabel(drift.severity)}
                              </Badge>
                            </TableCell>
                            <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                              {drift.summary || "No summary available."}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </div>
              ) : (
                <SectionMessage>No drifted resources were reported for this account.</SectionMessage>
              )}

              <div className="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/3">
                <div className="flex flex-wrap items-end justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Drift severity</h3>
                    <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                      Latest completed scan, excluding known exceptions and non-drifted resources.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-end gap-3">
                    <label className="text-sm text-gray-600 dark:text-gray-300">
                      From
                      <input
                        type="date"
                        min={firstScanDate}
                        max={severityEndDate || undefined}
                        value={severityStartDate || firstScanDate}
                        onChange={(event) => setSeverityStartDate(event.target.value)}
                        className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-900"
                      />
                    </label>
                    <label className="text-sm text-gray-600 dark:text-gray-300">
                      To
                      <input
                        type="date"
                        min={severityStartDate || firstScanDate}
                        value={severityEndDate || new Date().toISOString().slice(0, 10)}
                        onChange={(event) => setSeverityEndDate(event.target.value)}
                        className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-900"
                      />
                    </label>
                  </div>
                </div>
                {reportQuery.isLoading && <SectionMessage>Loading latest scan severity...</SectionMessage>}
                {!reportQuery.isLoading && !reportQuery.data?.latest_scan && (
                  <SectionMessage>No completed scan is available.</SectionMessage>
                )}
                {reportQuery.data?.latest_scan && (
                  <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {(["critical", "medium", "high", "low"] as const).map((severity) => (
                      <div key={severity} className="rounded-lg border border-gray-200 px-4 py-3 dark:border-gray-700">
                        <p className="text-sm capitalize text-gray-500 dark:text-gray-400">{severity}</p>
                        <p className="mt-1 text-xl font-semibold text-gray-900 dark:text-white">
                          {latestSeverityCounts[severity] ?? 0}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
                {severityHistoryPoints.length > 0 && (
                  <div className="mt-6">
                    <StatisticsChart
                      title="All-time alerts (historical)"
                      history={selectedSeverityPoints}
                    />
                  </div>
                )}
              </div>
            </>
          )}
          </>}
        </section>

        <section className="space-y-4">
          <button
            type="button"
            className="flex w-full items-center justify-between text-left"
            onClick={() => setIsAlertsExpanded((expanded) => !expanded)}
            aria-expanded={isAlertsExpanded}
          >
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Alert history (new or changed drift)</h2>
            {isAlertsExpanded ? <ChevronUpIcon className="size-5 text-gray-500" /> : <ChevronDownIcon className="size-5 text-gray-500" />}
          </button>
          {isAlertsExpanded && <>
          {alertsQuery.isLoading && <SectionMessage>Loading alerts...</SectionMessage>}
          {alertsQuery.error && <SectionMessage error>Unable to load alerts.</SectionMessage>}
          {scansQuery.data && scansQuery.data.length === 0 && (!alertsQuery.data || alertsQuery.data.length === 0) && (
            <SectionMessage>No alert history is available.</SectionMessage>
          )}
          {((scansQuery.data && scansQuery.data.length > 0) || (alertsQuery.data && alertsQuery.data.length > 0)) && (
            <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/3">
              <div className="flex flex-wrap items-center gap-3 border-b border-gray-100 p-4 dark:border-white/5">
                <input
                  type="search"
                  value={alertSearch}
                  onChange={(event) => setAlertSearch(event.target.value)}
                  placeholder="Search drifted resource"
                  className="h-10 min-w-60 flex-1 rounded-lg border border-gray-300 bg-transparent px-3 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-300"
                />
                <select
                  value={alertSeverity}
                  onChange={(event) => setAlertSeverity(event.target.value)}
                  className="h-10 rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
                >
                  <option value="all">All severities</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <select
                  value={alertScan}
                  onChange={(event) => setAlertScan(event.target.value)}
                  className="h-10 rounded-lg border border-gray-300 bg-white px-3 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
                >
                  <option value="all">All scans</option>
                  {alertScanOptions.map((scanId) => (
                    <option key={scanId} value={scanId}>Scan #{scanId}</option>
                  ))}
                </select>
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  {filteredAlerts.length} alerts · {filteredScanCount} scans
                </span>
              </div>
              <div className="max-w-full overflow-x-auto">
                <Table>
                  <TableHeader className="border-b border-gray-100 dark:border-white/5">
                    <TableRow>
                      {['Scan', 'Resource', 'Severity', 'Timestamp'].map((heading) => (
                        <TableCell key={heading} isHeader className="px-5 py-3 text-start text-theme-xs font-medium text-gray-500 dark:text-gray-400">
                          {heading}
                        </TableCell>
                      ))}
                    </TableRow>
                  </TableHeader>
                  {scanGroups.length > 0 ? (
                    <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                      {scanGroups.flatMap(({ scan, alerts }) => {
                        const scanId = scan.id;
                        const isExpanded = !!expandedScanIds[scanId];
                        const scanDrifts = Array.isArray(scan.result?.drifts)
                          ? (scan.result?.drifts as Array<Record<string, unknown>>)
                          : [];
                        const rows = [
                          <TableRow key={`scan-header-${scanId}`}>
                            <TableCell className="bg-gray-50 px-5 py-3 text-sm font-medium text-gray-700 dark:bg-white/3 dark:text-gray-300">
                              <div className="flex items-center gap-2">
                                <button
                                  type="button"
                                  onClick={() => setExpandedScanIds((current) => {
                                    const next: Record<number, boolean> = {};
                                    for (const item of scansQuery.data ?? []) {
                                      next[item.id] = false;
                                    }
                                    if (current[scanId]) {
                                      return next;
                                    }
                                    next[scanId] = true;
                                    return next;
                                  })}
                                  className="inline-flex items-center justify-center rounded-md border border-gray-200 bg-white p-1 text-gray-600 hover:text-gray-900 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300"
                                  aria-label={isExpanded ? `Collapse scan ${scanId}` : `Expand scan ${scanId}`}
                                >
                                  {isExpanded ? <ChevronUpIcon className="size-4" /> : <ChevronDownIcon className="size-4" />}
                                </button>
                                <span>
                                  Scan #{scanId} · {scan.created_at ? formatUtcTimestamp(scan.created_at) : "timestamp unavailable"} · {alerts.length} new alerts
                                </span>
                              </div>
                            </TableCell>
                            <TableCell className="bg-gray-50 dark:bg-white/3" />
                            <TableCell className="bg-gray-50 dark:bg-white/3" />
                            <TableCell className="bg-gray-50 dark:bg-white/3" />
                          </TableRow>,
                        ];

                        if (isExpanded) {
                          rows.push(
                            <TableRow key={`scan-report-${scanId}`}>
                              <TableCell className="px-0 py-0 dark:bg-white/2">
                                <div className="border-t border-gray-100 bg-gray-50 px-4 py-3 dark:border-white/5 dark:bg-white/2">
                                  <div className="mb-2 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                                    Scan report · {scanDrifts.length} drifted resources
                                  </div>
                                  <div className="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-950">
                                    <Table>
                                      <TableHeader className="border-b border-gray-100 dark:border-white/5">
                                        <TableRow>
                                          {['Resource', 'Type', 'Severity', 'Summary'].map((heading) => (
                                            <TableCell key={heading} isHeader className="px-4 py-2 text-start text-xs font-medium text-gray-500 dark:text-gray-400">
                                              {heading}
                                            </TableCell>
                                          ))}
                                        </TableRow>
                                      </TableHeader>
                                      <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                                        {scanDrifts.length > 0 ? (
                                          scanDrifts.map((drift, index) => (
                                            <TableRow key={`${scanId}-drift-${index}`}>
                                              <TableCell className="px-4 py-3 text-sm text-gray-800 dark:text-white/90">
                                                {String(drift.resource_id ?? "Unknown")}
                                              </TableCell>
                                              <TableCell className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                                                {String(drift.resource_type ?? "Unknown")}
                                              </TableCell>
                                              <TableCell className="px-4 py-3 text-sm">
                                                <Badge color={severityBadgeColor(normalizedSeverityLabel(String(drift.severity ?? "unknown")))}>
                                                  {normalizedSeverityLabel(String(drift.severity ?? "unknown"))}
                                                </Badge>
                                              </TableCell>
                                              <TableCell className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                                                {String(drift.summary ?? "No summary available.")}
                                              </TableCell>
                                            </TableRow>
                                          ))
                                        ) : (
                                          <TableRow>
                                            <TableCell className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                                              No drifted resources reported for this scan.
                                            </TableCell>
                                            <TableCell />
                                            <TableCell />
                                            <TableCell />
                                          </TableRow>
                                        )}
                                      </TableBody>
                                    </Table>
                                  </div>
                                </div>
                              </TableCell>
                            </TableRow>,
                          );
                        }

                        return rows;
                      })}
                    </TableBody>
                  ) : (
                    <TableBody className="divide-y divide-gray-100 dark:divide-white/5">
                      <TableRow>
                        <TableCell className="px-5 py-4 text-sm text-gray-500 dark:text-gray-400">
                          No alert scans match the selected resource and severity.
                        </TableCell>
                        <TableCell />
                        <TableCell />
                        <TableCell />
                      </TableRow>
                    </TableBody>
                  )}
                </Table>
              </div>
            </div>
          )}
          </>}
        </section>
      </div>
    </>
  );
}
