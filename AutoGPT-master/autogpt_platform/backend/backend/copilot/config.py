"""Configuration management for chat system (Chinese LLM edition).

Uses DeepSeek / Qianfan / DashScope instead of Anthropic / OpenAI.
Claude Agent SDK path is permanently disabled.
"""

import os
from typing import Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

from backend.blocks.llm import LlmModel

# Supported web search backends for the copilot ``web_search`` tool.
SearchProvider = Literal["ddgs", "tavily", "serper"]

# DeepSeek base URL for OpenAI-compatible API.
DEEPSEEK_OPENAI_COMPAT_BASE_URL = "https://api.deepseek.com/v1"


def _host_matches(base_url: str | None, suffix: str) -> bool:
    """True when ``base_url``'s parsed hostname equals or ends with
    ``.suffix``."""
    if not base_url:
        return False
    host = (urlparse(base_url).hostname or "").lower()
    suffix = suffix.lower()
    return host == suffix or host.endswith("." + suffix)

# Per-request routing mode for a single chat turn.
# - 'fast': route to the baseline OpenAI-compatible path with the cheaper model.
# - 'extended_thinking': route to the Claude Agent SDK path with the default
#   (opus) model.
# ``None`` means "no override"; the server falls back to the Claude Code
# subscription flag → LaunchDarkly COPILOT_SDK → config.use_claude_agent_sdk.
CopilotMode = Literal["fast", "extended_thinking"]

# Per-request model selection: ``"provider:tier"`` compound string.
# - ``"deepseek:standard"`` / ``"deepseek:advanced"`` — DeepSeek
# - ``"qwen:standard"`` / ``"qwen:advanced"`` — Qwen (DashScope)
# - ``"ernie:standard"`` / ``"ernie:advanced"`` — ERNIE (Qianfan)
# Legacy bare ``"standard"`` / ``"advanced"`` are accepted for backward
# compatibility and mapped to deepseek internally.
# None means no preference — falls through to LD per-user targeting, then config.
CopilotLlmModel = Literal[
    "standard", "advanced",  # legacy backward compat
    "deepseek:standard", "deepseek:advanced",
    "qwen:standard", "qwen:advanced",
    "ernie:standard", "ernie:advanced",
]


class ChatConfig(BaseSettings):
    """Configuration for the chat system."""

    # Chat model tiers — a 2×2 of (path, tier).  ``path`` = ``CopilotMode``
    # (``"fast"`` → baseline OpenAI-compat / any OpenRouter model;
    # ``"extended_thinking"`` → Claude Agent SDK, Anthropic-only CLI).
    # ``tier`` = ``CopilotLlmModel`` (``"standard"`` / ``"advanced"``).
    # Each cell has its own config so the two paths can evolve
    # independently (cheap provider on baseline, Anthropic on SDK) at each
    # tier without conflating one path's needs with the other's constraint.
    #
    # Historical env var names (``CHAT_MODEL`` / ``CHAT_ADVANCED_MODEL`` /
    # ``CHAT_FAST_MODEL``) are preserved via ``validation_alias`` so
    # existing deployments continue to override the same effective cell.
    fast_standard_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices(
            "CHAT_FAST_STANDARD_MODEL",
            "CHAT_FAST_MODEL",
        ),
        description="Baseline path, 'standard' / ``None`` tier. Default is "
        "DeepSeek V3 (deepseek-chat) via direct API.",
    )
    fast_advanced_model: str = Field(
        default="deepseek-reasoner",
        validation_alias=AliasChoices("CHAT_FAST_ADVANCED_MODEL"),
        description="Baseline path, 'advanced' tier. Default is DeepSeek R1.",
    )
    thinking_standard_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices(
            "CHAT_THINKING_STANDARD_MODEL",
            "CHAT_MODEL",
        ),
        description="SDK path (disabled). Kept for backward compat; "
        "defaults to deepseek-chat.",
    )
    thinking_advanced_model: str = Field(
        default="deepseek-reasoner",
        validation_alias=AliasChoices(
            "CHAT_THINKING_ADVANCED_MODEL",
            "CHAT_ADVANCED_MODEL",
        ),
        description="SDK path (disabled). Kept for backward compat; "
        "defaults to deepseek-reasoner.",
    )
    fast_deepseek_model: str = Field(
        default="deepseek-chat",
        validation_alias=AliasChoices("CHAT_FAST_DEEPSEEK_MODEL"),
        description="Baseline DeepSeek tier default model.",
    )
    thinking_deepseek_model: str = Field(
        default="deepseek-reasoner",
        validation_alias=AliasChoices("CHAT_THINKING_DEEPSEEK_MODEL"),
        description="DeepSeek reasoning tier default model.",
    )
    # --- Qwen (DashScope / 通义千问) model tiers ---
    qwen_standard_model: str = Field(
        default="qwen-plus",
        validation_alias=AliasChoices("CHAT_QWEN_STANDARD_MODEL"),
        description="Qwen Balanced tier. Default is qwen-plus.",
    )
    qwen_advanced_model: str = Field(
        default="qwen-max",
        validation_alias=AliasChoices("CHAT_QWEN_ADVANCED_MODEL"),
        description="Qwen Advanced tier. Default is qwen-max.",
    )
    # --- ERNIE (Qianfan / 文心一言) model tiers ---
    ernie_standard_model: str = Field(
        default="ernie-speed-128k",
        validation_alias=AliasChoices("CHAT_ERNIE_STANDARD_MODEL"),
        description="ERNIE Balanced tier. Default is ernie-speed-128k.",
    )
    ernie_advanced_model: str = Field(
        default="ernie-4.0-turbo-128k",
        validation_alias=AliasChoices("CHAT_ERNIE_ADVANCED_MODEL"),
        description="ERNIE Advanced tier. Default is ernie-4.0-turbo-128k.",
    )
    title_model: str = Field(
        default="deepseek-chat",
        description="Model for generating session titles (fast/cheap). "
        "Defaults to deepseek-chat.",
    )
    simulation_model: str = Field(
        default=LlmModel.DEEPSEEK_V4.value,
        description="Model for dry-run block simulation. Defaults to "
        "deepseek-chat (OpenAI-compatible, JSON mode supported).",
    )
    api_key: str | None = Field(default=None, description="DeepSeek API key")
    base_url: str | None = Field(
        default=DEEPSEEK_OPENAI_COMPAT_BASE_URL,
        description="Base URL for API (DeepSeek OpenAI-compatible endpoint)",
    )

    # Auxiliary client credentials — used for non-Anthropic models (title
    # generation, simulator, builder helpers).  Kept independent of the
    # main client so flipping ``use_openrouter=False`` (main → direct
    # Anthropic) does not break aux calls that need OpenAI / Google / etc.
    # via OpenRouter.  Default to OpenRouter; fall back to the main
    # ``api_key`` / ``base_url`` when unset (preserves current behaviour
    # for deployments that haven't split the keys yet).
    aux_api_key: str | None = Field(
        default=None,
        description="API key for auxiliary models (title, builder helpers). "
        "Kept separate from ``api_key`` so direct-Anthropic main mode does not "
        "break non-Anthropic aux models. Falls back to OPEN_ROUTER_API_KEY / "
        "``api_key`` when unset.",
    )
    aux_base_url: str | None = Field(
        default=None,
        description="Base URL for auxiliary models. Falls back to ``base_url`` "
        "when unset (i.e. OpenRouter).",
    )

    # Session TTL Configuration - 12 hours
    session_ttl: int = Field(default=43200, description="Session TTL in seconds")

    max_agent_runs: int = Field(default=30, description="Maximum number of agent runs")
    max_agent_schedules: int = Field(
        default=30, description="Maximum number of agent schedules"
    )

    # Stream registry configuration for SSE reconnection
    stream_ttl: int = Field(
        default=3600,
        description="TTL in seconds for stream data in Redis (1 hour)",
    )
    stream_lock_ttl: int = Field(
        default=300,
        description="TTL in seconds for stream lock (5 minutes). Increased from "
        "2 min to tolerate long DeepSeek R1 reasoning turns.",
    )
    stream_max_length: int = Field(
        default=10000,
        description="Maximum number of messages to store per stream",
    )

    # Redis key prefixes for stream registry
    session_meta_prefix: str = Field(
        default="chat:task:meta:",
        description="Prefix for session metadata hash keys",
    )
    turn_stream_prefix: str = Field(
        default="chat:stream:",
        description="Prefix for turn message stream keys",
    )

    # Langfuse Prompt Management Configuration
    # Note: Langfuse credentials are in Settings().secrets (settings.py)
    langfuse_prompt_name: str = Field(
        default="CoPilot Prompt",
        description="Name of the prompt in Langfuse to fetch",
    )
    langfuse_prompt_cache_ttl: int = Field(
        default=300,
        description="Cache TTL in seconds for Langfuse prompt (0 to disable caching)",
    )

    # Rate limiting — cost-based limits per day and per week, stored in
    # microdollars (1 USD = 1_000_000).  The counter tracks the real
    # generation cost reported by the provider (OpenRouter ``usage.cost``
    # or Claude Agent SDK ``total_cost_usd``), so cache discounts and
    # cross-model price differences are already reflected — no token
    # weighting or model multiplier is applied on top.
    # Checked at the HTTP layer (routes.py) before each turn.
    #
    # These are base limits for the FREE tier.  Higher tiers (PRO, BUSINESS,
    # ENTERPRISE) multiply these by their tier multiplier (see
    # rate_limit.TIER_MULTIPLIERS).  User tier is stored in the
    # User.subscriptionTier DB column and resolved inside
    # get_global_rate_limits().
    #
    # These defaults act as the ceiling when LaunchDarkly is unreachable;
    # the live per-tier values come from the COPILOT_*_COST_LIMIT flags.
    daily_cost_limit_microdollars: int = Field(
        default=1_000_000,
        description="Max cost per day in microdollars, resets at midnight UTC. "
        "0 means no spend allowed (will block); there is no unlimited tier.",
    )
    weekly_cost_limit_microdollars: int = Field(
        default=5_000_000,
        description="Max cost per week in microdollars, resets Monday 00:00 UTC. "
        "0 means no spend allowed (will block); there is no unlimited tier.",
    )

    # Token-based rate limiting — daily and weekly token quotas for
    # copilot conversations.  These replace the cost-based (microdollar)
    # limits for user-facing rate limiting.  0 disables token-based
    # limiting (falls back to cost-based only).
    daily_token_limit: int = Field(
        default=1_000_000,
        ge=0,
        description="Max tokens per day, resets at midnight UTC. "
        "0 disables token-based daily limiting.",
    )
    weekly_token_limit: int = Field(
        default=5_000_000,
        ge=0,
        description="Max tokens per week, resets Monday 00:00 UTC. "
        "0 disables token-based weekly limiting.",
    )

    # Cost (in credits / cents) to reset the daily rate limit using credits.
    # When a user hits their daily limit, they can spend this amount to reset
    # the daily counter and keep working.  Set to 0 to disable the feature.
    rate_limit_reset_cost: int = Field(
        default=500,
        ge=0,
        description="Credit cost (in cents) for resetting the daily rate limit. 0 = disabled.",
    )
    max_daily_resets: int = Field(
        default=5,
        ge=0,
        description="Maximum number of credit-based rate limit resets per user per day. 0 = unlimited.",
    )

    # Claude Agent SDK Configuration
    use_claude_agent_sdk: bool = Field(
        default=False,
        description="Use Claude Agent SDK. PERMANENTLY DISABLED — "
        "this project uses Chinese LLMs (DeepSeek/Qianfan/DashScope) exclusively.",
    )
    claude_agent_model: str | None = Field(
        default=None,
        description="Model for the Claude Agent SDK path. If None, derives from "
        "`thinking_standard_model` by stripping the OpenRouter provider prefix.",
    )
    claude_agent_max_buffer_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB (default SDK is 1MB)
        description="Max buffer size in bytes for Claude Agent SDK JSON message parsing. "
        "Increase if tool outputs exceed the limit.",
    )
    claude_agent_max_subtasks: int = Field(
        default=10,
        description="Max number of concurrent sub-agent Tasks the SDK can run per session.",
    )
    claude_agent_use_resume: bool = Field(
        default=True,
        description="Use --resume for multi-turn conversations instead of "
        "history compression. Falls back to compression when unavailable.",
    )
    claude_agent_fallback_model: str = Field(
        default="",
        description="Fallback model when the primary model is unavailable (e.g. 529 "
        "overloaded). The SDK automatically retries with this cheaper model. "
        "Empty string disables the fallback (no --fallback-model flag passed to CLI).",
    )
    agent_max_turns: int = Field(
        default=100,
        ge=1,
        le=10000,
        validation_alias=AliasChoices(
            "CHAT_AGENT_MAX_TURNS",
            "CHAT_CLAUDE_AGENT_MAX_TURNS",
        ),
        description="Maximum number of tool-call rounds per turn — applies to "
        "both the baseline and Claude Agent SDK paths. Prevents runaway tool "
        "loops from burning budget. Override via CHAT_AGENT_MAX_TURNS env var "
        "(legacy CHAT_CLAUDE_AGENT_MAX_TURNS still accepted).",
    )
    claude_agent_max_budget_usd: float = Field(
        default=10.0,
        ge=0.01,
        le=1000.0,
        description="Maximum spend in USD per SDK query. The CLI attempts "
        "to wrap up gracefully when this budget is reached. "
        "Set to $10 to allow most tasks to complete (p50=$5.37, p75=$13.07). "
        "Override via CHAT_CLAUDE_AGENT_MAX_BUDGET_USD env var.",
    )
    claude_agent_autocompact_pct_override: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Auto-compaction trigger threshold as a percentage of the "
        "CLI's perceived window (sets ``CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`` on the "
        "SDK subprocess). The CLI caps at its default (~93% of window); values "
        "above that have no effect. 50 (= 100K of a 200K window) keeps Anthropic "
        "context creation costs down. Set to 0 to omit the env var entirely "
        "and let the CLI use its default ~93% threshold — useful when the "
        "post-compaction floor (system prompt + tool defs ≈ 65-110K) is close "
        "to the trigger and a more aggressive value causes back-to-back "
        "compaction cascades. Skipped unconditionally for Moonshot routes.",
    )
    claude_agent_max_thinking_tokens: int = Field(
        default=8192,
        ge=0,
        le=128000,
        description="Maximum thinking/reasoning tokens per LLM call. Applies "
        "to both the Claude Agent SDK path (as ``max_thinking_tokens``) and "
        "the baseline path (as ``extra_body.reasoning.max_tokens`` on "
        "OpenRouter Anthropic routes, and as ``extra_body.thinking.budget_tokens`` "
        "on direct-Anthropic OpenAI-compat routes — the OAI-compat schema has "
        "no ``effort`` equivalent so this remains the only knob there). "
        "Extended thinking on Opus can generate 50k+ tokens at $75/M — capping "
        "this is the single biggest cost lever. 8192 is sufficient for most "
        "tasks; increase for complex reasoning. Set to 0 to disable extended "
        "thinking on both paths (kill switch): baseline skips the ``reasoning`` "
        "extra_body; SDK omits the ``max_thinking_tokens`` kwarg so the CLI "
        "falls back to model default (which, without the flag, leaves "
        "extended thinking off). On the SDK path with Claude 4.7+, prefer "
        "``claude_agent_thinking_effort`` for adaptive control — the SDK "
        "ignores ``max_thinking_tokens`` for those models.",
    )
    render_reasoning_in_ui: bool = Field(
        default=True,
        description="Render reasoning as live UI parts "
        "(``StreamReasoning*`` wire events). False suppresses the live "
        "wire events only; ``role='reasoning'`` rows are always persisted "
        "so the reasoning bubble hydrates on reload. Tokens are billed "
        "upstream regardless.",
    )
    stream_replay_count: int = Field(
        default=200,
        ge=1,
        le=10000,
        description="Max Redis stream entries replayed on SSE reconnect.",
    )
    claude_agent_thinking_effort: Literal["low", "medium", "high", "max"] | None = (
        # TODO: add xhigh when SDK support catches up
        Field(
            default=None,
            description="Thinking effort level: 'low', 'medium', 'high', 'max', or None. "
            "Applies to models that emit a reasoning channel — Sonnet, Opus, "
            "and Mythos (adaptive thinking) and Kimi K2.6 "
            "(OpenRouter ``reasoning`` extension lit up by #12871). "
            "Check https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking "  # noqa
            "for model compatibility and guidance. "
            "None = let the model decide. Override via CHAT_CLAUDE_AGENT_THINKING_EFFORT.",
        )
    )
    claude_agent_max_transient_retries: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Maximum number of retries for transient API errors "
        "(429, 5xx, ECONNRESET) before surfacing the error to the user.",
    )
    claude_agent_cross_user_prompt_cache: bool = Field(
        default=True,
        description="Enable cross-user prompt caching via SystemPromptPreset. "
        "The Claude Code default prompt becomes a cacheable prefix shared "
        "across all users, and our custom prompt is appended after it. "
        "Dynamic sections (working dir, git status, auto-memory) are excluded "
        "from the prefix. Set to False to fall back to passing the system "
        "prompt as a raw string.",
    )
    baseline_prompt_cache_ttl: str = Field(
        default="1h",
        description="TTL for the ephemeral prompt-cache markers on the baseline "
        "OpenRouter path. Anthropic supports only `5m` (default, 1.25x input "
        "price for the write) or `1h` (2x input price for the write). 1h is "
        "strictly cheaper overall when the static prefix gets >7 reads per "
        "write-window; since the system prompt + tools array is identical "
        "across all users in our workspace, 1h is the default so cross-user "
        "reads amortise the higher write cost. Anthropic has no longer "
        "(24h, permanent) TTL option — see "
        "https://platform.claude.com/docs/en/build-with-claude/prompt-caching.",
    )
    sdk_include_partial_messages: bool = Field(
        default=True,
        description="Stream SDK responses token-by-token instead of in "
        "one lump at the end.  Set to False if the SDK path starts "
        "double-writing text or dropping the tail of long messages.",
    )
    sdk_reconcile_openrouter_cost: bool = Field(
        default=True,
        description="Query OpenRouter's ``/api/v1/generation?id=`` after each "
        "SDK turn and record the authoritative ``total_cost`` instead of the "
        "Claude Agent SDK CLI's estimate.  Covers every OpenRouter-routed "
        "SDK turn regardless of vendor — the CLI's static Anthropic pricing "
        "table is accurate for Anthropic models (Sonnet/Opus via OpenRouter "
        "bill at Anthropic's own rates, penny-for-penny), but the reconcile "
        "catches any future rate change the CLI hasn't picked up and makes "
        "non-Anthropic cost (Kimi et al) correct — real billed amount, "
        "matching the baseline path's ``usage.cost`` read since #12864.  "
        "Kill-switch for emergencies: set ``CHAT_SDK_RECONCILE_OPENROUTER_COST"
        "=false`` to fall back to the CLI's ``total_cost_usd`` reported "
        "synchronously (accurate-for-Anthropic / over-billed-for-Kimi).  "
        "Tradeoff: 0.5-2s window between turn end and cost write; rate-limit "
        "counter briefly unaware, back-to-back turns in that window see "
        "stale state.  The alternative (writing an estimate sync then a "
        "correction delta) would double-count the rate limit.",
    )
    claude_agent_cli_path: str | None = Field(
        default=None,
        description="Optional explicit path to a Claude Code CLI binary. "
        "When set, the SDK uses this binary instead of the version bundled "
        "with the installed `claude-agent-sdk` package — letting us pin "
        "the Python SDK and the CLI independently. Critical for keeping "
        "OpenRouter compatibility while still picking up newer SDK API "
        "features (the bundled CLI version in 0.1.46+ is broken against "
        "OpenRouter — see PR #12294 and "
        "anthropics/claude-agent-sdk-python#789). Falls back to the "
        "bundled binary when unset. Reads from `CHAT_CLAUDE_AGENT_CLI_PATH` "
        "or the unprefixed `CLAUDE_AGENT_CLI_PATH` environment variable "
        "(same pattern as `api_key` / `base_url`).",
    )
    use_deepseek: bool = Field(
        default=True,
        description="Route copilot LLM calls through the DeepSeek API directly. "
        "Default is ``True`` — all turns use DeepSeek's OpenAI-compatible API.",
    )
    deepseek_base_url: str | None = Field(
        default=None,
        description="DeepSeek API base URL. Defaults to https://api.deepseek.com/v1.",
    )
    deepseek_api_key: str | None = Field(
        default=None,
        description="DeepSeek API key. Falls back to DEEPSEEK_API_KEY env var.",
    )

    # --- Qwen (DashScope) provider credentials ---
    qwen_api_key: str | None = Field(
        default=None,
        description="DashScope API key for Qwen. Falls back to DASHSCOPE_API_KEY env var.",
    )
    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="DashScope OpenAI-compatible base URL for Qwen.",
    )

    # --- ERNIE (Qianfan) provider credentials ---
    ernie_api_key: str | None = Field(
        default=None,
        description="Qianfan API key for ERNIE. Falls back to QIANFAN_API_KEY env var.",
    )
    ernie_base_url: str = Field(
        default="https://qianfan.baidubce.com/v2",
        description="Qianfan OpenAI-compatible base URL for ERNIE.",
    )

    # --- Vision model (Qwen-VL) for image pre-processing ---
    # When images are attached and the main model does NOT support vision
    # (e.g. DeepSeek), the system can call a separate vision model
    # (Qwen-VL) to analyse the images first and inject text descriptions
    # into the user message so the main model can "see" them.
    vision_model: str = Field(
        default="qwen-vl-max",
        validation_alias=AliasChoices("CHAT_VISION_MODEL"),
        description="Qwen-VL model to use for image analysis pre-processing. "
        "Options: qwen-vl-max (best), qwen-vl-plus (cheaper).",
    )
    vision_api_key: str | None = Field(
        default=None,
        description="DashScope API key for Qwen-VL. Falls back to "
        "CHAT_VISION_API_KEY → DASHSCOPE_API_KEY env vars.",
    )
    vision_base_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        validation_alias=AliasChoices("CHAT_VISION_BASE_URL"),
        description="Base URL for Qwen-VL OpenAI-compatible endpoint.",
    )
    vision_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("CHAT_VISION_ENABLED"),
        description="Whether to pre-process images with a vision model "
        "for non-vision-capable main models. Set to False to skip.",
    )

    use_claude_code_subscription: bool = Field(
        default=False,
        description="PERMANENTLY DISABLED — Claude Code CLI is not available.",
    )
    test_mode: bool = Field(
        default=False,
        description="Use dummy service instead of real LLM calls. "
        "Send __test_transient_error__, __test_fatal_error__, or "
        "__test_slow_response__ to trigger specific scenarios.",
    )

    # E2B Sandbox Configuration
    use_e2b_sandbox: bool = Field(
        default=True,
        description="Use E2B cloud sandboxes for persistent bash/python execution. "
        "When enabled, bash_exec routes commands to E2B and SDK file tools "
        "operate directly on the sandbox via E2B's filesystem API.",
    )
    e2b_api_key: str | None = Field(
        default=None,
        description="E2B API key. Falls back to E2B_API_KEY environment variable.",
    )
    e2b_sandbox_template: str = Field(
        default="base",
        description="E2B sandbox template to use for copilot sessions.",
    )
    e2b_sandbox_timeout: int = Field(
        default=420,  # 7 min safety net — allows headroom for compaction retries
        description="E2B sandbox running-time timeout (seconds). "
        "E2B timeout is wall-clock (not idle). Explicit per-turn pause is the primary "
        "mechanism; this is the safety net.",
    )
    e2b_sandbox_on_timeout: Literal["kill", "pause"] = Field(
        default="pause",
        description="E2B lifecycle action on timeout: 'pause' (default, free) or 'kill'.",
    )

    # Web search provider configuration for the copilot ``web_search`` tool.
    # DDGS (default) is free multi-engine search with no API key required;
    # Tavily and Serper are optional paid providers for enhanced results.
    search_provider: SearchProvider = Field(
        default="ddgs",
        description=(
            "Web search backend used by copilot's web_search tool. "
            "'ddgs' (default) is free multi-engine search with 8-backend "
            "fallback chain (DuckDuckGo → Bing → Brave → …). "
            "'tavily' / 'serper' require respective API keys set below."
        ),
    )
    tavily_api_key: str | None = Field(
        default=None,
        description="Tavily API key for AI-optimized search results.",
    )
    serper_api_key: str | None = Field(
        default=None,
        description="Serper.dev API key for fast Google SERP results.",
    )

    @property
    def openrouter_active(self) -> bool:
        """Always False — OpenRouter is no longer used for chat."""
        return False

    @property
    def effective_transport(
        self,
    ) -> Literal["deepseek"]:
        """The transport used for LLM calls. Always ``deepseek``."""
        return "deepseek"

    @property
    def main_client_credentials(self) -> tuple[str | None, str | None]:
        """``(api_key, base_url)`` for the main OpenAI-compatible client.
        Uses DeepSeek API by default."""
        return self.api_key, self.base_url

    @property
    def aux_client_credentials(self) -> tuple[str | None, str | None]:
        """``(api_key, base_url)`` for the auxiliary client.
        Falls back to main credentials when unset."""
        if self.aux_api_key is None and self.aux_base_url is None:
            return self.main_client_credentials
        api_key = self.aux_api_key or self.api_key
        base_url = self.aux_base_url or self.base_url
        return api_key, base_url

    @property
    def vision_client_credentials(self) -> tuple[str | None, str]:
        """``(api_key, base_url)`` for the Qwen-VL vision client."""
        return self.vision_api_key, self.vision_base_url

    def get_provider_credentials(
        self, provider: str
    ) -> tuple[str | None, str]:
        """Return ``(api_key, base_url)`` for a named provider.

        ``provider`` must be one of ``"deepseek"``, ``"qwen"``, ``"ernie"``.
        """
        if provider == "qwen":
            return self.qwen_api_key, self.qwen_base_url
        if provider == "ernie":
            return self.ernie_api_key, self.ernie_base_url
        # default: deepseek
        return self.api_key, self.base_url

    def get_provider_model(self, provider: str, tier: str) -> str:
        """Return the model name for a given provider and tier.

        ``provider``: ``"deepseek"`` | ``"qwen"`` | ``"ernie"``
        ``tier``: ``"standard"`` (Balanced) | ``"advanced"``
        """
        is_advanced = tier == "advanced"
        if provider == "qwen":
            return self.qwen_advanced_model if is_advanced else self.qwen_standard_model
        if provider == "ernie":
            return self.ernie_advanced_model if is_advanced else self.ernie_standard_model
        # default: deepseek
        return self.fast_advanced_model if is_advanced else self.fast_standard_model

    @property
    def aux_uses_openrouter(self) -> bool:
        """Always False — all chat calls use DeepSeek direct API."""
        return False

    @property
    def aux_provider_label(self) -> str:
        """Cost-log ``provider`` label. Returns ``deepseek``."""
        return "deepseek"

    @property
    def e2b_active(self) -> bool:
        """True when E2B is enabled and the API key is present.

        Single source of truth for "should we use E2B right now?".
        Prefer this over combining ``use_e2b_sandbox`` and ``e2b_api_key``
        separately at call sites.
        """
        return self.use_e2b_sandbox and bool(self.e2b_api_key)

    @property
    def active_e2b_api_key(self) -> str | None:
        """Return the E2B API key when E2B is enabled and configured, else None.

        Combines the ``use_e2b_sandbox`` flag check and key presence into one.
        Use in callers::

            if api_key := config.active_e2b_api_key:
                # E2B is active; api_key is narrowed to str
        """
        return self.e2b_api_key if self.e2b_active else None

    @field_validator("e2b_api_key", mode="before")
    @classmethod
    def get_e2b_api_key(cls, v):
        """Get E2B API key from environment if not provided."""
        if not v:
            v = os.getenv("CHAT_E2B_API_KEY") or os.getenv("E2B_API_KEY")
        return v

    @field_validator("api_key", mode="before")
    @classmethod
    def get_api_key(cls, v):
        """Get API key from environment if not provided. Falls back to
        DEEPSEEK_API_KEY as the primary LLM provider."""
        if not v:
            v = os.getenv("CHAT_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        return v

    @field_validator("deepseek_api_key", mode="before")
    @classmethod
    def get_deepseek_api_key(cls, v):
        """Get DeepSeek API key from environment if not provided."""
        if not v:
            v = os.getenv("CHAT_DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
        return v

    @field_validator("qwen_api_key", mode="before")
    @classmethod
    def get_qwen_api_key(cls, v):
        """Get DashScope API key for Qwen from environment if not provided."""
        if not v:
            v = os.getenv("CHAT_QWEN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        return v

    @field_validator("ernie_api_key", mode="before")
    @classmethod
    def get_ernie_api_key(cls, v):
        """Get Qianfan API key for ERNIE from environment if not provided."""
        if not v:
            v = os.getenv("CHAT_ERNIE_API_KEY") or os.getenv("QIANFAN_API_KEY")
        return v

    @field_validator("vision_api_key", mode="before")
    @classmethod
    def get_vision_api_key(cls, v):
        """Get Qwen-VL vision API key from environment if not provided."""
        if not v:
            v = os.getenv("CHAT_VISION_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        return v

    @field_validator("base_url", mode="before")
    @classmethod
    def get_base_url(cls, v):
        """Get base URL from environment. Defaults to DeepSeek API."""
        if not v:
            v = os.getenv("CHAT_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL")
            if not v:
                v = DEEPSEEK_OPENAI_COMPAT_BASE_URL
        return v

    @field_validator("aux_api_key", mode="before")
    @classmethod
    def get_aux_api_key(cls, v):
        """Auxiliary API key — explicit ``CHAT_AUX_API_KEY`` only.

        Deliberately does NOT fall back to ``OPEN_ROUTER_API_KEY`` like
        ``api_key`` does.  An explicit aux key signals "I'm splitting
        the aux client from main"; an env-pulled OR key would silently
        force aux to OR even in direct-Anthropic deployments where a
        leftover ``OPEN_ROUTER_API_KEY`` happens to be in the env —
        producing OR-key-with-Anthropic-URL 401s on every title call.

        When unset, ``aux_client_credentials`` inherits
        ``main_client_credentials`` (which itself reads
        ``OPEN_ROUTER_API_KEY`` for OR mode), so single-key
        deployments keep working unchanged.
        """
        if not v:
            v = os.getenv("CHAT_AUX_API_KEY")
        return v

    @field_validator("aux_base_url", mode="before")
    @classmethod
    def get_aux_base_url(cls, v):
        """Auxiliary base URL — defaults to OpenRouter."""
        if not v:
            v = os.getenv("CHAT_AUX_BASE_URL")
        return v

    @field_validator("claude_agent_cli_path", mode="before")
    @classmethod
    def get_claude_agent_cli_path(cls, v):
        """Resolve the Claude Code CLI override path from environment.

        Accepts either the Pydantic-prefixed ``CHAT_CLAUDE_AGENT_CLI_PATH``
        or the unprefixed ``CLAUDE_AGENT_CLI_PATH`` (matching the same
        fallback pattern used by ``api_key`` / ``base_url``). Keeping the
        unprefixed form working is important because the field is
        primarily an operator escape hatch set via container/host env,
        and the unprefixed name is what the PR description, the field
        docstrings, and the reproduction test in
        ``cli_openrouter_compat_test.py`` refer to.
        """
        if not v:
            v = os.getenv("CHAT_CLAUDE_AGENT_CLI_PATH")
            if not v:
                v = os.getenv("CLAUDE_AGENT_CLI_PATH")
        if v:
            if not os.path.exists(v):
                raise ValueError(
                    f"claude_agent_cli_path '{v}' does not exist. "
                    "Check the path or unset CLAUDE_AGENT_CLI_PATH to use "
                    "the bundled CLI."
                )
            if not os.path.isfile(v):
                raise ValueError(f"claude_agent_cli_path '{v}' is not a regular file.")
            if not os.access(v, os.X_OK):
                raise ValueError(
                    f"claude_agent_cli_path '{v}' exists but is not executable. "
                    "Check file permissions."
                )
        return v

    @model_validator(mode="after")
    def _validate_sdk_model_vendor_compatibility(self) -> "ChatConfig":
        """NOP — SDK is permanently disabled. All model names are valid."""
        return self

    @model_validator(mode="after")
    def _validate_aux_client_for_direct_main(self) -> "ChatConfig":
        """NOP — aux client always uses DeepSeek. No Anthropic validation needed."""
        return self

    # Prompt paths for different contexts
    PROMPT_PATHS: dict[str, str] = {
        "default": "prompts/chat_system.md",
        "onboarding": "prompts/onboarding_system.md",
    }

    class Config:
        """Pydantic config."""

        env_prefix = "CHAT_"
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Ignore extra environment variables
        # Accept both the Python attribute name and the validation_alias when
        # constructing a ``ChatConfig`` directly (e.g. in tests passing
        # ``thinking_standard_model=...``).  Without this, pydantic only
        # accepts the alias names (``CHAT_THINKING_STANDARD_MODEL`` env) and
        # rejects field-name kwargs — breaking ``ChatConfig(field=...)`` in
        # every test that constructs a config.
        populate_by_name = True
