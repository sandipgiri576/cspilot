from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph

from cspilot.agents.executor import execute_plan
from cspilot.agents.planner import create_plan
from cspilot.agents.reporter import generate_report
from cspilot.agents.verifier import verify_execution
from cspilot.state import CspilotState
from cspilot.tools.registry import reset_allowed_profile, set_allowed_profile


def planner_node(state: CspilotState) -> dict[str, Any]:
    """Plan with the existing AGAPI planner."""
    try:
        plan = _run_maybe_async(
            create_plan(
                state["user_request"],
                profile=state["profile"],
            )
        )
        _write_json(Path(state["workdir"]) / "plan.json", plan)
        return {"plan": plan, "execution_result": None, "verification_result": None}
    except Exception as exc:
        return {
            "plan": None,
            "execution_result": None,
            "verification_result": None,
            "errors": [*state.get("errors", []), f"planner: {type(exc).__name__}: {exc}"],
        }


def executor_node(state: CspilotState) -> dict[str, Any]:
    """Execute a plan through the existing allowlisted executor."""
    if not state.get("plan"):
        return _retry_update(state, "executor: missing plan")
    token = set_allowed_profile(state["profile"], state["user_request"])
    try:
        execution_result = execute_plan(state["plan"] or {"steps": []}, state["workdir"])
        update: dict[str, Any] = {"execution_result": execution_result}
        if execution_result.get("success") is not True:
            update = _retry_update(state, "executor: execution failed", update)
        return update
    except Exception as exc:
        failed_result = {
            "success": False,
            "workdir": state["workdir"],
            "steps": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
        return _retry_update(
            state,
            f"executor: {type(exc).__name__}: {exc}",
            {"execution_result": failed_result, "verification_result": None},
        )
    finally:
        reset_allowed_profile(token)


def verifier_node(state: CspilotState) -> dict[str, Any]:
    """Verify execution output through the existing verifier."""
    if not state.get("execution_result"):
        return _retry_update(state, "verifier: missing execution result")
    try:
        verification_result = verify_execution(state["execution_result"] or {}, state["workdir"])
        update: dict[str, Any] = {"verification_result": verification_result}
        if verification_result.get("verified") is not True:
            update = _retry_update(state, "verifier: verification failed", update)
        return update
    except Exception as exc:
        failed_verification = {
            "verified": False,
            "issues": [f"{type(exc).__name__}: {exc}"],
        }
        return _retry_update(
            state,
            f"verifier: {type(exc).__name__}: {exc}",
            {"verification_result": failed_verification},
        )


def reporter_node(state: CspilotState) -> dict[str, Any]:
    """Create the final deterministic report."""
    plan = state.get("plan") or {"steps": []}
    execution_result = state.get("execution_result") or {
        "success": False,
        "workdir": state["workdir"],
        "steps": [],
    }
    verification_result = state.get("verification_result") or {
        "verified": False,
        "issues": state.get("errors", []),
    }
    report = generate_report(
        state["user_request"],
        plan,
        execution_result,
        verification_result,
        html=state["html"],
        profile=state["profile"],
    )
    return {"final_report": report}


def run_graph_agent(
    user_request: str,
    workdir: str | Path,
    profile: str = "chem",
    html: bool = False,
    max_retries: int = 2,
) -> CspilotState:
    """Run the single-agent LangGraph orchestration."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    initial_state: CspilotState = {
        "user_request": user_request,
        "workdir": str(root),
        "profile": profile,
        "html": html,
        "max_retries": max_retries,
        "retry_count": 0,
        "plan": None,
        "execution_result": None,
        "verification_result": None,
        "final_report": None,
        "errors": [],
    }
    app = build_graph()
    final_state = app.invoke(initial_state)
    return final_state


def build_graph():
    graph = StateGraph(CspilotState)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("reporter", reporter_node)
    graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_conditional_edges(
        "executor",
        _route_after_executor,
        {"retry": "planner", "verify": "verifier"},
    )
    graph.add_conditional_edges(
        "verifier",
        _route_after_verifier,
        {"retry": "planner", "report": "reporter"},
    )
    graph.add_edge("reporter", END)
    return graph.compile()


def _route_after_executor(state: CspilotState) -> Literal["retry", "verify"]:
    execution_result = state.get("execution_result")
    if execution_result and execution_result.get("success") is True:
        return "verify"
    if state.get("retry_count", 0) < state.get("max_retries", 0):
        return "retry"
    return "verify"


def _route_after_verifier(state: CspilotState) -> Literal["retry", "report"]:
    verification_result = state.get("verification_result")
    if verification_result and verification_result.get("verified") is True:
        return "report"
    if state.get("retry_count", 0) < state.get("max_retries", 0):
        return "retry"
    return "report"


def _retry_update(
    state: CspilotState,
    message: str,
    update: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        **(update or {}),
        "retry_count": state.get("retry_count", 0) + 1,
        "errors": [*state.get("errors", []), message],
    }


def _run_maybe_async(value: Any) -> Any:
    if inspect.isawaitable(value):
        return asyncio.run(value)
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

