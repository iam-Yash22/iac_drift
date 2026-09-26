import { useQuery } from "@tanstack/react-query";
import PageMeta from "@/components/common/PageMeta";
import DemographicCard from "@/components/ecommerce/DemographicCard";
import EcommerceMetrics from "@/components/ecommerce/EcommerceMetrics";
import MonthlySalesChart from "@/components/ecommerce/MonthlySalesChart";
import MonthlyTarget from "@/components/ecommerce/MonthlyTarget";
import RecentOrders from "@/components/ecommerce/RecentOrders";
import StatisticsChart from "@/components/ecommerce/StatisticsChart";
import { getDashboardSummary, getSeverityHistory } from "@/api/dashboard";

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-12 gap-4 md:gap-6" aria-label="Loading dashboard">
      {Array.from({ length: 5 }, (_, index) => (
        <div
          key={index}
          className="col-span-12 h-40 animate-pulse rounded-2xl border border-gray-200 bg-gray-100 dark:border-gray-800 dark:bg-white/5"
        />
      ))}
    </div>
  );
}

export default function DriftWatchHome() {
  const { data, error, isLoading } = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: getDashboardSummary,
  });
  const severityHistoryQuery = useQuery({
    queryKey: ["dashboard", "severity-history"],
    queryFn: () => getSeverityHistory(),
  });

  if (isLoading) {
    return (
      <>
        <PageMeta title="IaC DriftWatch" description="Infrastructure drift monitoring dashboard" />
        <DashboardSkeleton />
      </>
    );
  }

  if (error || !data) {
    return (
      <>
        <PageMeta title="IaC DriftWatch" description="Infrastructure drift monitoring dashboard" />
        <div className="rounded-2xl border border-error-200 bg-error-50 px-5 py-6 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-400">
          Unable to load dashboard data. Please try again.
        </div>
      </>
    );
  }

  if (data.total_accounts === 0) {
    return (
      <>
        <PageMeta title="IaC DriftWatch" description="Infrastructure drift monitoring dashboard" />
        <div className="rounded-2xl border border-gray-200 bg-white px-5 py-10 dark:border-gray-800 dark:bg-white/3">
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">No accounts yet</h1>
          <p className="mt-3 text-gray-500 dark:text-gray-400">
            Add a monitored AWS account to begin tracking infrastructure drift.
          </p>
        </div>
      </>
    );
  }

  const alertCount = Object.values(data.alert_counts).reduce(
    (total, count) => total + count,
    0,
  );
  const completedScans = data.latest_scans.filter(
    (scan) => scan.status === "completed",
  ).length;
  const completionRate = Math.round(
    (completedScans / data.total_accounts) * 100,
  );
  const scanPoints = data.latest_scans.map((scan) => ({
    label: `Account ${scan.account_id}`,
    value: scan.status === "completed" ? 1 : 0,
  }));
  const scanRows = data.latest_scans.map((scan) => ({
    id: scan.account_id,
    accountId: scan.account_id,
    status: scan.status,
  }));

  return (
    <>
      <PageMeta title="IaC DriftWatch" description="Infrastructure drift monitoring dashboard" />
      <div className="grid grid-cols-12 gap-4 md:gap-6">
        <div className="col-span-12 space-y-6 xl:col-span-7">
          <EcommerceMetrics
            accountCount={data.total_accounts}
            alertCount={alertCount}
          />
          <MonthlySalesChart points={scanPoints} />
        </div>
        <div className="col-span-12 xl:col-span-5">
          <MonthlyTarget
            completionRate={completionRate}
            accountCount={data.total_accounts}
            alertCount={alertCount}
          />
        </div>
        <div className="col-span-12">
          <StatisticsChart
            alertCounts={data.alert_counts}
            history={severityHistoryQuery.data?.points}
          />
        </div>
        <div className="col-span-12 xl:col-span-5">
          <DemographicCard latestScans={data.latest_scans} />
        </div>
        <div className="col-span-12 xl:col-span-7">
          <RecentOrders rows={scanRows} />
        </div>
      </div>
    </>
  );
}
