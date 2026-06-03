from __future__ import annotations

import asyncio
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from agents import Agent, AgentOutputSchema, Runner
from pydantic import BaseModel, Field

from cspilot.llm import create_agapi_model
from cspilot.tools.registry import get_allowed_tools


class RepairStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class RepairedPlan(BaseModel):
    steps: list[RepairStep] = Field(default_factory=list)


INPUT_KEYS = ("input_xyz", "xyz_path", "input_file", "xyz_file", "file")
OUTPUT_KEYS = (
    "output_path",
    "output_file",
    "xyz_path",
    "optimized_xyz",
    "lowest_geometry_copy",
    "lowest_geometry",
    "path",
)
XYZ_PRODUCER_TOOLS = {
    "stk_build_from_smiles_tool",
    "molecule_name_to_xyz_tool",
    "smiles_to_xyz_tool",
}


def repair_plan(
    user_request: str,
    plan: dict[str, Any],
    execution_result: dict[str, Any],
    workdir: str,
) -> dict[str, Any]:
    """Repair a failed execution plan without allowing arbitrary actions."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    original_plan = _clean_plan(plan)
    failed = _failed_step(original_plan, execution_result)
    if failed is None:
        return _failure("No failed step could be identified.", original_plan)

    if not _looks_like_missing_input_failure(execution_result, failed["step"]):
        agapi = _agapi_repair(user_request, original_plan, execution_result, root)
        if agapi.get("success"):
            return agapi
        return _failure("Execution failure was not a missing input file and AGAPI repair failed.", original_plan, agapi)

    missing_path = _missing_input_path(failed["step"])
    existing = _find_existing_xyz(root, missing_path, execution_result, failed["index"])
    if existing is not None:
        repaired = _replace_step_input(original_plan, failed["index"], str(existing))
        attempt_path = _write_repair_attempt(root, repaired)
        return {
            "success": True,
            "level": "deterministic_file_repair",
            "repaired_plan": repaired,
            "repair_attempt_path": str(attempt_path),
            "message": f"Repaired missing input path to {existing}.",
        }

    workflow_repair = _workflow_repair(user_request, original_plan, failed["index"], missing_path)
    if workflow_repair is not None:
        attempt_path = _write_repair_attempt(root, workflow_repair)
        return {
            "success": True,
            "level": "workflow_repair",
            "repaired_plan": workflow_repair,
            "repair_attempt_path": str(attempt_path),
            "message": "Inserted a structure-generation step before the failed calculation.",
        }

    agapi = _agapi_repair(user_request, original_plan, execution_result, root)
    if agapi.get("success"):
        return agapi
    return _failure("No deterministic repair was available and AGAPI repair failed.", original_plan, agapi)


def _clean_plan(plan: dict[str, Any]) -> dict[str, Any]:
    steps = plan.get("steps") if isinstance(plan, dict) else []
    if not isinstance(steps, list):
        steps = []
    clean_steps = []
    for step in steps:
        if isinstance(step, dict):
            clean_steps.append(
                {
                    "tool": str(step.get("tool", "")),
                    "args": dict(step.get("args") if isinstance(step.get("args"), dict) else {}),
                }
            )
    return {"steps": clean_steps}


def _failed_step(plan: dict[str, Any], execution_result: dict[str, Any]) -> dict[str, Any] | None:
    index = execution_result.get("failed_step_index")
    if isinstance(index, int) and 1 <= index <= len(plan.get("steps", [])):
        return {"index": index - 1, "step": plan["steps"][index - 1]}
    steps = execution_result.get("steps")
    if isinstance(steps, list):
        for idx, result in enumerate(steps):
            if isinstance(result, dict) and result.get("success") is False and idx < len(plan.get("steps", [])):
                return {"index": idx, "step": plan["steps"][idx]}
    return None


def _looks_like_missing_input_failure(execution_result: dict[str, Any], step: dict[str, Any]) -> bool:
    args = step.get("args") if isinstance(step.get("args"), dict) else {}
    if not any(key in args for key in INPUT_KEYS):
        return False
    text = json.dumps(execution_result, default=str).lower()
    return any(
        token in text
        for token in (
            "no such file",
            "filenotfound",
            "file not found",
            "does not exist",
            "missing",
            "cannot find",
        )
    )


def _missing_input_path(step: dict[str, Any]) -> str | None:
    args = step.get("args") if isinstance(step.get("args"), dict) else {}
    for key in INPUT_KEYS:
        value = args.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _find_existing_xyz(
    workdir: Path,
    missing_path: str | None,
    execution_result: dict[str, Any],
    failed_index: int,
) -> Path | None:
    candidates: list[Path] = []
    missing_name = Path(missing_path).name if missing_path else ""
    if missing_path:
        direct = _resolve_path(workdir, missing_path)
        if direct.exists():
            return direct
        if missing_name:
            candidates.extend(path for path in workdir.rglob(missing_name) if path.is_file())

    for value in _previous_output_values(execution_result, failed_index):
        if isinstance(value, str):
            path = _resolve_path(workdir, value)
            if path.suffix.lower() == ".xyz" and path.exists():
                candidates.append(path)

    candidates.extend(_latest_xyz_from_workdir(workdir))
    unique = list(dict.fromkeys(path.resolve() for path in candidates if path.suffix.lower() == ".xyz" and path.exists()))
    if not unique:
        return None
    if missing_name:
        for path in unique:
            if path.name == missing_name:
                return path
    return max(unique, key=lambda path: path.stat().st_mtime)


def _previous_output_values(execution_result: dict[str, Any], failed_index: int) -> list[Any]:
    values: list[Any] = []
    steps = execution_result.get("steps")
    if not isinstance(steps, list):
        return values
    for result in steps[:failed_index]:
        if isinstance(result, dict):
            values.extend(_collect_output_values(result))
    return values


def _collect_output_values(value: Any) -> list[Any]:
    collected: list[Any] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in OUTPUT_KEYS or key == "generated_files":
                if isinstance(item, list):
                    collected.extend(item)
                else:
                    collected.append(item)
            collected.extend(_collect_output_values(item))
    elif isinstance(value, list):
        for item in value:
            collected.extend(_collect_output_values(item))
    return collected


def _latest_xyz_from_workdir(workdir: Path) -> list[Path]:
    return sorted(
        (path for path in workdir.rglob("*.xyz") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def _replace_step_input(plan: dict[str, Any], step_index: int, input_path: str) -> dict[str, Any]:
    repaired = deepcopy(plan)
    args = repaired["steps"][step_index].setdefault("args", {})
    for key in INPUT_KEYS:
        args.pop(key, None)
    args["input_xyz"] = input_path
    return repaired


def _workflow_repair(
    user_request: str,
    plan: dict[str, Any],
    failed_index: int,
    missing_path: str | None,
) -> dict[str, Any] | None:
    allowed = set(get_allowed_tools())
    output_path = _safe_output_path(user_request, missing_path)
    request_lower = user_request.lower()
    producer: dict[str, Any] | None = None

    smiles = _extract_smiles(user_request)
    if "stk" in request_lower and smiles and "stk_build_from_smiles_tool" in allowed:
        producer = {
            "tool": "stk_build_from_smiles_tool",
            "args": {"smiles": smiles, "output_path": output_path},
        }
    elif smiles and "smiles_to_xyz_tool" in allowed:
        producer = {
            "tool": "smiles_to_xyz_tool",
            "args": {"smiles": smiles, "output_path": output_path},
        }
    else:
        molecule_name = _infer_molecule_name(user_request, missing_path)
        if molecule_name and "molecule_name_to_xyz_tool" in allowed:
            producer = {
                "tool": "molecule_name_to_xyz_tool",
                "args": {"name": molecule_name, "output_path": output_path},
            }

    if producer is None:
        return None
    if _plan_already_produces(plan, output_path):
        return None

    repaired = deepcopy(plan)
    repaired["steps"].insert(failed_index, producer)
    repaired = _replace_step_input(repaired, failed_index + 1, output_path)
    return repaired


def _plan_already_produces(plan: dict[str, Any], output_path: str) -> bool:
    for step in plan.get("steps", []):
        if not isinstance(step, dict):
            continue
        args = step.get("args") if isinstance(step.get("args"), dict) else {}
        if step.get("tool") in XYZ_PRODUCER_TOOLS and args.get("output_path") == output_path:
            return True
    return False


def _safe_output_path(user_request: str, missing_path: str | None) -> str:
    if missing_path and Path(missing_path).suffix.lower() == ".xyz":
        return Path(missing_path).name
    name = _infer_molecule_name(user_request, missing_path)
    if name:
        return f"{_slug(name)}.xyz"
    return "stk_molecule.xyz"


def _infer_molecule_name(user_request: str, missing_path: str | None) -> str | None:
    if missing_path:
        stem = Path(missing_path).stem
        if stem and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", stem):
            return stem.replace("_", " ").replace("-", " ")
    request = user_request.strip()
    quoted = re.search(r"['\"]([^'\"]+)['\"]", request)
    if quoted and not _looks_like_smiles(quoted.group(1)):
        return quoted.group(1)
    lowered = request.lower()
    for verb in ("optimize", "optimise", "calculate", "run", "build"):
        match = re.search(rf"\b{verb}\s+([a-z][a-z0-9_-]*)\b", lowered)
        if match and match.group(1) not in {"with", "using", "orca", "xtb", "stk"}:
            return match.group(1)
    return None


def _extract_smiles(user_request: str) -> str | None:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", user_request)
    for item in quoted:
        if _looks_like_smiles(item):
            return item
    for token in re.findall(r"\b[BCNOFPSIcnopsbrclBrCl0-9@+\-\[\]\(\)=#$\\/%.]+\b", user_request):
        if _looks_like_smiles(token):
            return token
    return None


def _looks_like_smiles(value: str) -> bool:
    stripped = value.strip()
    if not stripped or " " in stripped:
        return False
    if re.fullmatch(r"[A-Za-z]+", stripped):
        return any(char.islower() for char in stripped)
    return bool(re.search(r"[0-9@+\-\[\]\(\)=#$\\/%.]", stripped))


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "stk_molecule"


def _agapi_repair(
    user_request: str,
    plan: dict[str, Any],
    execution_result: dict[str, Any],
    workdir: Path,
) -> dict[str, Any]:
    allowed_tools = get_allowed_tools()
    failed_step = execution_result.get("failed_tool") or execution_result.get("failed_step_index")
    prompt = f"""Repair this cspilot execution plan as strict JSON only.

Original request:
{user_request}

Allowed tools:
{allowed_tools}

Original plan:
{json.dumps(plan, indent=2)}

Execution failure:
{json.dumps(execution_result, indent=2, default=str)}

Rules:
- Output exactly {{"steps": [{{"tool": "...", "args": {{}}}}]}}.
- Use only allowed tools.
- Do not invent files or scientific values.
- Do not add shell commands.
- If a tool requires input_xyz, only reference a file that already exists or
  is produced by an earlier step.
- Use molecule_name_to_xyz_tool, smiles_to_xyz_tool, or stk_build_from_smiles_tool
  before calculations when an XYZ file is missing.
"""
    try:
        repaired = asyncio.run(_run_agapi_repair(prompt))
    except Exception as exc:
        return _failure(f"AGAPI repair failed for {failed_step}: {type(exc).__name__}: {exc}", plan)

    if not _uses_only_allowed_tools(repaired, allowed_tools):
        return _failure("AGAPI repair returned a disallowed tool.", plan, {"repaired_plan": repaired})
    attempt_path = _write_repair_attempt(workdir, repaired)
    return {
        "success": True,
        "level": "agapi_repair",
        "repaired_plan": repaired,
        "repair_attempt_path": str(attempt_path),
    }


async def _run_agapi_repair(prompt: str) -> dict[str, Any]:
    agent = Agent(
        name="cspilot_repair",
        instructions="You repair cspilot execution plans using only allowlisted tools.",
        model=create_agapi_model(),
        tools=[],
        output_type=AgentOutputSchema(RepairedPlan, strict_json_schema=False),
    )
    result = await Runner.run(agent, prompt)
    repaired = (
        result.final_output
        if isinstance(result.final_output, RepairedPlan)
        else RepairedPlan.model_validate(result.final_output)
    )
    return repaired.model_dump(mode="json")


def _uses_only_allowed_tools(plan: dict[str, Any], allowed_tools: list[str]) -> bool:
    allowed = set(allowed_tools)
    return all(step.get("tool") in allowed for step in plan.get("steps", []) if isinstance(step, dict))


def _write_repair_attempt(workdir: Path, plan: dict[str, Any]) -> Path:
    existing = sorted(workdir.glob("repair_attempt_*.json"))
    path = workdir / f"repair_attempt_{len(existing) + 1:03d}.json"
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path


def _resolve_path(workdir: Path, path: str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return workdir / candidate


def _failure(message: str, plan: dict[str, Any], details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": False,
        "repaired_plan": plan,
        "error": message,
        "details": details or {},
    }
