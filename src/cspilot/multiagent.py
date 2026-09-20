"""Opt-in decomposer -> isolated agent loops -> deterministic aggregation graph."""
from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from cspilot.agents.decomposer import Decomposition, decompose_request
from cspilot.agents.reporter import _reported_values, generate_report
from cspilot.llm import with_model_clients
from cspilot.tools.aggregation import aggregate_results, validate_species


class MultiState(TypedDict, total=False):
    user_request: str
    workdir: str
    model: str | None
    base_url: str | None
    html: bool
    max_steps: int
    max_retries: int
    workers: int
    decomposition: dict[str, Any]
    summaries: list[dict[str, Any]]
    aggregate: dict[str, Any]
    errors: list[str]
    execution_result: dict[str, Any]
    verification_result: dict[str, Any]
    final_report: str


def _save(root: str | Path, name: str, value: Any) -> None:
    (Path(root) / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def decompose_node(state: MultiState) -> dict[str, Any]:
    try:
        plan = Decomposition.model_validate(asyncio.run(with_model_clients(decompose_request(
            state["user_request"], state.get("model"), state.get("base_url"))))).model_dump(mode="json")
        if plan["blocked_reason"]:
            raise ValueError(plan["blocked_reason"])
        # Resolve supplied paths before changing into isolated child work directories.
        notes = []
        for task in plan["subtasks"]:
            if task["input_xyz"]:
                path = Path(task["input_xyz"]).expanduser()
                if not path.is_absolute() and (Path(state["workdir"]) / path).is_file():
                    path = Path(state["workdir"]) / path
                if (plan["kind"] == "reaction" and task["smiles"] and not path.is_file()
                        and task["input_xyz"] not in state["user_request"]
                        and path.name not in state["user_request"]):
                    # A model-proposed output is not a supplied input. Generate from
                    # the declared species instead; never discard a user-named file.
                    notes.append(f"{task['id']}: discarded unsupplied missing input {task['input_xyz']}; generate from SMILES")
                    task["input_xyz"] = None
                    continue
                task["input_xyz"] = str(path.resolve())
        _save(state["workdir"], "decomposition_notes.json", notes)
        validate_species(plan)
        _save(state["workdir"], "decomposition.json", plan)
        return {"decomposition": plan}
    except Exception as exc:
        (Path(state["workdir"]) / "decomposition_error.txt").write_text(str(exc), encoding="utf-8")
        detail = " ".join(str(exc).split())[:500]
        return {"errors": [f"Decomposition blocked: {detail}. See decomposition_error.txt."]}


def _run_child(task: dict[str, Any], state: MultiState) -> dict[str, Any]:
    from cspilot.graph import run_graph_agent

    root = Path(state["workdir"]) / "subtasks" / task["id"]
    root.mkdir(parents=True, exist_ok=True)
    request = task["request"] + "\nWrite all generated files only inside your assigned workdir."
    plan = state["decomposition"]
    if task.get("input_xyz"):
        request += f"\nUse this supplied geometry, not another conformer: {task['input_xyz']}"
    elif task.get("smiles"):
        request += f"\nGenerate geometry from this explicit SMILES: {task['smiles']}"
    if plan["kind"] != "collection":
        request += (f"\nCalculate {plan['property']} with ORCA/OPI. Use method={plan['method']}, "
                    f"basis={plan['basis']}, charge={task['charge']}, mult={task['mult']}, "
                    f"xTB uhf={task['mult'] - 1}, nprocs=1. Gas phase, 298.15 K, 1 atm. "
                    "For enthalpy or Gibbs energy use run_xtb_orca_frequency_workflow "
                    "(ORCA optimization and frequencies). Do not use single point thermochemistry. "
                    "Report only this species, do not calculate a reaction or other species.")
    try:
        child = run_graph_agent(request, root, profile="chem", agent_mode="single",
                                model=state.get("model"), base_url=state.get("base_url"),
                                max_steps=state["max_steps"], max_retries=state["max_retries"],
                                isolate_outputs=True)
        execution = child.get("execution_result") or {}
        verification = child.get("verification_result") or {}
        summary = {"id": task["id"], "verified": verification.get("verified") is True,
                   "issues": verification.get("issues", []), "execution_result": execution,
                   "results": [{"property": k, "value": v} for k, v in _reported_values(execution)],
                   "final_state": str(root / "final_state.json")}
    except Exception as exc:
        summary = {"id": task["id"], "verified": False, "issues": [str(exc)],
                   "execution_result": {}, "results": []}
    summary["summary_file"] = str(root / "summary.json")
    _save(root, "summary.json", summary)
    return summary


def children_node(state: MultiState) -> dict[str, Any]:
    if state.get("errors"):
        return {"summaries": []}
    tasks = state["decomposition"]["subtasks"]
    # Serial by default to avoid oversubscribing ORCA/OpenMP. State is isolated either way.
    if state["workers"] == 1:
        summaries = [_run_child(task, state) for task in tasks]
    else:
        with ThreadPoolExecutor(max_workers=state["workers"]) as pool:
            summaries = list(pool.map(lambda task: _run_child(task, state), tasks))
    _save(state["workdir"], "summaries.json", summaries)
    return {"summaries": summaries}


def aggregate_node(state: MultiState) -> dict[str, Any]:
    result = ({"success": False, "error": "; ".join(state["errors"])} if state.get("errors")
              else aggregate_results(state["decomposition"], state["summaries"]))
    _save(state["workdir"], "aggregate.json", result)
    return {"aggregate": result}


def verify_node(state: MultiState) -> dict[str, Any]:
    issues = list(state.get("errors", []))
    for summary in state.get("summaries", []):
        if not summary["verified"]:
            issues.append(f"{summary['id']}: " + "; ".join(summary["issues"]))
    if state["aggregate"].get("success") is not True:
        issues.append(state["aggregate"].get("error") or "Aggregation incomplete")
    verification = {"verified": not issues, "issues": list(dict.fromkeys(issues)), "workdir": state["workdir"]}
    execution = {"success": not issues, "workdir": state["workdir"], "steps": [state["aggregate"]]}
    _save(state["workdir"], "execution_result.json", execution)
    _save(state["workdir"], "verification_result.json", verification)
    return {"verification_result": verification, "execution_result": execution}


def report_node(state: MultiState) -> dict[str, Any]:
    report = generate_report(state["user_request"], {"steps": []}, state["execution_result"],
                             state["verification_result"], html=state["html"], profile="chem")
    (Path(state["workdir"]) / ("final_report.html" if state["html"] else "final_report.md")).write_text(report)
    return {"final_report": report}


def run_multiagent(user_request: str, workdir: str | Path, *, model: str | None = None,
                   base_url: str | None = None, html: bool = False, max_steps: int = 8,
                   max_retries: int = 1, workers: int = 1) -> dict[str, Any]:
    if not 1 <= workers <= 4 or max_steps < 1 or max_retries < 0:
        raise ValueError("Require workers=1..4, max_steps>=1 and max_retries>=0")
    root = Path(workdir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    state: MultiState = {"user_request": user_request, "workdir": str(root), "model": model,
        "base_url": base_url, "html": html, "max_steps": max_steps, "max_retries": max_retries,
        "workers": workers, "errors": [], "summaries": []}
    graph = StateGraph(MultiState)
    nodes = [("decomposer", decompose_node), ("independent_agents", children_node),
             ("aggregator", aggregate_node), ("verify", verify_node), ("report", report_node)]
    previous = START
    for name, function in nodes:
        graph.add_node(name, function)
        graph.add_edge(previous, name)
        previous = name
    graph.add_edge(previous, END)
    try:
        for update in graph.compile().stream(state, stream_mode="updates"):
            for values in update.values():
                state.update(values)
    except Exception as exc:
        state["errors"].append(f"Multiagent failed: {exc}")
        state.update(aggregate_node(state))
        state.update(verify_node(state))
        state.update(report_node(state))
    final = {**state, "agent_mode": "multiagent", "plan": {"steps": []}}
    _save(root, "final_state.json", final)
    return final
