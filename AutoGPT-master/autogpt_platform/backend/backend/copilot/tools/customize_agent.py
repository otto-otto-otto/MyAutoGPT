from typing import Any
from backend.copilot.model import ChatSession
from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase


class CustomizeAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "customize_agent"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "Customize an existing agent's configuration."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]}

    async def _execute(self, user_id: str | None, session: ChatSession, *, agent_id: str = "", **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="customize_agent tool not yet implemented", session_id=session.session_id)
