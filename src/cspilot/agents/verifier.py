from __future__ import annotations

from numbers import Real
from pathlib import Path
from typing import Any


def verify_tool_result(result: dict[str, Any], workdir: str) -> dict[str, Any]:
    """Verify recorded tool output without inferring any scientific values."""
    issues: list[str] = []
    root = Path(workdir)

    for key, value in _walk(result):
        normalized_key = key.lower()
        if normalized_key == "success" and value is False:
            issues.append("Tool returned success=false.")
        if normalized_key == "status" and value in {"failed", "skipped"}:
            issues.append(f"Tool status is {value}.")
        if normalized_key in {"error", "error_message"} and value not in (None, ""):
            issues.append(f"Tool returned {key}: {value}")
        if _is_energy_key(normalized_key) and value is not None and not _numeric_value(value):
            issues.append(f"Energy value for '{key}' is not numeric.")
        if _is_file_key(normalized_key) and isinstance(value, str):
            path = _existing_path(value, root)
            if path is None:
                issues.append(f"Returned file does not exist: {value}")

    _verify_expected_outputs(result, root, issues)
    return {"verified": not issues, "issues": _deduplicate(issues)}


def verify_execution(execution_result: dict[str, Any], workdir: str) -> dict[str, Any]:
    """Verify an executor result and all of its returned step data."""
    issues: list[str] = []
    if execution_result.get("success") is not True:
        issues.append("Execution result did not report success=true.")

    steps = execution_result.get("steps", [])
    if not isinstance(steps, list):
        issues.append("Execution result steps are missing or invalid.")
        steps = []

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            issues.append(f"Step {index} result is not a JSON object.")
            continue
        if "success" in step and step["success"] is not True:
            issues.append(f"Step {index} did not report success=true.")
        verification = verify_tool_result(step, workdir)
        issues.extend(f"Step {index}: {issue}" for issue in verification["issues"])
        _verify_step_xyz(step, Path(workdir), index, issues)

    return {"verified": not issues, "issues": _deduplicate(issues)}


def _walk(value: Any) -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            found.append((str(key), item))
            found.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk(item))
    return found


def _is_energy_key(key: str) -> bool:
    return (
        "energy" in key
        or "enthalpy" in key
        or "gap" in key
        or "frequenc" in key
        or key in {"g", "h", "zpe"}
    )


def _numeric_value(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, Real):
        return True
    if isinstance(value, list):
        return all(_numeric_value(item) for item in value)
    return False


def _is_file_key(key: str) -> bool:
    return key in {
        "path",
        "input_path",
        "input_xyz",
        "xyz_path",
        "optimized_xyz",
        "orca_input",
        "orca_output",
        "workflow_result_path",
        "result_path",
        "trajectory",
        "log",
        "input",
        "output",
    } or key.endswith("_file")


def _existing_path(value: str, root: Path) -> Path | None:
    path = Path(value).expanduser()
    candidates = [path] if path.is_absolute() else [path, root / path]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def _verify_expected_outputs(result: dict[str, Any], root: Path, issues: list[str]) -> None:
    for value in _dicts(result):
        if "task" in value and value["task"] in {"sp", "opt", "freq"}:
            output = value.get("files", {}).get("output") if isinstance(value.get("files"), dict) else None
            if not isinstance(output, str) or _existing_path(output, root) is None:
                issues.append("ORCA output file is missing after an ORCA job.")

        outputs = value.get("outputs")
        if isinstance(outputs, dict) and "optimized_xyz" in outputs:
            optimized_xyz = outputs["optimized_xyz"]
            if not isinstance(optimized_xyz, str) or _existing_path(optimized_xyz, root) is None:
                issues.append("xTB optimized XYZ file is missing after an xTB job.")


def _verify_step_xyz(
    step: dict[str, Any],
    root: Path,
    index: int,
    issues: list[str],
) -> None:
    if not _successful_step(step):
        return
    tool_name = str(step.get("tool_name", "")).lower()
    if not any(token in tool_name for token in ("molecule", "smiles_to_xyz", "xtb")):
        return

    xyz_paths = [
        value
        for key, value in _walk(step)
        if key.lower() in {"xyz_path", "optimized_xyz"} and isinstance(value, str)
    ]
    if not xyz_paths or not any(_existing_path(path, root) is not None for path in xyz_paths):
        issues.append(f"Step {index}: XYZ output file is missing after molecule/xTB step.")


def _successful_step(step: dict[str, Any]) -> bool:
    if "success" in step:
        return step["success"] is True
    return step.get("status") == "ok"


def _dicts(value: Any) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    if isinstance(value, dict):
        results.append(value)
        for item in value.values():
            results.extend(_dicts(item))
    elif isinstance(value, list):
        for item in value:
            results.extend(_dicts(item))
    return results


def _deduplicate(issues: list[str]) -> list[str]:
    return list(dict.fromkeys(issues))
