"""
SandboxManager - Security review orchestrator.

Manages the lifecycle of detection engines and coordinates content review
across multiple engines (sensitive word + code security).

Features:
  - Lazy model loading on first use
  - Fail-open fallback when models are unavailable
  - Batch review support
  - Engine health monitoring
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from .engines.sensitive_word_engine import SensitiveWordEngine
from .engines.code_security_engine import CodeSecurityEngine

logger = logging.getLogger(__name__)


# ---- Pydantic Models ----

class ReviewItem(BaseModel):
    """A single item to be reviewed."""
    content: str = Field(..., description="Text or code to review")
    review_type: str = Field(default="text", description="'text' or 'code'")


class RiskDetail(BaseModel):
    """Detailed result from one engine."""
    engine: str = Field(..., description="Engine name: 'sensitive_word' or 'code_security'")
    decision: str = Field(..., description="'approved', 'rejected', or 'flagged'")
    score: float = Field(..., description="Risk score 0.0-1.0")
    reason: str = Field(default="", description="Why this decision was made")
    matches: list[str] = Field(default_factory=list, description="Matched patterns/categories")


class EthicsReviewResult(BaseModel):
    """Aggregated review result across all engines."""
    approved: bool = Field(..., description="True if all engines approved")
    risks: list[RiskDetail] = Field(default_factory=list, description="Per-engine risk details")
    summary: str = Field(default="", description="Human-readable summary")
    combined_score: float = Field(default=0.0, description="Overall risk score 0.0-1.0")
    reviewed_at: str = Field(default="", description="ISO timestamp")


class ModelStatus(BaseModel):
    """Status of loaded ML models."""
    engine: str
    loaded: bool
    version: str
    model_size_bytes: int = 0
    last_trained: str = ""


# ---- SandboxManager ----

class SandboxManager:
    """
    Security review orchestrator (Singleton pattern).

    Usage:
        manager = SandboxManager.get_instance()
        await manager.initialize()
        result = await manager.review_text("some text")
    """

    _instance: Optional["SandboxManager"] = None
    _lock = asyncio.Lock()

    # Path to model files (set during initialization)
    DEFAULT_MODEL_DIR: str = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "models"
    )

    def __init__(self):
        self._sw_engine: SensitiveWordEngine | None = None
        self._cs_engine: CodeSecurityEngine | None = None
        self._initialized = False
        self._model_dir: str = self.DEFAULT_MODEL_DIR
        self._review_history: list[dict[str, Any]] = []
        self._stats: dict[str, int] = {
            "total_reviews": 0,
            "approved": 0,
            "rejected": 0,
            "flagged": 0,
        }

    @classmethod
    async def get_instance(cls) -> "SandboxManager":
        """Get or create the singleton instance."""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    async def initialize(self, model_dir: str | None = None) -> bool:
        """
        Initialize engines and load ML models.

        Args:
            model_dir: Directory containing .pkl model files

        Returns:
            True if at least one engine loaded successfully
        """
        if self._initialized:
            return True

        if model_dir:
            self._model_dir = model_dir

        logger.info(f"Initializing SandboxManager with models from: {self._model_dir}")

        # Initialize sensitive word engine
        self._sw_engine = SensitiveWordEngine()
        sw_model_path = os.path.join(self._model_dir, "sw_model.pkl")
        sw_loaded = self._sw_engine.load_model(sw_model_path)
        if sw_loaded:
            logger.info("SensitiveWordEngine loaded successfully")
        else:
            logger.warning("SensitiveWordEngine failed to load — will use rule-based fallback")

        # Initialize code security engine
        self._cs_engine = CodeSecurityEngine()
        cs_model_path = os.path.join(self._model_dir, "cs_model.pkl")
        cs_loaded = self._cs_engine.load_model(cs_model_path)
        if cs_loaded:
            logger.info("CodeSecurityEngine loaded successfully")
        else:
            logger.warning("CodeSecurityEngine failed to load — will use rule-only mode")

        self._initialized = True
        return sw_loaded or cs_loaded

    def _ensure_initialized(self):
        """Raise if manager is not initialized."""
        if not self._initialized:
            raise RuntimeError("SandboxManager not initialized. Call initialize() first.")

    def _record_review(self, result: EthicsReviewResult):
        """Record review for statistics."""
        self._stats["total_reviews"] += 1
        if result.approved:
            self._stats["approved"] += 1
        else:
            is_rejected = any(r.decision == "rejected" for r in result.risks)
            if is_rejected:
                self._stats["rejected"] += 1
            else:
                self._stats["flagged"] += 1

        # Keep recent history (max 1000 entries)
        self._review_history.append({
            "summary": result.summary,
            "score": result.combined_score,
            "approved": result.approved,
            "timestamp": result.reviewed_at,
        })
        if len(self._review_history) > 1000:
            self._review_history = self._review_history[-1000:]

    async def review_text(self, text: str) -> EthicsReviewResult:
        """Review plain text for sensitive/risky content."""
        self._ensure_initialized()

        risks: list[RiskDetail] = []

        # Sensitive word check
        if self._sw_engine is not None:
            sw_result = self._sw_engine.predict(text)
            risks.append(RiskDetail(
                engine="sensitive_word",
                decision=sw_result.decision,
                score=sw_result.score,
                reason=sw_result.reason,
                matches=sw_result.matches,
            ))

        # Aggregate
        approved = all(r.decision == "approved" for r in risks)
        rejected_risks = [r for r in risks if r.decision == "rejected"]
        flagged_risks = [r for r in risks if r.decision == "flagged"]

        if rejected_risks:
            summary = f"REJECTED: {len(rejected_risks)} engine(s) found high-risk content"
        elif flagged_risks:
            summary = f"FLAGGED: {len(flagged_risks)} engine(s) flagged for review"
        else:
            summary = "APPROVED: No risky content detected"

        combined = max((r.score for r in risks), default=0.0)

        result = EthicsReviewResult(
            approved=approved,
            risks=risks,
            summary=summary,
            combined_score=round(combined, 4),
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._record_review(result)
        return result

    async def review_code(self, code: str) -> EthicsReviewResult:
        """Review code snippet for security issues."""
        self._ensure_initialized()

        risks: list[RiskDetail] = []

        # Code security check
        if self._cs_engine is not None:
            cs_result = self._cs_engine.predict(code)
            risks.append(RiskDetail(
                engine="code_security",
                decision=cs_result.decision,
                score=cs_result.score,
                reason=cs_result.reason,
                matches=cs_result.matches,
            ))

        # Aggregate
        approved = all(r.decision == "approved" for r in risks)
        rejected_risks = [r for r in risks if r.decision == "rejected"]
        flagged_risks = [r for r in risks if r.decision == "flagged"]

        if rejected_risks:
            summary = f"REJECTED: {len(rejected_risks)} engine(s) found dangerous code patterns"
        elif flagged_risks:
            summary = f"FLAGGED: {len(flagged_risks)} engine(s) flagged code for review"
        else:
            summary = "APPROVED: No security issues detected"

        combined = max((r.score for r in risks), default=0.0)

        result = EthicsReviewResult(
            approved=approved,
            risks=risks,
            summary=summary,
            combined_score=round(combined, 4),
            reviewed_at=datetime.now(timezone.utc).isoformat(),
        )

        self._record_review(result)
        return result

    async def review_batch(self, items: list[ReviewItem]) -> list[EthicsReviewResult]:
        """Review multiple items in parallel."""
        self._ensure_initialized()

        tasks = []
        for item in items:
            if item.review_type == "code":
                tasks.append(self.review_code(item.content))
            else:
                tasks.append(self.review_text(item.content))

        return list(await asyncio.gather(*tasks))

    def get_model_status(self) -> list[ModelStatus]:
        """Get current status of all loaded models."""
        statuses: list[ModelStatus] = []

        # SW model status
        sw_meta = {}
        sw_path = os.path.join(self._model_dir, "sw_model_metadata.json")
        if os.path.exists(sw_path):
            with open(sw_path, "r", encoding="utf-8") as f:
                sw_meta = json.load(f)

        sw_model_path = os.path.join(self._model_dir, "sw_model.pkl")
        sw_size = os.path.getsize(sw_model_path) if os.path.exists(sw_model_path) else 0

        statuses.append(ModelStatus(
            engine="sensitive_word",
            loaded=self._sw_engine.is_loaded if self._sw_engine else False,
            version=sw_meta.get("version", "unknown"),
            model_size_bytes=sw_size,
            last_trained=sw_meta.get("trained_at", ""),
        ))

        # CS model status
        cs_meta = {}
        cs_path = os.path.join(self._model_dir, "cs_model_metadata.json")
        if os.path.exists(cs_path):
            with open(cs_path, "r", encoding="utf-8") as f:
                cs_meta = json.load(f)

        cs_model_path = os.path.join(self._model_dir, "cs_model.pkl")
        cs_size = os.path.getsize(cs_model_path) if os.path.exists(cs_model_path) else 0

        statuses.append(ModelStatus(
            engine="code_security",
            loaded=self._cs_engine.is_loaded if self._cs_engine else False,
            version=cs_meta.get("version", "unknown"),
            model_size_bytes=cs_size,
            last_trained=cs_meta.get("trained_at", ""),
        ))

        return statuses

    def get_stats(self) -> dict[str, Any]:
        """Get review statistics."""
        stats = dict(self._stats)
        rejection_rate = (
            round(stats["rejected"] / stats["total_reviews"], 4)
            if stats["total_reviews"] > 0
            else 0.0
        )
        stats["rejection_rate"] = rejection_rate
        stats["recent_reviews"] = self._review_history[-20:]  # last 20
        return stats
