"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SearchEngineStats {
  engine: string;
  hitRate: number;
  latencyMs: number;
  totalRequests: number;
}

interface TokenUsageData {
  timestamp: string;
  provider: string;
  tokens: number;
  costUsd: number;
}

interface FusionConsistencyData {
  timestamp: string;
  strategy: string;
  consistency: number;
}

interface DecomposeQualityData {
  timestamp: string;
  score: number;
  subtaskCount: number;
  dagDepth: number;
}

interface ChineseMetrics {
  searchEngines: SearchEngineStats[];
  tokenUsage: TokenUsageData[];
  fusionConsistency: FusionConsistencyData[];
  decomposeQuality: DecomposeQualityData[];
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Simple stat card with title, value, and optional trend indicator. */
function StatCard({
  title,
  value,
  subtitle,
  trend,
}: {
  title: string;
  value: string;
  subtitle?: string;
  trend?: "up" | "down" | "neutral";
}) {
  const trendColors = {
    up: "text-green-500",
    down: "text-red-500",
    neutral: "text-gray-400",
  };
  const trendArrows = { up: "▲", down: "▼", neutral: "—" };

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-700 dark:bg-gray-800">
      <div className="text-sm font-medium text-gray-500 dark:text-gray-400">
        {title}
      </div>
      <div className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">
        {value}
      </div>
      {subtitle && (
        <div className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          {trend && (
            <span className={trendColors[trend]}>{trendArrows[trend]} </span>
          )}
          {subtitle}
        </div>
      )}
    </div>
  );
}

/** Horizontal bar showing a percentage with label. */
function ProgressBar({
  label,
  value,
  maxValue = 1,
  color = "bg-blue-500",
}: {
  label: string;
  value: number;
  maxValue?: number;
  color?: string;
}) {
  const pct = Math.min(100, Math.round((value / maxValue) * 100));
  return (
    <div className="mb-2">
      <div className="mb-1 flex justify-between text-xs text-gray-600 dark:text-gray-300">
        <span>{label}</span>
        <span>{pct}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-gray-200 dark:bg-gray-700">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/** Mini pie-chart-like display for search engine hit rates. */
function SearchEnginePies({ engines }: { engines: SearchEngineStats[] }) {
  const total = engines.reduce((s, e) => s + e.totalRequests, 0);
  const colors = [
    "bg-blue-500",
    "bg-green-500",
    "bg-purple-500",
    "bg-orange-500",
  ];

  return (
    <div className="space-y-3">
      {engines.map((e, i) => (
        <ProgressBar
          key={e.engine}
          label={`${e.engine} (${e.totalRequests} 次请求, ${e.latencyMs}ms)`}
          value={e.hitRate}
          maxValue={1}
          color={colors[i % colors.length]}
        />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Dashboard Component
// ---------------------------------------------------------------------------

export default function ChineseDashboard() {
  const [metrics, setMetrics] = useState<ChineseMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshInterval, setRefreshInterval] = useState(30);

  const fetchMetrics = useCallback(async () => {
    try {
      const res = await fetch("/api/chinese-metrics");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: ChineseMetrics = await res.json();
      setMetrics(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch metrics");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    const timer = setInterval(fetchMetrics, refreshInterval * 1000);
    return () => clearInterval(timer);
  }, [fetchMetrics, refreshInterval]);

  // ------ Computed values ------
  const totalTokens = useMemo(
    () =>
      metrics?.tokenUsage.reduce((s, t) => s + t.tokens, 0) ?? 0,
    [metrics],
  );
  const totalCost = useMemo(
    () =>
      metrics?.tokenUsage.reduce((s, t) => s + t.costUsd, 0) ?? 0,
    [metrics],
  );
  const avgDecompose = useMemo(() => {
    const scores = metrics?.decomposeQuality ?? [];
    if (!scores.length) return 0;
    return scores.reduce((s, d) => s + d.score, 0) / scores.length;
  }, [metrics]);
  const avgConsistency = useMemo(() => {
    const scores = metrics?.fusionConsistency ?? [];
    if (!scores.length) return 0;
    return scores.reduce((s, f) => s + f.consistency, 0) / scores.length;
  }, [metrics]);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
        <span className="ml-3 text-gray-500 dark:text-gray-400">
          加载监控数据中...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 p-4 dark:border-red-800 dark:bg-red-900/20">
        <p className="text-red-600 dark:text-red-400">
          监控数据加载失败: {error}
        </p>
        <button
          onClick={fetchMetrics}
          className="mt-2 rounded bg-red-100 px-3 py-1 text-sm text-red-700 hover:bg-red-200 dark:bg-red-800 dark:text-red-300"
        >
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          中文智能体监控看板
        </h2>
        <div className="flex items-center gap-3">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-gray-200"
          >
            <option value={10}>10秒刷新</option>
            <option value={30}>30秒刷新</option>
            <option value={60}>60秒刷新</option>
          </select>
          <button
            onClick={fetchMetrics}
            className="rounded-lg bg-blue-500 px-4 py-1.5 text-sm text-white hover:bg-blue-600 transition-colors"
          >
            立即刷新
          </button>
        </div>
      </div>

      {/* Stat cards row */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          title="Token 消耗"
          value={totalTokens.toLocaleString()}
          subtitle={`费用 $${totalCost.toFixed(4)}`}
          trend={totalTokens > 10000 ? "up" : "neutral"}
        />
        <StatCard
          title="任务拆解质量"
          value={`${(avgDecompose * 100).toFixed(0)}分`}
          subtitle={avgDecompose > 0.8 ? "优秀" : avgDecompose > 0.6 ? "良好" : "待优化"}
          trend={avgDecompose > 0.8 ? "up" : avgDecompose < 0.6 ? "down" : "neutral"}
        />
        <StatCard
          title="模型融合一致性"
          value={`${(avgConsistency * 100).toFixed(0)}%`}
          subtitle={avgConsistency > 0.9 ? "高度一致" : "有待提升"}
          trend={avgConsistency > 0.9 ? "up" : avgConsistency < 0.7 ? "down" : "neutral"}
        />
        <StatCard
          title="子任务数"
          value={
            metrics?.decomposeQuality
              ? String(
                  metrics.decomposeQuality.reduce((s, d) => s + d.subtaskCount, 0),
                )
              : "—"
          }
          subtitle="累计拆解子任务"
        />
      </div>

      {/* Two-column layout */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column: Search & Fusion */}
        <div className="space-y-6">
          {/* Search engine stats */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">
              搜索引擎命中率
            </h3>
            {metrics?.searchEngines && metrics.searchEngines.length > 0 ? (
              <SearchEnginePies engines={metrics.searchEngines} />
            ) : (
              <p className="text-sm text-gray-400">暂无搜索数据</p>
            )}
          </div>

          {/* Fusion consistency trend */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">
              多模型融合一致性
            </h3>
            {metrics?.fusionConsistency && metrics.fusionConsistency.length > 0 ? (
              <div className="space-y-3">
                {metrics.fusionConsistency.slice(-5).map((f, i) => (
                  <ProgressBar
                    key={i}
                    label={`${f.strategy} — ${new Date(f.timestamp).toLocaleTimeString("zh-CN")}`}
                    value={f.consistency}
                    maxValue={1}
                    color={
                      f.consistency > 0.9
                        ? "bg-green-500"
                        : f.consistency > 0.7
                          ? "bg-yellow-500"
                          : "bg-red-500"
                    }
                  />
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无融合数据</p>
            )}
          </div>
        </div>

        {/* Right column: Token & Decompose */}
        <div className="space-y-6">
          {/* Token usage by provider */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">
              Token 消耗趋势 (按模型)
            </h3>
            {metrics?.tokenUsage && metrics.tokenUsage.length > 0 ? (
              <div className="flex items-end gap-2" style={{ height: "120px" }}>
                {/* Simple bar chart for recent token usage */}
                {Object.entries(
                  metrics.tokenUsage.slice(-10).reduce(
                    (acc, t) => {
                      acc[t.provider] = (acc[t.provider] || 0) + t.tokens;
                      return acc;
                    },
                    {} as Record<string, number>,
                  ),
                ).map(([provider, tokens], i) => {
                  const maxTokens = Math.max(
                    ...Object.values(
                      metrics.tokenUsage.slice(-10).reduce(
                        (acc, t) => {
                          acc[t.provider] = (acc[t.provider] || 0) + t.tokens;
                          return acc;
                        },
                        {} as Record<string, number>,
                      ),
                    ),
                    1,
                  );
                  const height = `${(tokens / maxTokens) * 100}%`;
                  const colors = ["bg-blue-500", "bg-green-500", "bg-purple-500", "bg-orange-500"];
                  return (
                    <div
                      key={provider}
                      className="flex flex-1 flex-col items-center justify-end"
                    >
                      <span className="mb-1 text-xs font-medium text-gray-600 dark:text-gray-300">
                        {tokens.toLocaleString()}
                      </span>
                      <div
                        className={`w-full rounded-t ${colors[i % colors.length]} opacity-80`}
                        style={{ height }}
                      />
                      <span className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                        {provider}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无 Token 数据</p>
            )}
          </div>

          {/* Decomposition quality */}
          <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300">
              任务拆解质量评分
            </h3>
            {metrics?.decomposeQuality && metrics.decomposeQuality.length > 0 ? (
              <div className="space-y-3">
                {metrics.decomposeQuality.slice(-5).map((d, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <div className="flex-1">
                      <ProgressBar
                        label={`${new Date(d.timestamp).toLocaleTimeString("zh-CN")} — ${d.subtaskCount}个子任务, 深度${d.dagDepth}`}
                        value={d.score}
                        maxValue={1}
                        color={
                          d.score > 0.8
                            ? "bg-green-500"
                            : d.score > 0.6
                              ? "bg-yellow-500"
                              : "bg-red-500"
                        }
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无拆解数据</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
