from typing import Any
from backend.copilot.model import ChatSession
from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase


class RunAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "run_agent"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "Run an agent by ID with optional inputs."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"agent_id": {"type": "string"}}, "required": ["agent_id"]}

    async def _execute(self, user_id: str | None, session: ChatSession, *, agent_id: str = "", **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="run_agent tool not yet implemented", session_id=session.session_id)
