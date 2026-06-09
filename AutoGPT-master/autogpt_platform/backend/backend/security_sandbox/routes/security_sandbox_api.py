"""
FastAPI routes for the Security Sandbox module.

Endpoints:
  POST /api/sandbox/review/text   - Review text content
  POST /api/sandbox/review/code   - Review code snippet
  POST /api/sandbox/review/batch  - Batch review
  GET  /api/sandbox/models/status - Model health & metadata
  GET  /api/sandbox/stats         - Review statistics
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..sandbox_manager import (
    EthicsReviewResult,
    ModelStatus,
    ReviewItem,
    SandboxManager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sandbox", tags=["v2", "sandbox"])

# Track if manager is initialized (lazy, on first request)
_manager: Optional[SandboxManager] = None
_init_lock = False


async def _get_manager() -> SandboxManager:
    """Lazily initialize and return the SandboxManager singleton."""
    global _manager, _init_lock
    if _manager is None and not _init_lock:
        _init_lock = True
        _manager = await SandboxManager.get_instance()
        await _manager.initialize()
        logger.info("SandboxManager initialized via API lazy-load")
    if _manager is None:
        raise HTTPException(status_code=503, detail="SandboxManager not available")
    return _manager


# ---- Request Models ----

class TextReviewRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50000, description="Text to review")


class CodeReviewRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=100000, description="Code to review")
    language: str = Field(default="auto", description="Programming language hint")


class BatchReviewRequest(BaseModel):
    items: list[ReviewItem] = Field(..., min_length=1, max_length=100, description="Items to review")


# ---- Endpoints ----

@router.post(
    "/review/text",
    response_model=EthicsReviewResult,
    summary="Review text for sensitive/risky content",
)
async def review_text(request: TextReviewRequest):
    """Analyze text for spam, phishing, or risky content patterns."""
    manager = await _get_manager()
    result = await manager.review_text(request.text)
    return result


@router.post(
    "/review/code",
    response_model=EthicsReviewResult,
    summary="Review code for security vulnerabilities",
)
async def review_code(request: CodeReviewRequest):
    """Analyze code for dangerous patterns (command injection, path traversal, etc.)."""
    manager = await _get_manager()
    result = await manager.review_code(request.code)
    return result


@router.post(
    "/review/batch",
    response_model=list[EthicsReviewResult],
    summary="Batch review multiple items",
)
async def review_batch(request: BatchReviewRequest):
    """Review multiple text or code items in parallel."""
    manager = await _get_manager()
    results = await manager.review_batch(request.items)
    return results


@router.get(
    "/models/status",
    response_model=list[ModelStatus],
    summary="Get ML model status and metadata",
)
async def get_models_status():
    """Returns the load status, version, and training metadata for each model."""
    manager = await _get_manager()
    return manager.get_model_status()


@router.get(
    "/stats",
    summary="Get review statistics",
)
async def get_stats():
    """Returns review counts, rejection rate, and recent review history."""
    manager = await _get_manager()
    return manager.get_stats()


@router.get(
    "/health",
    summary="Sandbox health check",
)
async def health_check():
    """Quick health check for the sandbox module."""
    manager = await _get_manager()
    model_status = manager.get_model_status()
    engines_loaded = sum(1 for m in model_status if m.loaded)
    return {
        "status": "healthy" if engines_loaded > 0 else "degraded",
        "engines_loaded": engines_loaded,
        "total_engines": len(model_status),
        "total_reviews": manager.get_stats()["total_reviews"],
    }
