import logging
from pathlib import Path
from typing import Any

from backend.copilot.model import ChatSession

from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase

logger = logging.getLogger(__name__)

_GUIDE_CACHE: str | None = None


def _load_guide() -> str:
    """Load the agent-building guide from disk (cached per process)."""
    global _GUIDE_CACHE
    if _GUIDE_CACHE is None:
        guide_path = Path(__file__).parent.parent / "sdk" / "agent_generation_guide.md"
        _GUIDE_CACHE = guide_path.read_text(encoding="utf-8")
    return _GUIDE_CACHE


class GetAgentBuildingGuideTool(BaseTool):
    @property
    def name(self) -> str:
        return "get_agent_building_guide"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "Retrieve guidance on how to build agents."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def _execute(self, user_id: str | None, session: ChatSession, **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="get_agent_building_guide tool not yet implemented", session_id=session.session_id)
