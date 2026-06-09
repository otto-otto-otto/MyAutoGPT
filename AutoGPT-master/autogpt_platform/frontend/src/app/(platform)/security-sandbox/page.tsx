"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Code2,
  FileSearch,
  Gauge,
  Loader2,
  RefreshCw,
  Send,
  Shield,
  ShieldAlert,
  ShieldCheck,
  ShieldX,
  Sparkles,
  TextSelect,
  XCircle,
} from "lucide-react";
import {
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RiskDetail {
  engine: string;
  decision: "approved" | "rejected" | "flagged";
  score: number;
  reason: string;
  matches: string[];
}

interface ReviewResult {
  approved: boolean;
  risks: RiskDetail[];
  summary: string;
  combined_score: number;
  reviewed_at: string;
}

interface ModelStatus {
  engine: string;
  loaded: boolean;
  version: string;
  model_size_bytes: number;
  last_trained: string;
}

interface Stats {
  total_reviews: number;
  approved: number;
  rejected: number;
  flagged: number;
  rejection_rate: number;
  recent_reviews: Array<{
    summary: string;
    score: number;
    approved: boolean;
    timestamp: string;
  }>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const API_BASE = typeof window !== "undefined" ? `${window.location.origin}/api/sandbox` : "";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const msg = (await res.text().catch(() => "")) || res.statusText;
    throw new Error(`HTTP ${res.status}: ${msg}`);
  }
  return res.json();
}

function decisionColor(d: "approved" | "rejected" | "flagged") {
  switch (d) {
    case "approved":
      return "text-emerald-600 bg-emerald-50 dark:bg-emerald-950 dark:text-emerald-400";
    case "rejected":
      return "text-red-600 bg-red-50 dark:bg-red-950 dark:text-red-400";
    case "flagged":
      return "text-amber-600 bg-amber-50 dark:bg-amber-950 dark:text-amber-400";
  }
}

function decisionIcon(d: "approved" | "rejected" | "flagged") {
  switch (d) {
    case "approved":
      return <ShieldCheck className="h-5 w-5 text-emerald-500" />;
    case "rejected":
      return <ShieldX className="h-5 w-5 text-red-500" />;
    case "flagged":
      return <ShieldAlert className="h-5 w-5 text-amber-500" />;
  }
}

// ---------------------------------------------------------------------------
// Page Component
// ---------------------------------------------------------------------------

export default function SecuritySandboxPage() {
  // State
  const [stats, setStats] = useState<Stats | null>(null);
  const [models, setModels] = useState<ModelStatus[]>([]);
  const [statsLoading, setStatsLoading] = useState(true);
  const [modelsLoading, setModelsLoading] = useState(true);

  // Review test state
  const [testMode, setTestMode] = useState<"text" | "code">("text");
  const [testInput, setTestInput] = useState("");
  const [testResult, setTestResult] = useState<ReviewResult | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState("");

  // Fetch helpers
  const loadStats = useCallback(async () => {
    setStatsLoading(true);
    const data = await fetchJson<Stats>(`${API_BASE}/stats`);
    setStats(data);
    setStatsLoading(false);
  }, []);

  const loadModels = useCallback(async () => {
    setModelsLoading(true);
    const data = await fetchJson<ModelStatus[]>(`${API_BASE}/models/status`);
    setModels(data);
    setModelsLoading(false);
  }, []);

  useEffect(() => {
    loadStats();
    loadModels();
  }, [loadStats, loadModels]);

  // Submit review
  const handleReview = useCallback(async () => {
    if (!testInput.trim()) return;
    setTestLoading(true);
    setTestError("");
    setTestResult(null);
    const endpoint = testMode === "code" ? `${API_BASE}/review/code` : `${API_BASE}/review/text`;
    const body = testMode === "code" ? { code: testInput } : { text: testInput };
    const data = await fetchJson<ReviewResult>(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).catch((err: Error) => {
      setTestError(err.message);
      return null;
    });
    if (data) {
      setTestResult(data);
      loadStats(); // refresh stats after review
    }
    setTestLoading(false);
  }, [testInput, testMode, loadStats]);

  // Chart data
  const pieData = useMemo(() => {
    if (!stats) return [];
    return [
      { name: "Approved", value: stats.approved, color: "#22c55e" },
      { name: "Flagged", value: stats.flagged, color: "#f59e0b" },
      { name: "Rejected", value: stats.rejected, color: "#ef4444" },
    ];
  }, [stats]);

  const engineCount = models.length;
  const loadedCount = models.filter((m) => m.loaded).length;

  return (
    <div className="mx-auto max-w-7xl space-y-6 px-4 py-8">
      {/* ---- Header ---- */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-gray-900 dark:text-gray-100">
            Security Sandbox
          </h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Built-in content moderation &amp; code security review powered by self-trained ML models
          </p>
        </div>
        <button
          onClick={() => { loadStats(); loadModels(); }}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition-all hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-750"
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* ---- Stats Cards ---- */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Reviews */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-100 dark:bg-blue-900/40">
              <FileSearch className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Total Reviews</p>
              {statsLoading ? (
                <Loader2 className="mt-1 h-4 w-4 animate-spin text-gray-400" />
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {stats?.total_reviews ?? 0}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Rejection Rate */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-red-100 dark:bg-red-900/40">
              <XCircle className="h-5 w-5 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Rejection Rate</p>
              {statsLoading ? (
                <Loader2 className="mt-1 h-4 w-4 animate-spin text-gray-400" />
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {stats ? `${(stats.rejection_rate * 100).toFixed(1)}%` : "0%"}
                </p>
              )}
            </div>
          </div>
        </div>

        {/* ML Models */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-100 dark:bg-purple-900/40">
              <Sparkles className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">ML Models</p>
              {modelsLoading ? (
                <Loader2 className="mt-1 h-4 w-4 animate-spin text-gray-400" />
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {loadedCount}/{engineCount} loaded
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Flagged Today */}
        <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm transition-shadow hover:shadow-md dark:border-gray-700 dark:bg-gray-900">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-100 dark:bg-amber-900/40">
              <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400">Flagged</p>
              {statsLoading ? (
                <Loader2 className="mt-1 h-4 w-4 animate-spin text-gray-400" />
              ) : (
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {stats?.flagged ?? 0}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ---- Two-Column: Review Test + Chart ---- */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-5">
        {/* ---- Real-time Testing ---- */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm lg:col-span-3 dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
            <Activity className="h-5 w-5 text-blue-500" />
            Real-time Content Review
          </h2>

          {/* Mode toggle */}
          <div className="mb-4 flex gap-2">
            <button
              onClick={() => { setTestMode("text"); setTestResult(null); setTestError(""); }}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                testMode === "text"
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400"
              }`}
            >
              <TextSelect className="h-4 w-4" /> Text
            </button>
            <button
              onClick={() => { setTestMode("code"); setTestResult(null); setTestError(""); }}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
                testMode === "code"
                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                  : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400"
              }`}
            >
              <Code2 className="h-4 w-4" /> Code
            </button>
          </div>

          {/* Input */}
          <textarea
            value={testInput}
            onChange={(e) => setTestInput(e.target.value)}
            placeholder={
              testMode === "text"
                ? "Enter text to scan for risky or spam content patterns..."
                : "Paste code to scan for security vulnerabilities..."
            }
            rows={6}
            className="w-full resize-none rounded-lg border border-gray-200 bg-gray-50 p-3 text-sm text-gray-900 placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-100 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-100 dark:placeholder-gray-500"
          />

          {/* Submit Button */}
          <button
            onClick={handleReview}
            disabled={testLoading || !testInput.trim()}
            className="mt-3 inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {testLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {testLoading ? "Analyzing..." : "Review Content"}
          </button>

          {testError && (
            <div className="mt-3 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
              {testError}
            </div>
          )}

          {/* Result Panel */}
          {testResult && (
            <div className="mt-5 space-y-3 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
              {/* Overall verdict */}
              <div className="flex items-center gap-3">
                {testResult.approved ? (
                  <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                ) : (
                  <AlertTriangle className="h-6 w-6 text-red-500" />
                )}
                <div>
                  <p
                    className={`text-base font-semibold ${
                      testResult.approved ? "text-emerald-700 dark:text-emerald-400" : "text-red-700 dark:text-red-400"
                    }`}
                  >
                    {testResult.summary}
                  </p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Combined risk score: {(testResult.combined_score * 100).toFixed(1)}%
                  </p>
                </div>
              </div>

              {/* Score bar */}
              <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    testResult.combined_score > 0.7
                      ? "bg-red-500"
                      : testResult.combined_score > 0.35
                      ? "bg-amber-500"
                      : "bg-emerald-500"
                  }`}
                  style={{ width: `${testResult.combined_score * 100}%` }}
                />
              </div>

              {/* Per-engine details */}
              {testResult.risks.map((risk, i) => (
                <div
                  key={i}
                  className="flex items-start gap-3 rounded-md border border-gray-200 bg-white p-3 dark:border-gray-600 dark:bg-gray-800"
                >
                  {decisionIcon(risk.decision)}
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${decisionColor(risk.decision)}`}>
                        {risk.decision.toUpperCase()}
                      </span>
                      <span className="text-sm font-medium capitalize text-gray-700 dark:text-gray-300">
                        {risk.engine.replace("_", " ")}
                      </span>
                      <span className="text-xs text-gray-400">
                        score: {(risk.score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">
                      {risk.reason}
                    </p>
                    {risk.matches.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {risk.matches.map((m, j) => (
                          <span
                            key={j}
                            className="rounded bg-gray-100 px-2 py-0.5 text-[11px] text-gray-600 dark:bg-gray-700 dark:text-gray-300"
                          >
                            {m}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ---- Pie Chart ---- */}
        <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm lg:col-span-2 dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
            <Gauge className="h-5 w-5 text-purple-500" />
            Review Distribution
          </h2>
          {stats && stats.total_reviews > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {pieData.map((entry, idx) => (
                    <Cell key={idx} fill={entry.color} strokeWidth={0} />
                  ))}
                </Pie>
                <Tooltip />
                <Legend
                  verticalAlign="bottom"
                  height={36}
                  formatter={(value: string) => (
                    <span className="text-xs text-gray-600 dark:text-gray-400">{value}</span>
                  )}
                />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <p className="py-12 text-center text-sm text-gray-400 dark:text-gray-500">
              No review data yet. Submit a review to see stats.
            </p>
          )}
        </div>
      </div>

      {/* ---- Model Status Panel ---- */}
      <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
          <Shield className="h-5 w-5 text-indigo-500" />
          ML Model Status
        </h2>
        {modelsLoading ? (
          <div className="flex items-center gap-3 py-8 text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading model status...
          </div>
        ) : models.length === 0 ? (
          <p className="py-4 text-sm text-gray-400 dark:text-gray-500">
            No model data available. Models are trained during Docker build.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {models.map((model) => (
              <div
                key={model.engine}
                className={`rounded-lg border p-4 transition-colors ${
                  model.loaded
                    ? "border-emerald-200 bg-emerald-50/50 dark:border-emerald-800 dark:bg-emerald-950/30"
                    : "border-red-200 bg-red-50/50 dark:border-red-800 dark:bg-red-950/30"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold capitalize text-gray-900 dark:text-gray-100">
                    {model.engine.replace("_", " ")}
                  </span>
                  <span
                    className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${
                      model.loaded
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300"
                        : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
                    }`}
                  >
                    <span
                      className={`inline-block h-2 w-2 rounded-full ${
                        model.loaded ? "bg-emerald-500" : "bg-red-500"
                      }`}
                    />
                    {model.loaded ? "Loaded" : "Not Loaded"}
                  </span>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <div>
                    <span className="block text-[11px] uppercase tracking-wider text-gray-400">Version</span>
                    <span className="font-medium text-gray-700 dark:text-gray-300">{model.version}</span>
                  </div>
                  <div>
                    <span className="block text-[11px] uppercase tracking-wider text-gray-400">Size</span>
                    <span className="font-medium text-gray-700 dark:text-gray-300">
                      {model.model_size_bytes > 0
                        ? `${(model.model_size_bytes / 1024).toFixed(1)} KB`
                        : "N/A"}
                    </span>
                  </div>
                  <div className="col-span-2">
                    <span className="block text-[11px] uppercase tracking-wider text-gray-400">Last Trained</span>
                    <span className="font-medium text-gray-700 dark:text-gray-300">
                      {model.last_trained
                        ? new Date(model.last_trained).toLocaleString()
                        : "N/A"}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ---- Recent Review Log ---- */}
      <div className="rounded-xl border border-gray-200 bg-white shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="flex items-center justify-between border-b border-gray-200 p-5 dark:border-gray-700">
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-gray-100">
            <Activity className="h-5 w-5 text-orange-500" />
            Recent Review Log
          </h2>
          <span className="text-xs text-gray-400 dark:text-gray-500">
            Last 20 reviews (in-memory, resets on restart)
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-gray-100 bg-gray-50 text-xs uppercase tracking-wider text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400">
              <tr>
                <th className="px-5 py-3 font-medium">Time</th>
                <th className="px-5 py-3 font-medium">Summary</th>
                <th className="px-5 py-3 font-medium">Score</th>
                <th className="px-5 py-3 font-medium">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
              {stats?.recent_reviews && stats.recent_reviews.length > 0 ? (
                stats.recent_reviews
                  .slice()
                  .reverse()
                  .map((entry, i) => (
                    <tr
                      key={i}
                      className="transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50"
                    >
                      <td className="whitespace-nowrap px-5 py-3 text-xs text-gray-500 dark:text-gray-400">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="max-w-xs truncate px-5 py-3 text-gray-700 dark:text-gray-300">
                        {entry.summary}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                            <div
                              className={`h-full rounded-full ${
                                entry.score > 0.7 ? "bg-red-500" : entry.score > 0.35 ? "bg-amber-500" : "bg-emerald-500"
                              }`}
                              style={{ width: `${entry.score * 100}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-400">{(entry.score * 100).toFixed(0)}%</span>
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <span
                          className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                            entry.approved
                              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300"
                              : "bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300"
                          }`}
                        >
                          {entry.approved ? "Approved" : "Blocked"}
                        </span>
                      </td>
                    </tr>
                  ))
              ) : (
                <tr>
                  <td colSpan={4} className="px-5 py-12 text-center text-sm text-gray-400 dark:text-gray-500">
                    No review history yet. Submit content above to see results here.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
