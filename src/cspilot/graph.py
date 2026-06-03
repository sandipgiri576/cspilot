from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from cspilot.agents.executor import execute_plan
from cspilot.agents.planner import create_plan
from cspilot.agents.reporter import generate_report
from cspilot.agents.router import route_request
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


def router_node(state: CspilotState) -> dict[str, Any]:
    """Route a request to one specialist profile before planning."""
    try:
        route = route_request(
            state["user_request"],
            profile=state.get("profile", "auto"),
        )
        specialist = str(route["specialist"])
        _write_json(Path(state["workdir"]) / "route.json", route)
        return {"profile": specialist, "route": route}
    except Exception as exc:
        route = {
            "success": False,
            "specialist": "general",
            "reason": f"Router failed: {type(exc).__name__}: {exc}",
            "allowed_tool_groups": [],
        }
        _write_json(Path(state["workdir"]) / "route.json", route)
        return {
            "profile": "general",
            "route": route,
            "errors": [*state.get("errors", []), route["reason"]],
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
    agent_mode: str = "single",
    html: bool = False,
    max_retries: int = 1,
) -> CspilotState:
    """Run the LangGraph planner/executor/verifier/reporter orchestration."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    if agent_mode not in {"single", "multi"}:
        return _failed_initial_state(
            user_request=user_request,
            workdir=root,
            profile=profile,
            agent_mode=agent_mode,
            html=html,
            max_retries=max_retries,
            error="Unknown agent_mode. Expected 'single' or 'multi'.",
        )
    selected_profile = profile
    initial_state: CspilotState = {
        "user_request": user_request,
        "workdir": str(root),
        "profile": selected_profile,
        "agent_mode": agent_mode,
        "route": None,
        "html": html,
        "max_retries": max_retries,
        "retry_count": 0,
        "plan": None,
        "execution_result": None,
        "verification_result": None,
        "final_report": None,
        "errors": [],
    }
    try:
        app = build_graph(agent_mode=agent_mode)
        final_state = app.invoke(initial_state)
    except Exception as exc:
        final_state = {
            **initial_state,
            "errors": [f"graph: {type(exc).__name__}: {exc}"],
            "execution_result": {
                "success": False,
                "workdir": str(root),
                "steps": [],
                "error": f"{type(exc).__name__}: {exc}",
            },
        }
        final_state["final_report"] = _failure_report(final_state)
    return final_state


def build_graph(agent_mode: str = "single"):
    if agent_mode not in {"single", "multi"}:
        raise ValueError("agent_mode must be 'single' or 'multi'.")
    graph = StateGraph(CspilotState)
    if agent_mode == "multi":
        graph.add_node("router", router_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("verifier", verifier_node)
    graph.add_node("reporter", reporter_node)
    if agent_mode == "multi":
        graph.add_edge(START, "router")
        graph.add_edge("router", "planner")
    else:
        graph.add_edge(START, "planner")
    graph.add_edge("planner", "executor")
    graph.add_edge("executor", "verifier")
    graph.add_edge("verifier", "reporter")
    graph.add_edge("reporter", END)
    return graph.compile()


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


def _failed_initial_state(
    user_request: str,
    workdir: Path,
    profile: str,
    agent_mode: str,
    html: bool,
    max_retries: int,
    error: str,
) -> CspilotState:
    state: CspilotState = {
        "user_request": user_request,
        "workdir": str(workdir),
        "profile": profile,
        "agent_mode": agent_mode,
        "route": None,
        "html": html,
        "max_retries": max_retries,
        "retry_count": 0,
        "plan": None,
        "execution_result": {
            "success": False,
            "workdir": str(workdir),
            "steps": [],
            "error": error,
        },
        "verification_result": None,
        "final_report": None,
        "errors": [error],
    }
    state["final_report"] = _failure_report(state)
    return state


def _failure_report(state: CspilotState) -> str:
    errors = "\n".join(f"- {error}" for error in state.get("errors", []))
    return f"**Task**\n{state['user_request']}\n\n**Errors**\n{errors or '- Graph failed.'}\n"
