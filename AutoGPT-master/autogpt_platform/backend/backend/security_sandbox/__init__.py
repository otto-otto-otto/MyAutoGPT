"""
Security Sandbox - Built-in content moderation and ethics review module.

Provides:
  - SensitiveWordEngine: ML-based risky text detection
  - CodeSecurityEngine: Pattern+ML-based dangerous code detection
  - SandboxManager: Orchestrator that manages engines and review workflow
  - REST API routes for external access

Model files are trained during Docker build and loaded at runtime.
"""

from .sandbox_manager import SandboxManager, EthicsReviewResult, RiskDetail, ReviewItem

__all__ = [
    "SandboxManager",
    "EthicsReviewResult",
    "RiskDetail",
    "ReviewItem",
]
