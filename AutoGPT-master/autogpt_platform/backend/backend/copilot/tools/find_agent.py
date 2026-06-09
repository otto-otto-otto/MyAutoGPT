from typing import Any
from backend.copilot.model import ChatSession
from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase


class FindAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "find_agent"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "Search for agents by name, description, or capability."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}

    async def _execute(self, user_id: str | None, session: ChatSession, *, query: str = "", **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="find_agent tool not yet implemented", session_id=session.session_id)
