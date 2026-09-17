from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from langgraph.graph import END, START, StateGraph

from cspilot.agents.planner import AgentDecision, decide_next_action
from cspilot.agents.reporter import generate_report
from cspilot.agents.router import route_request
from cspilot.agents.verifier import verify_execution, verify_request_completion, verify_tool_result
from cspilot.state import CspilotState
from cspilot.tools.registry import call_tool, reset_allowed_profile, set_allowed_profile


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def router_node(state: CspilotState) -> dict[str, Any]:
    route = route_request(state["user_request"], profile=state["profile"])
    _write_json(Path(state["workdir"]) / "route.json", route)
    return {"profile": str(route["specialist"]), "route": route}


def planner_node(state: CspilotState) -> dict[str, Any]:
    """Choose one action with the complete observation history."""
    try:
        decision = AgentDecision.model_validate(asyncio.run(decide_next_action(
            state["user_request"], state.get("observations", []),
            profile=state["profile"], workdir=state["workdir"],
            model=state.get("model"), base_url=state.get("base_url"),
        ))).model_dump(mode="json")
        _write_json(
            Path(state["workdir"]) / f"decision_{len(state.get('observations', [])) + 1:03d}.json",
            decision,
        )
        return {"decision": decision}
    except Exception as exc:
        message = f"Decision failed: {type(exc).__name__}: {exc}"
        return {"decision": {"action": "blocked", "summary": message},
                "errors": [*state["errors"], message]}


def decide_node(state: CspilotState) -> dict[str, Any]:
    decision = state.get("decision") or {"action": "blocked"}
    reason = None
    if decision["action"] != "tool":
        reason = decision["action"]
    elif len(state.get("observations", [])) >= state.get("max_steps", 8):
        reason = "max_steps"
    elif state["retry_count"] > state["max_retries"]:
        reason = "max_retries"
    return {"stop_reason": reason}


def executor_node(state: CspilotState) -> dict[str, Any]:
    """Execute exactly one registered action without model calls."""
    decision = state["decision"]
    step = {"tool": decision["tool"], "args": decision["args"]}
    plan = {"steps": [*(state.get("plan") or {"steps": []})["steps"], step]}
    token = set_allowed_profile(state["profile"], state["user_request"])
    try:
        result = call_tool(step["tool"], step["args"], state["workdir"])
    except Exception as exc:
        result = {"tool_name": step["tool"], "success": False,
                  "error": f"{type(exc).__name__}: {exc}"}
    finally:
        reset_allowed_profile(token)
    _write_json(Path(state["workdir"]) / "plan.json", plan)
    _write_json(Path(state["workdir"]) / f"step_{len(plan['steps']):03d}_result.json", result)
    return {"plan": plan, "pending_result": result}


def observe_node(state: CspilotState) -> dict[str, Any]:
    result = state["pending_result"] or {}
    verification = verify_tool_result(result, state["workdir"])
    failed = result.get("success") is False or result.get("status") in {"failed", "skipped"}
    if failed:
        verification = {"verified": False, "issues": [
            *verification.get("issues", []),
            str(result.get("error") or result.get("message") or "Tool failed"),
        ]}
    observation = {
        "step": len((state["plan"] or {})["steps"]),
        "action": state["decision"], "result": result, "verification": verification,
    }
    observations = [*state.get("observations", []), observation]
    execution = {"success": all(o["verification"]["verified"] for o in observations),
                 "workdir": state["workdir"], "steps": [o["result"] for o in observations]}
    _write_json(Path(state["workdir"]) / "observations.json", observations)
    _write_json(Path(state["workdir"]) / "execution_result.json", execution)
    return {"observations": observations, "execution_result": execution,
            "pending_result": None,
            "retry_count": state["retry_count"] + int(not verification["verified"])}


def verifier_node(state: CspilotState) -> dict[str, Any]:
    execution = state.get("execution_result") or {
        "success": False, "workdir": state["workdir"], "steps": [],
    }
    verification = verify_execution(execution, state["workdir"])
    issues = list(verification.get("issues", []))
    issues.extend(verify_request_completion(state["user_request"], execution))
    for observation in state.get("observations", []):
        issues.extend(f"Step {observation['step']}: {issue}"
                      for issue in observation["verification"].get("issues", []))
    if state.get("stop_reason") != "finish":
        issues.append(f"Agent stopped: {state.get('stop_reason')}.")
        if (state.get("decision") or {}).get("action") == "blocked":
            issues.append("Agent status: " + str(state["decision"].get("summary", "")))
    if not execution["steps"]:
        issues.append("No tool results support task completion.")
    issues.extend(state["errors"])
    verification = {"verified": not issues, "issues": list(dict.fromkeys(issues)),
                    "workdir": state["workdir"]}
    execution = {**execution, "success": verification["verified"]}
    _write_json(Path(state["workdir"]) / "execution_result.json", execution)
    _write_json(Path(state["workdir"]) / "verification_result.json", verification)
    return {"verification_result": verification, "execution_result": execution}


def reporter_node(state: CspilotState) -> dict[str, Any]:
    report = generate_report(
        state["user_request"], state["plan"] or {"steps": []},
        state["execution_result"] or {}, state["verification_result"] or {},
        html=state["html"], profile=state["profile"],
    )
    path = Path(state["workdir"]) / ("final_report.html" if state["html"] else "final_report.md")
    path.write_text(report, encoding="utf-8")
    return {"final_report": report}


def build_graph(agent_mode: str = "single"):
    if agent_mode not in {"single", "multi"}:
        raise ValueError("agent_mode must be 'single' or 'multi'.")
    graph = StateGraph(CspilotState)
    for name, node in (
        ("planner", planner_node), ("decide", decide_node), ("tool", executor_node),
        ("observe", observe_node), ("verifier", verifier_node), ("reporter", reporter_node),
    ):
        graph.add_node(name, node)
    if agent_mode == "multi":
        graph.add_node("router", router_node)
        graph.add_edge(START, "router")
        graph.add_edge("router", "planner")
    else:
        graph.add_edge(START, "planner")
    graph.add_edge("planner", "decide")
    graph.add_conditional_edges("decide", lambda s: "stop" if s.get("stop_reason") else "tool",
                                {"stop": "verifier", "tool": "tool"})
    graph.add_edge("tool", "observe")
    graph.add_edge("observe", "planner")
    graph.add_edge("verifier", "reporter")
    graph.add_edge("reporter", END)
    return graph.compile()


def run_graph_agent(
    user_request: str, workdir: str | Path, profile: str = "chem",
    agent_mode: str = "single", html: bool = False, max_retries: int = 1,
    model: str | None = None, base_url: str | None = None, max_steps: int = 8,
) -> CspilotState:
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    state: CspilotState = {
        "user_request": user_request, "workdir": str(root), "profile": profile,
        "agent_mode": agent_mode, "model": model, "base_url": base_url, "route": None,
        "html": html, "max_retries": max_retries, "retry_count": 0, "max_steps": max_steps,
        "plan": {"steps": []}, "execution_result": None, "verification_result": None,
        "final_report": None, "errors": [], "observations": [], "decision": None,
        "stop_reason": None, "pending_result": None,
    }
    try:
        if agent_mode not in {"single", "multi"}:
            raise ValueError("Unknown agent_mode. Expected 'single' or 'multi'.")
        if max_steps < 1 or max_retries < 0:
            raise ValueError("max_steps must be positive and max_retries nonnegative.")
        # Retain completed observations if orchestration itself fails.
        for update in build_graph(agent_mode).stream(
            state, config={"recursion_limit": 4 * max_steps + 12}, stream_mode="updates",
        ):
            for values in update.values():
                state.update(values)
    except Exception as exc:
        state["errors"].append(f"graph: {type(exc).__name__}: {exc}")
        state["stop_reason"] = "error"
        state.update(verifier_node(state))
        if state["profile"] not in {"chem", "stk", "materials", "analysis", "thermo", "general"}:
            state["profile"] = "general"
        state.update(reporter_node(state))
    _write_json(root / "plan.json", state["plan"])
    _write_json(root / "final_state.json", state)
    return state
