from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cspilot.agents.verifier import verify_tool_result
from cspilot.tools.registry import call_tool, get_allowed_tools


def execute_plan(plan: dict[str, Any], workdir: str) -> dict[str, Any]:
    """Execute a validated JSON plan only through the allowlisted tool registry."""
    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    steps = plan.get("steps")
    if not isinstance(steps, list):
        raise ValueError("Plan must contain a steps list.")

    _write_json(root / "plan.json", plan)
    results: list[dict[str, Any]] = []
    issues: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict) or step.get("tool") not in get_allowed_tools():
            raise ValueError(f"Unknown or disallowed tool in step {index}.")
        tool_name = str(step["tool"])
        result = call_tool(tool_name, step.get("args", {}), str(root))
        results.append(result)
        _write_json(root / f"step_{index:03d}_result.json", result)
        verification = verify_tool_result(result, str(root))
        issues.extend(f"Step {index}: {issue}" for issue in verification["issues"])
        if result.get("success") is False:
            error = str(result.get("error") or "Tool returned success=false.")
            issues.append(f"Step {index}: {error}")
            execution_result = {
                "success": False,
                "workdir": str(root),
                "plan_path": str(root / "plan.json"),
                "steps": results,
                "failed_step_index": index,
                "failed_tool": tool_name,
                "error": error,
                "verification": {"verified": False, "issues": _deduplicate(issues)},
            }
            _write_json(root / "execution_result.json", execution_result)
            return execution_result

    execution_result = {
        "success": not issues,
        "workdir": str(root),
        "plan_path": str(root / "plan.json"),
        "steps": results,
        "verification": {"verified": not issues, "issues": issues},
    }
    _write_json(root / "execution_result.json", execution_result)
    return execution_result


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _deduplicate(issues: list[str]) -> list[str]:
    return list(dict.fromkeys(issues))
