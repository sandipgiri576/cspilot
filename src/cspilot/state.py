"""Define typed state passed through the single-agent LangGraph."""

from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class CspilotState(TypedDict):
    """Store planner, execution, verification, and reporting graph state."""

    user_request: str
    workdir: str
    profile: str
    agent_mode: str
    model: str | None
    base_url: str | None
    route: dict[str, Any] | None
    html: bool
    max_retries: int
    retry_count: int
    plan: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    verification_result: dict[str, Any] | None
    final_report: str | None
    errors: list[str]
    observations: NotRequired[list[dict[str, Any]]]
    decision: NotRequired[dict[str, Any] | None]
    max_steps: NotRequired[int]
    stop_reason: NotRequired[str | None]
    pending_result: NotRequired[dict[str, Any] | None]
    isolate_outputs: NotRequired[bool]


cspilotState = CspilotState
