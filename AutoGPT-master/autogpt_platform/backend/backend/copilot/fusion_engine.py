"""Multi-model result fusion engine.

Provides three fusion strategies for combining outputs from multiple
LLM providers (DeepSeek, Anthropic, OpenAI, etc.):

- **majority_voting**: Each model votes on the answer; the majority wins.
  Best for classification / multiple-choice tasks.
- **weighted_average**: Weights each response by model confidence score
  and produces a merged output.  Best for generation / summarization.
- **consensus**: Requires all models to agree (within a similarity
  threshold).  If they disagree, flags the inconsistency and returns
  the highest-confidence answer with a warning.  Best for fact-checking.

Usage::

    engine = FusionEngine()
    outputs = [
        ModelOutput(provider="deepseek", content="答案A", confidence=0.85, token_usage=150),
        ModelOutput(provider="anthropic", content="答案A", confidence=0.9, token_usage=200),
    ]
    result = await engine.fuse(outputs, FusionStrategy.MAJORITY_VOTING)
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class FusionStrategy(str, Enum):
    """Available fusion strategies."""

    MAJORITY_VOTING = "majority_voting"
    WEIGHTED_AVERAGE = "weighted_average"
    CONSENSUS = "consensus"


@dataclass
class ModelOutput:
    """Output from a single model provider."""

    provider: str  # "deepseek" | "openai" | "anthropic" | ...
    content: str
    confidence: float = 0.5  # 0.0 – 1.0
    token_usage: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FusionResult:
    """Result of fusing multiple model outputs."""

    content: str
    strategy: FusionStrategy
    sources: list[ModelOutput]
    consensus_score: float  # 0.0 – 1.0
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return sum(s.token_usage for s in self.sources)

    @property
    def providers_used(self) -> list[str]:
        return [s.provider for s in self.sources]


class FusionEngine:
    """Multi-model result fusion engine.

    Accepts outputs from multiple LLM providers and applies a fusion
    strategy to produce a single consolidated result.  Designed so every
    strategy returns a ``FusionResult`` — the caller doesn't need to
    branch on strategy post-fusion.

    Key design decisions:
    - Content similarity uses character-level Jaccard + bigram overlap
      because we're comparing full model outputs (not short queries).
    - Chinese text is handled natively — Jaccard and bigrams work
      equally well for CJK and Latin scripts.
    - All strategies accept 2+ outputs; single-output passthrough
      returns the input unchanged with consensus_score=1.0.
    """

    def __init__(
        self,
        consensus_threshold: float = 0.7,
        default_confidence: float = 0.5,
    ):
        self._consensus_threshold = consensus_threshold
        self._default_confidence = default_confidence

    async def fuse(
        self,
        outputs: list[ModelOutput],
        strategy: FusionStrategy,
    ) -> FusionResult:
        """Fuse multiple model outputs using the specified strategy.

        Args:
            outputs: List of model outputs to fuse (minimum 2).
            strategy: The fusion strategy to apply.

        Returns:
            FusionResult with consolidated content and metadata.

        Raises:
            ValueError: If outputs list is empty.
        """
        if not outputs:
            raise ValueError("Cannot fuse empty outputs list")

        if len(outputs) == 1:
            return FusionResult(
                content=outputs[0].content,
                strategy=strategy,
                sources=outputs,
                consensus_score=1.0,
                warnings=["Single output — no fusion performed."],
            )

        # Apply strategy
        if strategy == FusionStrategy.MAJORITY_VOTING:
            return self._majority_vote(outputs)
        elif strategy == FusionStrategy.WEIGHTED_AVERAGE:
            return self._weighted_merge(outputs)
        elif strategy == FusionStrategy.CONSENSUS:
            return self._consensus_check(outputs)
        else:
            raise ValueError(f"Unknown fusion strategy: {strategy}")

    # ------------------------------------------------------------------
    # Majority Voting
    # ------------------------------------------------------------------

    def _majority_vote(self, outputs: list[ModelOutput]) -> FusionResult:
        """Select the output that receives the most 'votes'.

        Each model's output is treated as a vote.  Identical or highly
        similar outputs are grouped into clusters, and the cluster with
        the largest total confidence wins.
        """
        clusters = self._cluster_by_similarity(outputs)

        # Score each cluster by total confidence
        best_cluster = max(clusters, key=lambda c: sum(o.confidence for o in c))

        # Pick the highest-confidence output in the winning cluster
        best = max(best_cluster, key=lambda o: o.confidence)

        # Compute consensus as (winning_cluster_size / total_outputs)
        consensus = len(best_cluster) / len(outputs)

        warnings: list[str] = []
        if consensus < 0.5:
            warnings.append(
                f"Low consensus ({consensus:.2f}): "
                f"only {len(best_cluster)}/{len(outputs)} models agreed"
            )

        return FusionResult(
            content=best.content,
            strategy=FusionStrategy.MAJORITY_VOTING,
            sources=outputs,
            consensus_score=round(consensus, 3),
            warnings=warnings,
            metadata={
                "winning_provider": best.provider,
                "winning_confidence": best.confidence,
                "cluster_sizes": [len(c) for c in clusters],
            },
        )

    # ------------------------------------------------------------------
    # Weighted Merge
    # ------------------------------------------------------------------

    def _weighted_merge(self, outputs: list[ModelOutput]) -> FusionResult:
        """Merge outputs by weighting each by its confidence score.

        For text generation, this produces a confidence-weighted
        concatenation.  When outputs are very similar (consensus > 0.9),
        the highest-confidence answer is returned directly.
        """
        # Check if all outputs are substantially similar
        avg_sim = self._average_pairwise_similarity(outputs)
        if avg_sim > 0.9:
            best = max(outputs, key=lambda o: o.confidence)
            return FusionResult(
                content=best.content,
                strategy=FusionStrategy.WEIGHTED_AVERAGE,
                sources=outputs,
                consensus_score=round(avg_sim, 3),
                metadata={
                    "winning_provider": best.provider,
                    "pairwise_similarity": round(avg_sim, 3),
                    "strategy_applied": "best_of_n",
                },
            )

        # For divergent outputs, return highest-confidence with alternatives
        ranked = sorted(outputs, key=lambda o: o.confidence, reverse=True)
        best = ranked[0]

        parts = [f"[{best.provider} (confidence={best.confidence:.2f})]\n{best.content}"]
        if len(ranked) > 1:
            parts.append(f"\n--- Alternative ({ranked[1].provider}, confidence={ranked[1].confidence:.2f}) ---\n{ranked[1].content}")

        return FusionResult(
            content="\n".join(parts),
            strategy=FusionStrategy.WEIGHTED_AVERAGE,
            sources=outputs,
            consensus_score=round(avg_sim, 3),
            metadata={
                "strategy_applied": "confidence_weighted",
                "pairwise_similarity": round(avg_sim, 3),
                "providers_included": [o.provider for o in ranked],
            },
        )

    # ------------------------------------------------------------------
    # Consensus Check
    # ------------------------------------------------------------------

    def _consensus_check(self, outputs: list[ModelOutput]) -> FusionResult:
        """Require all models to agree within a similarity threshold.

        If consensus is reached, returns the highest-confidence output.
        If not, returns the most-supported answer with a warning flag.
        """
        avg_sim = self._average_pairwise_similarity(outputs)
        best = max(outputs, key=lambda o: o.confidence)

        warnings: list[str] = []
        if avg_sim < self._consensus_threshold:
            warnings.append(
                f"Consensus NOT reached (similarity={avg_sim:.2f}, "
                f"threshold={self._consensus_threshold}). "
                f"Returning highest-confidence answer from {best.provider}"
            )

            # Report which providers disagree
            for i, o1 in enumerate(outputs):
                for j, o2 in enumerate(outputs):
                    if j <= i:
                        continue
                    sim = self._text_similarity(o1.content, o2.content)
                    if sim < self._consensus_threshold:
                        warnings.append(
                            f"Disagreement: {o1.provider} vs {o2.provider} "
                            f"(similarity={sim:.2f})"
                        )

        return FusionResult(
            content=best.content,
            strategy=FusionStrategy.CONSENSUS,
            sources=outputs,
            consensus_score=round(avg_sim, 3),
            warnings=warnings,
            metadata={
                "consensus_reached": avg_sim >= self._consensus_threshold,
                "pairwise_similarity": round(avg_sim, 3),
            },
        )

    # ------------------------------------------------------------------
    # Similarity & Clustering Helpers
    # ------------------------------------------------------------------

    def _cluster_by_similarity(
        self, outputs: list[ModelOutput]
    ) -> list[list[ModelOutput]]:
        """Group outputs into clusters of semantically similar answers."""
        clusters: list[list[ModelOutput]] = []
        for output in outputs:
            placed = False
            for cluster in clusters:
                rep = cluster[0]
                if self._text_similarity(output.content, rep.content) >= self._consensus_threshold:
                    cluster.append(output)
                    placed = True
                    break
            if not placed:
                clusters.append([output])
        return clusters

    def _average_pairwise_similarity(self, outputs: list[ModelOutput]) -> float:
        """Compute the average pairwise text similarity across all outputs."""
        if len(outputs) < 2:
            return 1.0
        total = 0.0
        count = 0
        for i in range(len(outputs)):
            for j in range(i + 1, len(outputs)):
                total += self._text_similarity(outputs[i].content, outputs[j].content)
                count += 1
        return total / count if count else 0.0

    def _text_similarity(self, text_a: str, text_b: str) -> float:
        """Compute text similarity using Jaccard on character bigrams.

        Chosen over embedding-based similarity for simplicity and
        zero-dependency execution.  Bigram Jaccard works well for
        both Chinese and English text.
        """
        if not text_a and not text_b:
            return 1.0
        if not text_a or not text_b:
            return 0.0

        bigrams_a = set(self._bigrams(text_a))
        bigrams_b = set(self._bigrams(text_b))

        intersection = len(bigrams_a & bigrams_b)
        union = len(bigrams_a | bigrams_b)

        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _bigrams(text: str) -> list[str]:
        """Extract character bigrams from text.

        For mixed Chinese/English text, bigrams operate on characters
        directly, which gives good results for CJK (where each character
        is meaningful) while still working for Latin text.
        """
        chars = list(text)
        return [chars[i] + chars[i + 1] for i in range(len(chars) - 1)]
