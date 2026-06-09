"""External API routes for chat tools - stateless HTTP endpoints.

Note: These endpoints use ephemeral sessions that are not persisted to Redis.
As a result, session-based rate limiting (max_agent_runs, max_agent_schedules)
is not enforced for external API calls. Each request creates a fresh session
with zeroed counters. Rate limiting for external API consumers should be
handled separately (e.g., via API key quotas).
"""

import logging
from typing import Any

from fastapi import APIRouter, Security
from prisma.enums import APIKeyPermission
from pydantic import BaseModel, Field

from backend.api.external.middleware import require_permission
from backend.copilot.model import ChatSession
# [AGENT-REMOVED] from backend.copilot.tools import find_agent_tool, run_agent_tool
from backend.copilot.tools.models import ToolResponseBase
from backend.data.auth.base import APIAuthorizationInfo

logger = logging.getLogger(__name__)

tools_router = APIRouter(prefix="/tools", tags=["tools"])

# Note: We use Security() as a function parameter dependency (auth: APIAuthorizationInfo = Security(...))
# rather than in the decorator's dependencies= list. This avoids duplicate permission checks
# while still enforcing auth AND giving us access to auth for extracting user_id.


# Request models
class FindAgentRequest(BaseModel):
    query: str = Field(..., description="Search query for finding agents")


class RunAgentRequest(BaseModel):
    """Request to run or schedule an agent.

    The tool automatically handles the setup flow:
    - First call returns available inputs so user can decide what values to use
    - Returns missing credentials if user needs to configure them
    - Executes when inputs are provided OR use_defaults=true
    - Schedules execution if schedule_name and cron are provided
    """

    username_agent_slug: str = Field(
        ...,
        description="The marketplace agent slug (e.g., 'username/agent-name')",
    )
    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Dictionary of input values for the agent",
    )
    use_defaults: bool = Field(
        default=False,
        description="Set to true to run with default values (user must confirm)",
    )
    schedule_name: str | None = Field(
        None,
        description="Name for scheduled execution (triggers scheduling mode)",
    )
    cron: str | None = Field(
        None,
        description="Cron expression (5 fields: minute hour day month weekday)",
    )
    timezone: str = Field(
        default="UTC",
        description="IANA timezone (e.g., 'America/New_York', 'UTC')",
    )


def _create_ephemeral_session(user_id: str) -> ChatSession:
    """Create an ephemeral session for stateless API requests."""
    return ChatSession.new(user_id, dry_run=False)


# [AGENT-REMOVED] Agent-related API endpoints disabled.
# @tools_router.post(
#     path="/find-agent",
# )
# async def find_agent(...):
#     ...
#
# @tools_router.post(
#     path="/run-agent",
# )
# async def run_agent(...):
#     ...


# [AGENT-REMOVED] Commented out — agent tools no longer available
# @tools_router.post(
#     path="/find-agent",
# )
# async def find_agent(
#     request: FindAgentRequest,
#     auth: APIAuthorizationInfo = Security(
#         require_permission(APIKeyPermission.USE_TOOLS)
#     ),
# ) -> dict[str, Any]:
#     ...


# [AGENT-REMOVED] Commented out — agent tools no longer available
# @tools_router.post(
#     path="/run-agent",
# )
# async def run_agent(
#     request: RunAgentRequest,
#     auth: APIAuthorizationInfo = Security(
#         require_permission(APIKeyPermission.USE_TOOLS)
#     ),
# ) -> dict[str, Any]:
#     ...


def _response_to_dict(result: ToolResponseBase) -> dict[str, Any]:
    """Convert a tool response to a dictionary for JSON serialization."""
    return result.model_dump()
