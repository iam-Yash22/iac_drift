import type { ApexOptions } from "apexcharts";
import type ApexCharts from "apexcharts";
import { useRef, useState } from "react";
import Chart from "react-apexcharts";
import type { SeverityHistoryPoint } from "@/api/dashboard";
import { parseUtcDate } from "@/utils/date";

type TimelineScope = "day" | "week" | "month" | "quarter" | "year";

const severityNames = ["critical", "medium", "high", "low"] as const;
const severityColors = ["#ef4444", "#3b82f6", "#f59e0b", "#22c55e"];

function bucketKey(date: Date, scope: TimelineScope) {
  if (Number.isNaN(date.getTime())) return "Unknown";
  if (scope === "day") return date.toISOString().slice(0, 10);
  if (scope === "month") return date.toISOString().slice(0, 7);
  if (scope === "year") return date.getUTCFullYear().toString();
  if (scope === "quarter") {
    return `${date.getUTCFullYear()}-Q${Math.floor(date.getUTCMonth() / 3) + 1}`;
  }

  const start = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
  const day = start.getUTCDay() || 7;
  start.setUTCDate(start.getUTCDate() - day + 1);
  return start.toISOString().slice(0, 10);
}

function displayKey(key: string, scope: TimelineScope) {
  if (scope === "quarter" || scope === "year") return key;
  const date = new Date(`${key}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) return key;
  return date.toLocaleDateString(undefined, {
    dateStyle: "medium",
    timeZone: "UTC",
  });
}

function aggregatePoints(points: SeverityHistoryPoint[], scope: TimelineScope) {
  const buckets = new Map<string, Record<string, number>>();
  for (const point of points) {
    const key = bucketKey(parseUtcDate(point.date), scope);
    const bucket = buckets.get(key) ?? { critical: 0, medium: 0, high: 0, low: 0 };
    for (const severity of severityNames) {
      bucket[severity] += point[severity];
    }
    buckets.set(key, bucket);
  }

  return [...buckets.entries()].sort(([left], [right]) => left.localeCompare(right));
}

export default function StatisticsChart({
  alertCounts,
  history,
  title = "Overall scan severity",
}: {
  alertCounts?: Record<string, number>;
  history?: SeverityHistoryPoint[];
  title?: string;
}) {
  const [scope, setScope] = useState<TimelineScope>("day");
  const [windowSize, setWindowSize] = useState(7);
  const [windowStart, setWindowStart] = useState(0);
  const [zoomAnchor, setZoomAnchor] = useState<number | null>(null);
  const chartRef = useRef<ApexCharts | null>(null);
  const hasHistory = Boolean(history?.length);
  const historyProvided = history !== undefined;

  if (!hasHistory && historyProvided) {
    return (
      <div className="rounded-2xl border border-gray-200 bg-white px-5 py-5 dark:border-gray-800 dark:bg-white/3">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">{title}</h3>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">No completed scan history is available yet.</p>
      </div>
    );
  }

  if (!hasHistory) {
    const categories = ["critical", "high", "medium", "low", "info", "none"];
    const values = categories.map((severity) => alertCounts?.[severity] ?? 0);
    const options: ApexOptions = {
      chart: { fontFamily: "Outfit, sans-serif", toolbar: { show: false } },
      colors: ["#ef4444"],
      dataLabels: { enabled: true },
      plotOptions: { bar: { borderRadius: 4, columnWidth: "45%" } },
      xaxis: { categories },
      yaxis: { min: 0, forceNiceScale: true, decimalsInFloat: 0 },
    };
    return (
      <div className="rounded-2xl border border-gray-200 bg-white px-5 py-5 dark:border-gray-800 dark:bg-white/3">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">{title}</h3>
        {alertCounts ? null : <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">No completed scan history is available.</p>}
        <Chart options={options} series={[{ name: "Resources", data: values }]} type="bar" height={310} />
      </div>
    );
  }

  const grouped = aggregatePoints(history ?? [], scope);
  const maxWindowStart = Math.max(0, grouped.length - windowSize);
  const safeWindowStart = Math.min(windowStart, maxWindowStart);
  const visibleGrouped = grouped.slice(safeWindowStart, safeWindowStart + windowSize);
  const categories = visibleGrouped.map(([key]) => displayKey(key, scope));
  const options: ApexOptions = {
    chart: {
      id: "severity-timeline",
      fontFamily: "Outfit, sans-serif",
      toolbar: { show: false },
      zoom: { enabled: true },
      events: {
        zoomed: (_chart, context) => {
          const minimum = context?.xaxis?.min;
          if (typeof minimum === "number") {
            setZoomAnchor(
              Math.max(
                0,
                Math.min(grouped.length - 1, safeWindowStart + Math.round(minimum)),
              ),
            );
          }
        },
      },
    },
    colors: severityColors,
    stroke: { curve: "straight", width: 3 },
    markers: { size: 4, hover: { size: 6 } },
    dataLabels: { enabled: false },
    tooltip: { shared: true, intersect: false, y: { formatter: (value) => `${value} scan${value === 1 ? "" : "s"}` } },
    xaxis: { type: "category", categories, labels: { rotate: -35 } },
    yaxis: { min: 0, forceNiceScale: true, decimalsInFloat: 0, title: { text: "Scans" } },
    legend: { show: true, position: "top" },
  };
  const series = severityNames.map((severity) => ({
    name: severity[0].toUpperCase() + severity.slice(1),
    data: visibleGrouped.map(([, values]) => values[severity]),
  }));

  return (
    <div className="rounded-2xl border border-gray-200 bg-white px-5 py-5 dark:border-gray-800 dark:bg-white/3">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-800 dark:text-white/90">{title}</h3>
          {alertCounts ? null : (
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Number of completed scans containing each severity.
            </p>
          )}
        </div>
        <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          Scope
          <select
            value={scope}
            onChange={(event) => {
              setScope(event.target.value as TimelineScope);
              setWindowStart(0);
              setZoomAnchor(null);
            }}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-900"
          >
            <option value="day">Days</option>
            <option value="week">Weeks</option>
            <option value="month">Months</option>
            <option value="quarter">Quarters</option>
            <option value="year">Years</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-300">
          Points
          <select
            value={windowSize}
            onChange={(event) => {
              const nextWindowSize = Number(event.target.value);
              setWindowSize(nextWindowSize);
              setWindowStart((current) => Math.min(
                zoomAnchor ?? current,
                Math.max(0, grouped.length - nextWindowSize),
              ));
            }}
            className="rounded-lg border border-gray-300 bg-white px-3 py-2 dark:border-gray-700 dark:bg-gray-900"
          >
            <option value={2}>2</option>
            <option value={7}>7</option>
            <option value={14}>14</option>
            <option value={30}>30</option>
          </select>
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            title="Previous timeline window"
            aria-label="Previous timeline window"
            onClick={() => setWindowStart((current) => Math.max(0, current - windowSize))}
            disabled={windowStart === 0}
            className="rounded-lg border border-gray-300 px-3 py-2 text-lg leading-none text-gray-700 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300"
          >
            &larr;
          </button>
          <button
            type="button"
            title="Next timeline window"
            aria-label="Next timeline window"
            onClick={() => setWindowStart((current) => Math.min(maxWindowStart, current + windowSize))}
            disabled={windowStart === maxWindowStart}
            className="rounded-lg border border-gray-300 px-3 py-2 text-lg leading-none text-gray-700 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:text-gray-300"
          >
            &rarr;
          </button>
          <button
            type="button"
            title="Reset timeline"
            aria-label="Reset timeline"
            onClick={() => {
              setScope("day");
              setWindowSize(30);
              setWindowStart(0);
              setZoomAnchor(null);
              chartRef.current?.resetSeries(false, true);
            }}
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 dark:border-gray-700 dark:text-gray-300"
          >
            Reset graph
          </button>
        </div>
      </div>
      <div className="custom-scrollbar max-w-full overflow-x-auto">
        <div className="min-w-150 xl:min-w-full">
          <Chart
            options={options}
            series={series}
            type="line"
            height={340}
            chartRef={chartRef}
          />
        </div>
      </div>
    </div>
  );
}
