from typing import Any
from backend.copilot.model import ChatSession
from .base import BaseTool
from .models import ErrorResponse, ToolResponseBase


class CreateAgentTool(BaseTool):
    @property
    def name(self) -> str:
        return "create_agent"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return "Create a new agent from a specification or natural-language description."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"spec": {"type": "string", "description": "Agent specification"}}, "required": ["spec"]}

    async def _execute(self, user_id: str | None, session: ChatSession, *, spec: str = "", **kwargs) -> ToolResponseBase:
        return ErrorResponse(message="create_agent tool not yet implemented", session_id=session.session_id)
