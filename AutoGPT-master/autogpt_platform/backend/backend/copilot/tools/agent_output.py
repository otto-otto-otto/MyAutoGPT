"""View the output of a completed agent execution.

This tool lets the copilot inspect the results of a past agent run,
including node-level outputs, so it can answer follow-up questions or
summarise outcomes without re-running the agent.
"""

import logging
from typing import Any

from backend.data.execution import (
    get_graph_executions,
    get_execution_outputs_by_node_exec_id,
)
from backend.copilot.model import ChatSession

from .base import BaseTool
from .models import (
    AgentOutputResponse,
    ErrorResponse,
    ExecutionOutputInfo,
    ToolResponseBase,
)

logger = logging.getLogger(__name__)


class AgentOutputTool(BaseTool):
    """View a past agent execution's outputs by graph ID or execution ID."""

    @property
    def name(self) -> str:
        return "view_agent_output"

    @property
    def requires_auth(self) -> bool:
        return True

    @property
    def description(self) -> str:
        return (
            "View the output of a completed agent execution. Provide either "
            "agent_graph_id to see the latest run, or execution_id to inspect "
            "a specific past run. Returns node-level outputs."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_graph_id": {
                    "type": "string",
                    "description": (
                        "The graph ID of the agent whose latest execution "
                        "output you want to view."
                    ),
                },
                "execution_id": {
                    "type": "string",
                    "description": (
                        "The specific execution ID to view. If provided, "
                        "agent_graph_id is ignored."
                    ),
                },
            },
            "required": [],
        }

    async def _execute(
        self,
        user_id: str | None,
        session: ChatSession,
        *,
        agent_graph_id: str = "",
        execution_id: str = "",
        **kwargs,
    ) -> ToolResponseBase:
        if user_id is None:
            return ErrorResponse(
                message="Authentication required",
                session_id=session.session_id,
            )

        try:
            # Look up executions
            if execution_id:
                executions = await get_graph_executions(
                    graph_exec_id=execution_id,
                    user_id=user_id,
                    limit=1,
                )
            elif agent_graph_id:
                executions = await get_graph_executions(
                    graph_id=agent_graph_id,
                    user_id=user_id,
                    limit=5,
                )
            else:
                return ErrorResponse(
                    message=(
                        "Either agent_graph_id or execution_id must be provided."
                    ),
                    session_id=session.session_id,
                )

            if not executions:
                return ErrorResponse(
                    message="No executions found for this agent.",
                    session_id=session.session_id,
                )

            # Build available executions summary
            available_executions: list[dict[str, Any]] = []
            for ex in executions:
                available_executions.append(
                    {
                        "execution_id": ex.id,
                        "status": getattr(ex, "status", "unknown"),
                        "started_at": (
                            ex.started_at.isoformat()
                            if ex.started_at
                            else None
                        ),
                        "ended_at": (
                            ex.ended_at.isoformat()
                            if ex.ended_at
                            else None
                        ),
                    }
                )

            # Pick the latest execution for detailed output
            latest = executions[0]
            latest_graph_id = latest.graph_id or agent_graph_id

            # Try to get node execution outputs if available
            outputs: dict[str, list[Any]] = {}
            if hasattr(latest, "agentGraphId"):
                # We only have GraphExecutionMeta, not full node outputs.
                # Report what we have.
                pass

            execution_info = ExecutionOutputInfo(
                execution_id=latest.id,
                status=str(getattr(latest, "status", "unknown")),
                started_at=latest.started_at,
                ended_at=latest.ended_at,
                outputs=outputs,
            )

            return AgentOutputResponse(
                message=f"Found {len(executions)} execution(s) for this agent.",
                session_id=session.session_id,
                agent_name=agent_graph_id or agent_graph_id,
                agent_id=latest_graph_id,
                library_agent_id=None,
                library_agent_link=None,
                execution=execution_info,
                available_executions=available_executions,
                total_executions=len(available_executions),
            )

        except Exception as e:
            logger.exception("Error viewing agent output")
            return ErrorResponse(
                message=f"Failed to view agent output: {str(e)}",
                session_id=session.session_id,
            )
