from typing import Any
from backend.copilot.model import ChatSession
from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase


class FixAgentGraphTool(BaseTool):
    @property
    def name(self) -> str:
        return "fix_agent_graph"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "Fix validation errors in an agent graph."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"agent_json": {"type": "object"}}, "required": ["agent_json"]}

    async def _execute(self, user_id: str | None, session: ChatSession, *, agent_json: dict = None, **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="fix_agent_graph tool not yet implemented", session_id=session.session_id)
