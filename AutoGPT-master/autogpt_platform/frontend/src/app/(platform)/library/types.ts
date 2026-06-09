import type { Icon } from "@phosphor-icons/react";

export interface LibraryTab {
  id: string;
  title: string;
  icon: Icon;
}

/** Agent execution status — drives StatusBadge visuals & filtering. */
export type AgentStatus =
  | "running"
  | "error"
  | "listening"
  | "scheduled"
  | "idle";

/** Derived health bucket for quick triage. */
export type AgentHealth = "good" | "attention" | "stale";

/** Real-time metadata that powers the Intelligence Layer features. */
export interface AgentStatusInfo {
  status: AgentStatus;
  health: AgentHealth;
  /** 0-100 progress for currently running agents. */
  progress: number | null;
  totalRuns: number;
  lastRunAt: string | null;
  lastError: string | null;
  /** ID of the currently active execution (when status is "running"). */
  activeExecutionID: string | null;
  monthlySpend: number;
  nextScheduledRun: string | null;
  triggerType: string | null;
}

/** Fleet-wide aggregate counts used by the Briefing Panel stats grid. */
export interface FleetSummary {
  running: number;
  error: number;
  completed: number;
  listening: number;
  scheduled: number;
  idle: number;
  /** Total spend for the current calendar month, in cents. */
  monthlySpend: number;
}

export type SitrepPriority =
  | "error"
  | "running"
  | "stale"
  | "success"
  | "listening"
  | "scheduled"
  | "idle";

export interface SitrepItemData {
  id: string;
  agentID: string;
  agentName: string;
  agentImageUrl?: string | null;
  executionID?: string;
  priority: SitrepPriority;
  message: string;
  status: AgentStatus;
}

/** Filter options for the agent filter dropdown. */
export type AgentStatusFilter =
  | "all"
  | "running"
  | "attention"
  | "completed"
  | "listening"
  | "scheduled"
  | "idle"
  | "healthy";

/** Vertical domain identifiers matching preset agent categories. */
export type DomainId =
  | "finance"
  | "law"
  | "rd"
  | "operations"
  | "education"
  | "healthcare"
  | "banking"
  | "agriculture"
  | "media"
  | "artdesign";

/** Configuration for a vertical domain skill chip. */
export interface DomainConfig {
  id: DomainId;
  label: string;
  englishLabel: string;
  icon: string;
}

/** Graph IDs of the 10 preset vertical domain agents — used for client-side filtering. */
export const DOMAIN_GRAPH_ID_MAP: Record<DomainId, string> = {
  finance: "a1b2c3d4-e5f6-4701-a801-b1c2d3e4f5a1",
  law: "a1b2c3d4-e5f6-4702-a802-b1c2d3e4f5a2",
  rd: "a1b2c3d4-e5f6-4703-a803-b1c2d3e4f5a3",
  operations: "a1b2c3d4-e5f6-4704-a804-b1c2d3e4f5a4",
  education: "a1b2c3d4-e5f6-4705-a805-b1c2d3e4f5a5",
  healthcare: "a1b2c3d4-e5f6-4706-a806-b1c2d3e4f5a6",
  banking: "a1b2c3d4-e5f6-4707-a807-b1c2d3e4f5a7",
  agriculture: "a1b2c3d4-e5f6-4708-a808-b1c2d3e4f5a8",
  media: "a1b2c3d4-e5f6-4709-a809-b1c2d3e4f5a9",
  artdesign: "a1b2c3d4-e5f6-4710-a810-b1c2d3e4f5a0",
};

/** All 10 vertical domain configurations for the DomainSkillPicker. */
export const DOMAINS: DomainConfig[] = [
  { id: "finance", label: "财务", englishLabel: "Finance", icon: "💰" },
  { id: "law", label: "法律", englishLabel: "Law", icon: "⚖️" },
  { id: "rd", label: "研发", englishLabel: "R&D", icon: "💻" },
  { id: "operations", label: "运营", englishLabel: "Operations", icon: "📊" },
  { id: "education", label: "教育", englishLabel: "Education", icon: "📚" },
  { id: "healthcare", label: "医疗", englishLabel: "Healthcare", icon: "🏥" },
  { id: "banking", label: "金融", englishLabel: "Banking", icon: "🏦" },
  { id: "agriculture", label: "农业", englishLabel: "Agriculture", icon: "🌾" },
  { id: "media", label: "媒体娱乐", englishLabel: "Media", icon: "🎬" },
  { id: "artdesign", label: "艺术设计", englishLabel: "Art & Design", icon: "🎨" },
];
