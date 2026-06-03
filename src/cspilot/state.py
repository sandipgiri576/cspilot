from __future__ import annotations

from typing import Any, TypedDict


class CspilotState(TypedDict):
    user_request: str
    workdir: str
    profile: str
    agent_mode: str
    route: dict[str, Any] | None
    html: bool
    max_retries: int
    retry_count: int
    plan: dict[str, Any] | None
    execution_result: dict[str, Any] | None
    verification_result: dict[str, Any] | None
    final_report: str | None
    errors: list[str]


cspilotState = CspilotState
