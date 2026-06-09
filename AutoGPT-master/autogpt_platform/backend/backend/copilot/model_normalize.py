"""Model-slug normalization for Chinese LLM transports.

All transports (DeepSeek, Qianfan, DashScope) use bare model slugs
(e.g. ``deepseek-chat``, ``qwen-max``) — no vendor prefix needed.
"""

from __future__ import annotations

from backend.copilot.config import ChatConfig


def normalize_model_for_transport(raw_model: str, cfg: ChatConfig | None = None) -> str:
    """Normalize a model name for the configured transport.

    All Chinese LLM providers use bare model slugs directly — no
    vendor prefix stripping needed. Just return the raw model as-is.
    """
    return raw_model
