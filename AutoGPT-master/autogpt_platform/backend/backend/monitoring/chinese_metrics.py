"""Chinese-scenario specific Prometheus metrics.

Metrics registered here extend the existing instrumentation
(``instrumentation.py``) with Chinese-context-aware observability:

- ``chinese_task_decompose_quality``: Task decomposition quality score
  (gauge, 0-1). Tracks how well the Chinese semantic analyzer resolved
  ambiguities.
- ``chinese_search_hit_rate``: Search engine hit rate per engine
  (gauge, 0-1). Measures Baidu/Sogou result quality.
- ``chinese_model_fusion_consistency``: Multi-model fusion agreement
  score (gauge, 0-1). Higher = models agree more.
- ``chinese_token_usage``: Token usage by Chinese content vs. expected
  (histogram). Tracks estimation accuracy.
- ``chinese_dag_subtask_count``: Number of sub-tasks in decomposed
  DAG (histogram).
"""

from __future__ import annotations

from prometheus_client import Gauge, Histogram

# ---------------------------------------------------------------------------
# Task decomposition quality
# ---------------------------------------------------------------------------

chinese_task_decompose_quality = Gauge(
    "chinese_task_decompose_quality",
    "Quality score of Chinese task decomposition (0.0 - 1.0). "
    "Higher = better semantic disambiguation and subtask structure.",
    labelnames=["decomposer_mode"],
    namespace="autogpt",
    subsystem="chinese",
)

# ---------------------------------------------------------------------------
# Search engine metrics
# ---------------------------------------------------------------------------

chinese_search_hit_rate = Gauge(
    "chinese_search_hit_rate",
    "Hit rate of Chinese search engines (results with meaningful content "
    "/ total requests).",
    labelnames=["engine"],
    namespace="autogpt",
    subsystem="chinese",
)

chinese_search_latency_seconds = Histogram(
    "chinese_search_latency_seconds",
    "Latency of Chinese search engine requests in seconds.",
    labelnames=["engine"],
    buckets=[0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 15.0, 30.0],
    namespace="autogpt",
    subsystem="chinese",
)

chinese_search_dedup_ratio = Gauge(
    "chinese_search_dedup_ratio",
    "Deduplication ratio of aggregated search results "
    "(duplicates / total results).",
    namespace="autogpt",
    subsystem="chinese",
)

# ---------------------------------------------------------------------------
# Model fusion metrics
# ---------------------------------------------------------------------------

chinese_model_fusion_consistency = Gauge(
    "chinese_model_fusion_consistency",
    "Consistency score of multi-model fusion (0.0 - 1.0). "
    "1.0 = all models agree, 0.0 = complete disagreement.",
    labelnames=["fusion_strategy"],
    namespace="autogpt",
    subsystem="chinese",
)

chinese_fusion_provider_usage = Gauge(
    "chinese_fusion_provider_usage",
    "Number of times each provider was used in fusion (cumulative per session).",
    labelnames=["provider"],
    namespace="autogpt",
    subsystem="chinese",
)

# ---------------------------------------------------------------------------
# Token usage metrics
# ---------------------------------------------------------------------------

chinese_token_usage = Histogram(
    "chinese_token_usage",
    "Token usage for Chinese-context tasks.",
    labelnames=["provider", "estimation_method"],
    buckets=[100, 500, 1000, 2000, 4000, 8000, 16000, 32000, 64000],
    namespace="autogpt",
    subsystem="chinese",
)

chinese_token_estimation_error = Gauge(
    "chinese_token_estimation_error",
    "Relative error of Chinese token estimation vs. actual token count. "
    "(estimated - actual) / actual.  Positive = overestimation.",
    labelnames=["provider"],
    namespace="autogpt",
    subsystem="chinese",
)

# ---------------------------------------------------------------------------
# DAG execution metrics
# ---------------------------------------------------------------------------

chinese_dag_subtask_count = Histogram(
    "chinese_dag_subtask_count",
    "Number of sub-tasks generated in Chinese task decomposition.",
    buckets=[1, 2, 3, 5, 7, 10, 15, 20, 30],
    namespace="autogpt",
    subsystem="chinese",
)

chinese_dag_depth = Histogram(
    "chinese_dag_depth",
    "Maximum depth of the decomposed DAG (longest dependency chain).",
    buckets=[1, 2, 3, 5, 8, 12],
    namespace="autogpt",
    subsystem="chinese",
)

chinese_task_timeout_count = Gauge(
    "chinese_task_timeout_count",
    "Count of Chinese tasks that hit the timeout threshold.",
    labelnames=["action_type"],
    namespace="autogpt",
    subsystem="chinese",
)

# ---------------------------------------------------------------------------
# Helper: update metrics after task decomposition
# ---------------------------------------------------------------------------


def record_decomposition_quality(score: float, mode: str = "llm") -> None:
    """Record decomposition quality score."""
    chinese_task_decompose_quality.labels(decomposer_mode=mode).set(score)


def record_search_metrics(
    engine: str,
    hit_rate: float,
    latency_seconds: float,
    dedup_ratio: float = 0.0,
) -> None:
    """Record search engine performance metrics."""
    chinese_search_hit_rate.labels(engine=engine).set(hit_rate)
    chinese_search_latency_seconds.labels(engine=engine).observe(latency_seconds)
    chinese_search_dedup_ratio.set(dedup_ratio)


def record_fusion_metrics(
    consistency: float,
    strategy: str,
    provider_usage: dict[str, int],
) -> None:
    """Record multi-model fusion metrics."""
    chinese_model_fusion_consistency.labels(fusion_strategy=strategy).set(consistency)
    for provider, count in provider_usage.items():
        chinese_fusion_provider_usage.labels(provider=provider).inc(count)


def record_token_metrics(
    provider: str,
    tokens: int,
    estimation_method: str = "tiktoken",
    actual: int | None = None,
) -> None:
    """Record token usage metrics."""
    chinese_token_usage.labels(
        provider=provider, estimation_method=estimation_method
    ).observe(tokens)
    if actual is not None and actual > 0:
        error = (tokens - actual) / actual
        chinese_token_estimation_error.labels(provider=provider).set(error)


def record_dag_metrics(
    subtask_count: int,
    max_depth: int,
    timeout_count: int = 0,
    action_type: str = "unknown",
) -> None:
    """Record DAG decomposition metrics."""
    chinese_dag_subtask_count.observe(subtask_count)
    chinese_dag_depth.observe(max_depth)
    if timeout_count > 0:
        chinese_task_timeout_count.labels(action_type=action_type).inc(timeout_count)
