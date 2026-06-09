import { Key, storage } from "@/services/storage/local-storage";
import { create } from "zustand";
import { clearContentCache } from "./components/ArtifactPanel/components/useArtifactContent";
import { ORIGINAL_TITLE, parseSessionIDs } from "./helpers";

export interface DeleteTarget {
  id: string;
  title: string | null | undefined;
}

/**
 * A single workspace artifact surfaced in the copilot chat.
 *
 * Rendered by `ArtifactCard` (inline) and `ArtifactPanel` (preview pane).
 * Typically extracted from `workspace://<id>` URIs in assistant text parts
 * or from `FileUIPart` attachments; see `getMessageArtifacts` in
 * `ChatMessagesContainer/helpers.ts`.
 */
export interface ArtifactRef {
  /** Workspace file ID (matches the backend `WorkspaceFile.id`). */
  id: string;
  /** Human-visible filename, used as both title and download filename. */
  title: string;
  /** MIME type if known (from backend metadata or `workspace://id#mime`). */
  mimeType: string | null;
  /**
   * Fully-qualified URL the preview/download code will fetch from. Today
   * this is always the same-origin proxy path
   * `/api/proxy/api/workspace/files/{id}/download`.
   */
  sourceUrl: string;
  /**
   * Who produced the artifact — drives the origin badge color in
   * `ArtifactPanelHeader`. Derived from the emitting message's role.
   */
  origin: "agent" | "user-upload";
  /** Size in bytes if known — used by `classifyArtifact` for size gating. */
  sizeBytes?: number;
}

interface ArtifactPanelState {
  isOpen: boolean;
  isMinimized: boolean;
  isMaximized: boolean;
  width: number;
  activeArtifact: ArtifactRef | null;
  history: ArtifactRef[];
}

export const DEFAULT_PANEL_WIDTH = 600;

/** Autopilot response mode. */
export type CopilotMode = "extended_thinking" | "fast";

/** Per-request model selection: ``"provider:tier"`` compound string. */
export type CopilotLlmModel =
  | "deepseek:standard"
  | "deepseek:advanced"
  | "qwen:standard"
  | "qwen:advanced"
  | "ernie:standard"
  | "ernie:advanced";

export type CopilotProvider = "deepseek" | "qwen" | "ernie";
export type CopilotTier = "standard" | "advanced";

/** All valid model strings. */
export const VALID_COPILOT_MODELS: ReadonlySet<CopilotLlmModel> = new Set([
  "deepseek:standard",
  "deepseek:advanced",
  "qwen:standard",
  "qwen:advanced",
  "ernie:standard",
  "ernie:advanced",
]);

export const DEFAULT_COPILOT_MODEL: CopilotLlmModel = "deepseek:standard";

/** Parse a compound model string into provider and tier. */
export function parseModelString(
  model: string | null | undefined,
): { provider: CopilotProvider; tier: CopilotTier } {
  if (!model || !VALID_COPILOT_MODELS.has(model as CopilotLlmModel)) {
    return { provider: "deepseek", tier: "standard" };
  }
  const [provider, tier] = model.split(":") as [CopilotProvider, CopilotTier];
  return { provider, tier };
}

const isClient = typeof window !== "undefined";

function getPersistedWidth(): number {
  if (!isClient) return DEFAULT_PANEL_WIDTH;
  const saved = storage.get(Key.COPILOT_ARTIFACT_PANEL_WIDTH);
  if (saved) {
    const parsed = parseInt(saved, 10);
    // Match the drag-handle clamp so a stale/corrupt value can't open the
    // panel wider than 85% of the viewport.
    const maxWidth = window.innerWidth * 0.85;
    if (!isNaN(parsed) && parsed >= 320) {
      return Math.min(parsed, maxWidth);
    }
  }
  return DEFAULT_PANEL_WIDTH;
}

let panelWidthPersistTimer: ReturnType<typeof setTimeout> | null = null;
function schedulePanelWidthPersist(width: number) {
  if (!isClient) return;
  if (panelWidthPersistTimer) clearTimeout(panelWidthPersistTimer);
  panelWidthPersistTimer = setTimeout(() => {
    storage.set(Key.COPILOT_ARTIFACT_PANEL_WIDTH, String(width));
    panelWidthPersistTimer = null;
  }, 200);
}

function persistCompletedSessions(ids: Set<string>) {
  if (!isClient) return;
  try {
    if (ids.size === 0) {
      storage.clean(Key.COPILOT_COMPLETED_SESSIONS);
    } else {
      storage.set(Key.COPILOT_COMPLETED_SESSIONS, JSON.stringify([...ids]));
    }
  } catch {
    // Keep in-memory state authoritative if persistence is unavailable
  }
}

interface CopilotUIState {
  /** Prompt extracted from URL hash (e.g. /copilot#prompt=...) for input prefill. */
  initialPrompt: string | null;
  setInitialPrompt: (prompt: string | null) => void;

  sessionToDelete: DeleteTarget | null;
  setSessionToDelete: (target: DeleteTarget | null) => void;

  isDrawerOpen: boolean;
  setDrawerOpen: (open: boolean) => void;

  isSearchOpen: boolean;
  setSearchOpen: (open: boolean) => void;

  completedSessionIDs: Set<string>;
  addCompletedSession: (id: string) => void;
  clearCompletedSession: (id: string) => void;
  clearAllCompletedSessions: () => void;

  isNotificationsEnabled: boolean;
  setNotificationsEnabled: (enabled: boolean) => void;

  isSoundEnabled: boolean;
  toggleSound: () => void;

  showNotificationDialog: boolean;
  setShowNotificationDialog: (show: boolean) => void;

  // Artifact panel
  artifactPanel: ArtifactPanelState;
  openArtifact: (ref: ArtifactRef) => void;
  closeArtifactPanel: () => void;
  resetArtifactPanel: () => void;
  minimizeArtifactPanel: () => void;
  maximizeArtifactPanel: () => void;
  restoreArtifactPanel: () => void;
  setArtifactPanelWidth: (width: number) => void;
  goBackArtifact: () => void;

  // Card-based auto-open: ArtifactCard registers itself on mount, the store
  // decides whether to auto-open. Much simpler than message-scanning.
  registerArtifactForAutoOpen: (ref: ArtifactRef) => void;
  setAutoOpenReady: () => void;
  markUserClosedForAutoOpen: () => void;
  resetAutoOpenState: () => void;

  /** Autopilot mode: 'extended_thinking' (default) or 'fast'. */
  copilotChatMode: CopilotMode;
  setCopilotChatMode: (mode: CopilotMode) => void;

  /** Model tier: 'standard' (default) or 'advanced' (highest-capability). */
  copilotLlmModel: CopilotLlmModel;
  setCopilotLlmModel: (model: CopilotLlmModel) => void;

  /** Developer dry-run mode: sessions created with dry_run=true. */
  isDryRun: boolean;
  setIsDryRun: (enabled: boolean) => void;

  /** Selected vertical domain skill (null = none / default copilot). */
  selectedDomain: DomainId | null;
  setSelectedDomain: (domain: DomainId | null) => void;

  clearCopilotLocalData: () => void;
}

/** Vertical domain identifiers matching preset agents. */
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

/** Domain display metadata for the skill picker UI. */
export interface DomainMeta {
  id: DomainId;
  label: string;
  icon: string;
}

export const VERTICAL_DOMAINS: DomainMeta[] = [
  { id: "finance", label: "财务", icon: "💰" },
  { id: "law", label: "法律", icon: "⚖️" },
  { id: "rd", label: "研发", icon: "💻" },
  { id: "operations", label: "运营", icon: "📊" },
  { id: "education", label: "教育", icon: "📚" },
  { id: "healthcare", label: "医疗", icon: "🏥" },
  { id: "banking", label: "金融", icon: "🏦" },
  { id: "agriculture", label: "农业", icon: "🌾" },
  { id: "media", label: "媒体娱乐", icon: "🎬" },
  { id: "artdesign", label: "艺术设计", icon: "🎨" },
];

/** Compact vertical-domain system prompts sent as ``context`` with each request. */
export const VERTICAL_DOMAIN_PROMPTS: Record<DomainId, string> = {
  finance: "你是一位资深财务分析专家，精通企业财务报表分析（资产负债表/利润表/现金流量表）、公司估值建模（DCF/可比公司法）、预算编制与成本控制、税务筹划与合规分析、投资可行性研究。",
  law: "你是一位资深法律研究顾问，精通中国法律法规检索与解读、司法案例分析与判例研究、合同条款审查与风险识别、企业合规体系建设、知识产权法律研究、劳动用工法律风险分析。",
  rd: "你是一位资深技术架构师，精通系统架构设计与评审、技术选型评估与对比分析、代码质量审查与重构建议、性能瓶颈诊断与优化方案、系统安全审计与API设计。",
  operations: "你是一位资深运营管理专家，精通业务流程梳理与优化、供应链管理与物流分析、用户运营与增长策略、数据运营分析与KPI体系设计、项目管理与敏捷实践、竞品分析与市场研究。",
  education: "你是一位资深教育研究专家，精通课程体系设计与教学大纲编写、教学方法对比研究、学习效果评估与试题设计、教育政策分析与比较教育研究、学术研究指导与论文写作规范。",
  healthcare: "你是一位资深医疗健康研究顾问，精通医学文献检索与循证分析、临床研究设计与方法学评估、疾病流行病学数据解读与趋势分析、药物信息查询与药理学分析、公共卫生政策分析与健康管理。",
  banking: "你是一位资深金融行业研究分析师，精通宏观经济形势分析与预测、行业景气度研究与产业链分析、投资策略与大类资产配置、风险管理与压力测试、金融产品评估与创新研究、货币政策解读。",
  agriculture: "你是一位资深农业研究专家，精通作物种植技术与品种选择、畜牧养殖管理、渔业与水产养殖技术、土壤科学与土地管理、农业政策解读、智慧农业技术分析、农产品市场分析与价格预测。",
  media: "你是一位资深媒体与娱乐行业研究专家，精通内容创作策划与IP开发、媒体传播策略与公关方案、影视剧集分析评估、社交媒体运营策略、数字营销分析、受众画像与用户研究、娱乐产业趋势分析。",
  artdesign: "你是一位资深艺术与设计研究顾问，精通视觉设计策略与品牌全案、UI/UX设计评审与启发式评估、品牌VIS系统设计、艺术史分析与风格识别、设计趋势研究与预测、创意方法学与设计思维、工业设计与产品美学分析。",
}

// ── Card-based auto-open tracking ───────────────────────────────────
// Module-level state — not in Zustand to avoid unnecessary re-renders.
// ArtifactCard calls registerArtifactForAutoOpen on mount; the store
// decides whether to auto-open based on these flags.
const _autoOpenKnownIds = new Set<string>();
let _autoOpenReady = false;
let _autoOpenUserClosed = false;

export const useCopilotUIStore = create<CopilotUIState>((set, get) => ({
  initialPrompt: null,
  setInitialPrompt: (prompt) => set({ initialPrompt: prompt }),

  sessionToDelete: null,
  setSessionToDelete: (target) => set({ sessionToDelete: target }),

  isDrawerOpen: false,
  setDrawerOpen: (open) => set({ isDrawerOpen: open }),

  isSearchOpen: false,
  setSearchOpen: (open) => set({ isSearchOpen: open }),

  completedSessionIDs: isClient
    ? parseSessionIDs(storage.get(Key.COPILOT_COMPLETED_SESSIONS))
    : new Set(),
  addCompletedSession: (id) =>
    set((state) => {
      const next = new Set(state.completedSessionIDs);
      next.add(id);
      persistCompletedSessions(next);
      return { completedSessionIDs: next };
    }),
  clearCompletedSession: (id) =>
    set((state) => {
      const next = new Set(state.completedSessionIDs);
      next.delete(id);
      persistCompletedSessions(next);
      return { completedSessionIDs: next };
    }),
  clearAllCompletedSessions: () => {
    persistCompletedSessions(new Set());
    set({ completedSessionIDs: new Set<string>() });
  },

  isNotificationsEnabled:
    isClient &&
    storage.get(Key.COPILOT_NOTIFICATIONS_ENABLED) === "true" &&
    typeof Notification !== "undefined" &&
    Notification.permission === "granted",
  setNotificationsEnabled: (enabled) => {
    storage.set(Key.COPILOT_NOTIFICATIONS_ENABLED, String(enabled));
    set({ isNotificationsEnabled: enabled });
  },

  isSoundEnabled:
    !isClient || storage.get(Key.COPILOT_SOUND_ENABLED) !== "false",
  toggleSound: () =>
    set((state) => {
      const next = !state.isSoundEnabled;
      storage.set(Key.COPILOT_SOUND_ENABLED, String(next));
      return { isSoundEnabled: next };
    }),

  showNotificationDialog: false,
  setShowNotificationDialog: (show) => set({ showNotificationDialog: show }),

  // Artifact panel
  artifactPanel: {
    isOpen: false,
    isMinimized: false,
    isMaximized: false,
    width: getPersistedWidth(),
    activeArtifact: null,
    history: [],
  },
  openArtifact: (ref) =>
    set((state) => {
      const { activeArtifact, history: prevHistory } = state.artifactPanel;
      const topOfHistory = prevHistory[prevHistory.length - 1];
      const isReturningToTop = topOfHistory?.id === ref.id;
      const shouldPushHistory =
        state.artifactPanel.isOpen &&
        activeArtifact != null &&
        activeArtifact.id !== ref.id;
      const MAX_HISTORY = 25;
      const history = isReturningToTop
        ? prevHistory.slice(0, -1)
        : shouldPushHistory
          ? [...prevHistory, activeArtifact!].slice(-MAX_HISTORY)
          : prevHistory;
      return {
        artifactPanel: {
          ...state.artifactPanel,
          isOpen: true,
          isMinimized: false,
          activeArtifact: ref,
          history,
        },
      };
    }),
  closeArtifactPanel: () =>
    set((state) => ({
      artifactPanel: {
        ...state.artifactPanel,
        isOpen: false,
        isMinimized: false,
        history: [],
      },
    })),
  resetArtifactPanel: () =>
    set((state) => ({
      artifactPanel: {
        ...state.artifactPanel,
        isOpen: false,
        isMinimized: false,
        isMaximized: false,
        activeArtifact: null,
        history: [],
      },
    })),
  minimizeArtifactPanel: () =>
    set((state) => ({
      artifactPanel: { ...state.artifactPanel, isMinimized: true },
    })),
  maximizeArtifactPanel: () =>
    set((state) => ({
      artifactPanel: {
        ...state.artifactPanel,
        isMaximized: true,
        isMinimized: false,
      },
    })),
  restoreArtifactPanel: () =>
    set((state) => ({
      artifactPanel: {
        ...state.artifactPanel,
        isMaximized: false,
        isMinimized: false,
      },
    })),
  setArtifactPanelWidth: (width) => {
    schedulePanelWidthPersist(width);
    set((state) => ({
      artifactPanel: {
        ...state.artifactPanel,
        width,
        isMaximized: false,
      },
    }));
  },
  goBackArtifact: () =>
    set((state) => {
      const { history } = state.artifactPanel;
      if (history.length === 0) return state;
      const previous = history[history.length - 1];
      return {
        artifactPanel: {
          ...state.artifactPanel,
          activeArtifact: previous,
          history: history.slice(0, -1),
        },
      };
    }),

  // ── Card-based auto-open actions ─────────────────────────────────
  registerArtifactForAutoOpen: (ref) => {
    if (_autoOpenKnownIds.has(ref.id)) {
      // Already known — upgrade activeArtifact metadata if this ref is richer
      // (e.g. file-part ref with real MIME replacing text-extracted null MIME).
      const active = get().artifactPanel.activeArtifact;
      if (active?.id === ref.id && !active.mimeType && ref.mimeType) {
        set((state) => ({
          artifactPanel: { ...state.artifactPanel, activeArtifact: ref },
        }));
      }
      return;
    }
    _autoOpenKnownIds.add(ref.id);
    if (!_autoOpenReady || _autoOpenUserClosed || ref.origin !== "agent")
      return;
    get().openArtifact(ref);
  },
  setAutoOpenReady: () => {
    _autoOpenReady = true;
  },
  markUserClosedForAutoOpen: () => {
    _autoOpenUserClosed = true;
  },
  resetAutoOpenState: () => {
    _autoOpenKnownIds.clear();
    _autoOpenReady = false;
    _autoOpenUserClosed = false;
  },

  copilotChatMode: (() => {
    const saved = isClient ? storage.get(Key.COPILOT_MODE) : null;
    return saved === "fast" ? "fast" : "extended_thinking";
  })(),
  setCopilotChatMode: (mode) => {
    storage.set(Key.COPILOT_MODE, mode);
    set({ copilotChatMode: mode });
  },

  copilotLlmModel: (() => {
    const saved = isClient ? storage.get(Key.COPILOT_MODEL) : null;
    if (
      saved &&
      VALID_COPILOT_MODELS.has(saved as CopilotLlmModel)
    ) {
      return saved as CopilotLlmModel;
    }
    return DEFAULT_COPILOT_MODEL;
  })(),
  setCopilotLlmModel: (model) => {
    if (!VALID_COPILOT_MODELS.has(model as CopilotLlmModel)) return;
    storage.set(Key.COPILOT_MODEL, model);
    set({ copilotLlmModel: model });
  },

  isDryRun: isClient && storage.get(Key.COPILOT_DRY_RUN) === "true",
  setIsDryRun: (enabled) => {
    if (enabled) {
      storage.set(Key.COPILOT_DRY_RUN, "true");
    } else {
      storage.clean(Key.COPILOT_DRY_RUN);
    }
    set({ isDryRun: enabled });
  },

  selectedDomain: (() => {
    const saved = isClient ? storage.get(Key.COPILOT_DOMAIN) : null;
    return saved as DomainId | null;
  })(),
  setSelectedDomain: (domain) => {
    if (domain) {
      storage.set(Key.COPILOT_DOMAIN, domain);
    } else {
      storage.clean(Key.COPILOT_DOMAIN);
    }
    set({ selectedDomain: domain });
  },

  clearCopilotLocalData: () => {
    clearContentCache();
    _autoOpenKnownIds.clear();
    _autoOpenReady = false;
    _autoOpenUserClosed = false;
    storage.clean(Key.COPILOT_NOTIFICATIONS_ENABLED);
    storage.clean(Key.COPILOT_SOUND_ENABLED);
    storage.clean(Key.COPILOT_NOTIFICATION_BANNER_DISMISSED);
    storage.clean(Key.COPILOT_NOTIFICATION_DIALOG_DISMISSED);
    storage.clean(Key.COPILOT_ARTIFACT_PANEL_WIDTH);
    storage.clean(Key.COPILOT_COMPLETED_SESSIONS);
    storage.clean(Key.COPILOT_DRY_RUN);
    storage.clean(Key.COPILOT_MODE);
    storage.clean(Key.COPILOT_MODEL);
    storage.clean(Key.COPILOT_DOMAIN);
    set({
      completedSessionIDs: new Set<string>(),
      isSearchOpen: false,
      isNotificationsEnabled: false,
      isSoundEnabled: true,
      artifactPanel: {
        isOpen: false,
        isMinimized: false,
        isMaximized: false,
        width: DEFAULT_PANEL_WIDTH,
        activeArtifact: null,
        history: [],
      },
      copilotChatMode: "extended_thinking",
      copilotLlmModel: DEFAULT_COPILOT_MODEL,
      isDryRun: false,
      selectedDomain: null,
    });
    if (isClient) {
      document.title = ORIGINAL_TITLE;
    }
  },
}));
