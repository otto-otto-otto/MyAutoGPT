from typing import Any
from backend.copilot.model import ChatSession
from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase


class ListAgentTriggersTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_agent_triggers"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "List triggers configured for an agent."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]}

    async def _execute(self, user_id: str | None, session: ChatSession, *, agent_id: str = "", **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="list_agent_triggers tool not yet implemented", session_id=session.session_id)
