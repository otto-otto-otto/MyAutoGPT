"""Shared usage persistence and rate-limit recording.

Both the baseline (OpenRouter) and SDK (Anthropic) service layers need to:
  1. Append a ``Usage`` record to the session.
  2. Log the turn's token counts and cost.
  3. Record the real generation cost in Redis for rate-limiting.
  4. Write a PlatformCostLog entry for admin cost tracking.

This module extracts that common logic so both paths stay in sync.

Chinese Token Estimation:
  Chinese characters have higher information density than Latin characters.
  A single Chinese character corresponds to roughly 0.5-1.0 tokens,
  while an English word is typically 1-2 tokens.  We use a configurable
  ratio (default 1.8 chars/token) to estimate token counts for Chinese
  text when the tokenizer (tiktoken) is unavailable or doesn't cover the
  model in use.
"""

import asyncio
import logging
import math
import re
import threading

from openai.types.completion_usage import PromptTokensDetails

from backend.data.credit import UsageTransactionMetadata, get_user_credit_model
from backend.data.db import connect as ensure_db_connected
from backend.data.db_accessors import platform_cost_db
from backend.data.platform_cost import PlatformCostEntry, usd_to_microdollars
from backend.util.exceptions import InsufficientBalanceError
from backend.util.settings import Settings

from .model import ChatSession, Usage
from .rate_limit import record_cost_usage, record_token_usage

logger = logging.getLogger(__name__)

#: Tracks repeated BILLING_LEAK events per-user so the logs don't flood
#: when a wallet is empty.  Key = "{leak_type}:{user_id}".
_billing_leak_counter: dict[str, int] = {}

# ---------------------------------------------------------------------------
# Chinese token estimation
# ---------------------------------------------------------------------------

# Unicode ranges for Chinese characters
_CJK_RANGES = [
    (0x4E00, 0x9FFF),  # CJK Unified Ideographs
    (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B (rarely used)
    (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Ideographs Supplement
]


def _is_cjk_char(ch: str) -> bool:
    """Return True if the character is a CJK unified ideograph."""
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


# Budget quotas per model provider (microdollars per day).
# These are base quotas for the free tier; higher tiers multiply.
PROVIDER_BUDGET_QUOTAS: dict[str, int] = {
    "deepseek": 500_000,  # $0.50/day — DeepSeek is very cheap
    "openai": 1_000_000,  # $1.00/day
    "anthropic": 2_000_000,  # $2.00/day
    "open_router": 1_000_000,  # $1.00/day (default)
}


def estimate_chinese_tokens(text: str, ratio: float = 1.8) -> int:
    """Estimate token count for Chinese text.

    Uses a character-to-token ratio approach.  Chinese characters encode
    more information per character than Latin, so a single CJK character
    corresponds to roughly 0.5-1.0 tokens in most tokenizers.

    Args:
        text: The input text (mixed Chinese/English is fine).
        ratio: Estimated characters per token.  Default 1.8 (empirical
               average across DeepSeek, GPT, and Claude tokenizers).

    Returns:
        Estimated token count (rounded up to nearest int).
    """
    if not text:
        return 0

    cjk_count = sum(1 for ch in text if _is_cjk_char(ch))
    non_cjk_count = sum(1 for ch in text if not _is_cjk_char(ch) and not ch.isspace())

    # CJK: ~ratio chars per token
    # Non-CJK (Latin, digits, punctuation): ~4 chars per token (typical English)
    cjk_tokens = math.ceil(cjk_count / ratio) if cjk_count else 0
    non_cjk_tokens = math.ceil(non_cjk_count / 4.0) if non_cjk_count else 0

    return max(1, cjk_tokens + non_cjk_tokens)


def estimate_chinese_token_count(messages: list[dict]) -> int:
    """Estimate total token count for a list of chat messages.

    Iterates over message content and estimates token counts for each
    piece of text content.  Handles str and list-of-content-parts formats.

    Args:
        messages: List of chat messages in OpenAI format.

    Returns:
        Estimated total token count.
    """
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_chinese_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text", "")
                    total += estimate_chinese_tokens(text)
    return max(1, total)


def get_provider_budget(provider: str) -> int:
    """Get the daily budget quota for a specific provider.

    Args:
        provider: The provider name (e.g. "deepseek", "openai").

    Returns:
        Budget in microdollars per day.  Defaults to 1,000,000 ($1.00)
        for unknown providers.
    """
    return PROVIDER_BUDGET_QUOTAS.get(provider, 1_000_000)


# ---------------------------------------------------------------------------
# Warning thresholds for token consumption
# ---------------------------------------------------------------------------

# When consumed tokens reach this percentage of the context window,
# emit a warning log.  Useful for catching runaway prompts before
# they fail at the API boundary.
TOKEN_WARNING_THRESHOLD_PCT = 0.85  # 85% of context window


def check_token_budget(
    consumed_tokens: int,
    context_window: int,
    provider: str = "unknown",
) -> list[str]:
    """Check token consumption against budget and emit warnings.

    Args:
        consumed_tokens: Estimated or actual input tokens.
        context_window: The model's context window size.
        provider: Provider name for contextual warning messages.

    Returns:
        List of warning messages (empty if within budget).
    """
    warnings: list[str] = []
    remaining = context_window - consumed_tokens
    pct_used = consumed_tokens / context_window if context_window else 0

    if pct_used >= TOKEN_WARNING_THRESHOLD_PCT:
        warnings.append(
            f"[{provider}] Token budget warning: {consumed_tokens}/{context_window} "
            f"({pct_used:.1%}) used, only {remaining} tokens remaining"
        )

    if remaining < 100:
        warnings.append(
            f"[{provider}] CRITICAL: Only {remaining} tokens remaining in context window — "
            f"consider reducing prompt or lowering max_tokens"
        )

    return warnings


def _extract_cache_creation_tokens(ptd: PromptTokensDetails) -> int:
    """Return cache-write token count from a ``PromptTokensDetails`` object.

    Two provider-specific field names exist:
    - OpenRouter streams ``cache_write_tokens`` (typed attr on newer SDK,
      ``model_extra`` on older SDK).
    - Direct Anthropic API uses ``cache_creation_input_tokens`` in
      ``model_extra`` (never a typed attr on the OpenAI SDK).
    """
    typed_val = getattr(ptd, "cache_write_tokens", None)
    if typed_val:
        return int(typed_val)
    extras = ptd.model_extra or {}
    return int(
        extras.get("cache_write_tokens")
        or extras.get("cache_creation_input_tokens")
        or 0
    )


# Hold strong references to in-flight cost log tasks to prevent GC.
_pending_log_tasks: set[asyncio.Task[None]] = set()
# Guards all reads and writes to _pending_log_tasks. Done callbacks (discard)
# fire from the event loop thread; drain_pending_cost_logs iterates the set
# from any caller — the lock prevents RuntimeError from concurrent modification.
_pending_log_tasks_lock = threading.Lock()
# Per-loop semaphores: asyncio.Semaphore is not thread-safe and must not be
# shared across event loops running in different threads.
_log_semaphores: dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}


def _get_log_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _log_semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(50)
        _log_semaphores[loop] = sem
    return sem


def _schedule_cost_log(entry: PlatformCostEntry) -> None:
    """Schedule a fire-and-forget cost log via DatabaseManagerAsyncClient RPC."""

    async def _safe_log() -> None:
        async with _get_log_semaphore():
            try:
                await platform_cost_db().log_platform_cost(entry)
            except Exception:
                logger.exception(
                    "Failed to log platform cost for user=%s provider=%s block=%s",
                    entry.user_id,
                    entry.provider,
                    entry.block_name,
                )

    task = asyncio.create_task(_safe_log())
    with _pending_log_tasks_lock:
        _pending_log_tasks.add(task)

    def _remove(t: asyncio.Task[None]) -> None:
        with _pending_log_tasks_lock:
            _pending_log_tasks.discard(t)

    task.add_done_callback(_remove)


# Identifiers used by PlatformCostLog for copilot turns (not tied to a real
# block/credential in the block_cost_config or credentials_store tables).
COPILOT_BLOCK_ID = "copilot"
COPILOT_CREDENTIAL_ID = "copilot_system"


def _copilot_block_name(log_prefix: str) -> str:
    """Extract stable block_name from ``"[SDK][session][T1]"`` -> ``"copilot:SDK"``."""
    match = re.search(r"\[([A-Za-z][A-Za-z0-9_]*)\]", log_prefix)
    if match:
        return f"{COPILOT_BLOCK_ID}:{match.group(1)}"
    tag = log_prefix.strip(" []")
    return f"{COPILOT_BLOCK_ID}:{tag}" if tag else COPILOT_BLOCK_ID


async def persist_and_record_usage(
    *,
    session: ChatSession | None,
    user_id: str | None,
    prompt_tokens: int,
    completion_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
    log_prefix: str = "",
    cost_usd: float | str | None = None,
    model: str | None = None,
    provider: str = "open_router",
) -> int:
    """Persist token usage to session and record generation cost for rate limiting.

    Rate-limit counters are charged in microdollars against the provider's
    reported cost (``cost_usd``), so cache discounts and cross-model pricing
    differences are already reflected. When cost is unknown the turn is
    logged but the rate-limit counter is left alone — the caller logs an
    error at the point the absence is detected.

    Args:
        session: The chat session to append usage to (may be None on error).
        user_id: User ID for rate-limit counters (skipped if None).
        prompt_tokens: Uncached input tokens.
        completion_tokens: Output tokens.
        cache_read_tokens: Tokens served from prompt cache (Anthropic only).
        cache_creation_tokens: Tokens written to prompt cache (Anthropic only).
        log_prefix: Prefix for log messages (e.g. "[SDK]", "[Baseline]").
        cost_usd: Real generation cost for the turn (float from SDK or parsed
            from OpenRouter usage.cost). ``None`` means the provider did not
            report a cost and rate limiting is skipped for this turn.
        model: Model identifier for cost log attribution.
        provider: Cost provider name (e.g. "anthropic", "open_router").

    Returns:
        The computed total_tokens (prompt + completion; cache excluded).
    """
    prompt_tokens = max(0, prompt_tokens)
    completion_tokens = max(0, completion_tokens)
    cache_read_tokens = max(0, cache_read_tokens)
    cache_creation_tokens = max(0, cache_creation_tokens)

    no_tokens = (
        prompt_tokens <= 0
        and completion_tokens <= 0
        and cache_read_tokens <= 0
        and cache_creation_tokens <= 0
    )
    if no_tokens and cost_usd is None:
        return 0

    # total_tokens = prompt + completion. Cache tokens are tracked
    # separately and excluded from total so both baseline and SDK
    # paths share the same semantics.
    total_tokens = prompt_tokens + completion_tokens

    if session is not None:
        session.usage.append(
            Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_creation_tokens=cache_creation_tokens,
            )
        )

    if cache_read_tokens or cache_creation_tokens:
        logger.info(
            f"{log_prefix} Turn usage: uncached={prompt_tokens}, cache_read={cache_read_tokens},"
            f" cache_create={cache_creation_tokens}, output={completion_tokens},"
            f" total={total_tokens}, cost_usd={cost_usd}"
        )
    else:
        logger.info(
            f"{log_prefix} Turn usage: prompt={prompt_tokens}, completion={completion_tokens},"
            f" total={total_tokens}, cost_usd={cost_usd}"
        )

    cost_float: float | None = None
    if cost_usd is not None:
        try:
            val = float(cost_usd)
        except (ValueError, TypeError):
            logger.error(
                "%s cost_usd is not numeric: %r — rate limit skipped",
                log_prefix,
                cost_usd,
            )
        else:
            if not math.isfinite(val):
                logger.error(
                    "%s cost_usd is non-finite: %r — rate limit skipped",
                    log_prefix,
                    val,
                )
            elif val < 0:
                logger.warning(
                    "%s cost_usd %s is negative — skipping rate-limit + cost log",
                    log_prefix,
                    val,
                )
            else:
                cost_float = val

    cost_microdollars = usd_to_microdollars(cost_float)

    if user_id and cost_microdollars is not None and cost_microdollars > 0:
        # record_cost_usage() owns its fail-open handling for Redis/network
        # errors. Don't wrap with a broad except here — unexpected accounting
        # bugs should surface instead of being silently logged as warnings.
        await record_cost_usage(
            user_id=user_id,
            cost_microdollars=cost_microdollars,
        )

    # Record token consumption for token-based rate limiting.
    # Fail-open: Redis errors are logged but never block the user.
    if user_id and total_tokens > 0:
        await record_token_usage(
            user_id=user_id,
            token_count=total_tokens,
        )

    # Log to PlatformCostLog for admin cost dashboard.
    # Include entries where cost_usd is set even if token count is 0
    # (e.g. fully-cached Anthropic responses where only cache tokens
    # accumulate a charge without incrementing total_tokens).
    if user_id and (total_tokens > 0 or cost_float is not None):
        session_id = session.session_id if session else None

        if cost_float is not None:
            tracking_type = "cost_usd"
            tracking_amount = cost_float
        else:
            tracking_type = "tokens"
            tracking_amount = total_tokens

        _schedule_cost_log(
            PlatformCostEntry(
                user_id=user_id,
                graph_exec_id=session_id,
                block_id=COPILOT_BLOCK_ID,
                block_name=_copilot_block_name(log_prefix),
                provider=provider,
                credential_id=COPILOT_CREDENTIAL_ID,
                cost_microdollars=cost_microdollars,
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                cache_read_tokens=cache_read_tokens or None,
                cache_creation_tokens=cache_creation_tokens or None,
                model=model,
                tracking_type=tracking_type,
                tracking_amount=tracking_amount,
                metadata={
                    "tracking_type": tracking_type,
                    "tracking_amount": tracking_amount,
                    "cache_read_tokens": cache_read_tokens,
                    "cache_creation_tokens": cache_creation_tokens,
                    "source": "copilot",
                },
            )
        )

    return total_tokens


async def spend_copilot_credits(
    *,
    user_id: str | None,
    cost_usd: float | None,
    total_tokens: int = 0,
    reason: str = "copilot_chat_turn",
    model: str | None = None,
    log_prefix: str = "",
) -> None:
    """Deduct credits from the user's wallet for a copilot LLM turn.

    Calculates credit cost based on token consumption using the configured
    ``credits_per_10000_tokens`` rate.  Falls back to USD-based calculation
    when token count is unavailable.

    This is a **fail-open** helper — if the charge fails (e.g. database
    is unavailable, balance is insufficient) the error is logged as a
    ``BILLING_LEAK`` but **never** re-raised.  The LLM response has
    already been streamed to the user.
    """
    if user_id is None:
        return

    settings = Settings()
    credit_cost = 0

    # Primary: token-based credit deduction.
    # Formula: credit_cost = max(1, int(total_tokens / 10000 * credits_per_10000_tokens))
    # e.g. 1,000,000 tokens → 100 * 0.01 = 1 credit (minimum charge)
    if total_tokens > 0:
        credit_cost = max(
            1,
            int(total_tokens / 10000 * settings.config.credits_per_10000_tokens),
        )

    if credit_cost <= 0 and cost_usd is not None:
        # Fallback: USD-based credit deduction (legacy path when tokens unavailable).
        try:
            cost_float = float(cost_usd)
        except (ValueError, TypeError):
            logger.error(
                "%s spend_copilot_credits: cost_usd is not numeric: %r",
                log_prefix,
                cost_usd,
            )
            return

        if not math.isfinite(cost_float) or cost_float <= 0:
            return

        credit_cost = max(1, int(cost_float * settings.config.credits_per_usd))

    if credit_cost <= 0:
        return

    try:
        # Ensure the Prisma database connection is alive before querying.
        # Connections can be closed by pool timeouts (DB_POOL_TIMEOUT) or
        # transient network issues.  connect() is a no-op when already connected.
        await ensure_db_connected()

        credit_db = await get_user_credit_model(user_id)
        await credit_db.spend_credits(
            user_id=user_id,
            cost=credit_cost,
            metadata=UsageTransactionMetadata(
                block=COPILOT_BLOCK_ID,
                block_id=COPILOT_BLOCK_ID,
                reason=reason,
                input={
                    "cost_usd": cost_usd,
                    "total_tokens": total_tokens,
                    "model": model,
                    "source": "copilot_chat",
                },
            ),
            fail_insufficient_credits=True,
        )
        logger.debug(
            "%s Charged %s credits (%s tokens) for copilot turn",
            log_prefix,
            credit_cost,
            total_tokens,
        )
    except Exception as e:
        leak_type = (
            "INSUFFICIENT_BALANCE"
            if isinstance(e, InsufficientBalanceError)
            else "UNEXPECTED_ERROR"
        )

        # Track repeated BILLING_LEAK events per user so we don't flood
        # the logs when a user's wallet is empty.  First occurrence -> ERROR,
        # subsequent ones -> WARNING (rate-limited).
        leak_key = f"{leak_type}:{user_id}"
        leak_count = _billing_leak_counter.get(leak_key, 0)
        _billing_leak_counter[leak_key] = leak_count + 1

        if leak_count == 0:
            logger.error(
                "BILLING_LEAK[%s]: copilot LLM turn credit charge failed — "
                "user_id=%s, cost_credits=%s, cost_usd=%s, model=%s: %s",
                leak_type,
                user_id,
                credit_cost,
                cost_usd,
                model,
                e,
                extra={
                    "json_fields": {
                        "billing_leak": True,
                        "leak_type": leak_type,
                    }
                },
            )
        else:
            # Every 20th repeat leak we emit a single warning so admins
            # can still see that the wallet has never been topped up.
            if leak_count % 20 == 1:
                logger.warning(
                    "BILLING_LEAK[%s] x%d repeats — user_id=%s still has no valid "
                    "credit wallet. Check that initial sign-up grant succeeded.",
                    leak_type,
                    leak_count,
                    user_id,
                )
