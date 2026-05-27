from __future__ import annotations

import html as html_lib
import json
from pathlib import Path
from typing import Any

from cspilot.prompts.system_prompts import get_profile


def make_report(
    user_request: str,
    tool_results: list[dict[str, Any]],
    verification: dict[str, Any],
) -> str:
    """Build a plain-text report strictly from returned tool data."""
    lines = [f"Request: {user_request}"]
    if verification.get("workdir"):
        lines.append(f"Workdir: {verification['workdir']}")
    if not tool_results:
        lines.append("No tool results were returned.")
    for index, result in enumerate(tool_results, start=1):
        name = str(result.get("tool_name", f"step_{index}"))
        status = result.get("status", "returned")
        lines.append(f"Step {index} ({name}): {status}.")
        workdir = result.get("workdir") or result.get("run_dir")
        if workdir and workdir != verification.get("workdir"):
            lines.append(f"Workdir: {workdir}")
        for key, value in _reported_values(result):
            lines.append(f"{key}: {value}")
        files = _generated_files(result)
        if files:
            lines.append("Generated files: " + ", ".join(files))

    if verification.get("verified"):
        lines.append("Verification: passed.")
    else:
        lines.append("Verification: failed or incomplete.")
        for issue in verification.get("issues", []):
            lines.append(f"Issue: {issue}")
    return "\n".join(lines)


def generate_report(
    user_request: str,
    plan: dict[str, Any],
    execution_result: dict[str, Any],
    verification_result: dict[str, Any],
    html: bool = False,
    profile: str = "chem",
) -> str:
    """Create a deterministic Markdown or HTML execution report."""
    selected_profile = get_profile(profile)
    sections = _report_sections(
        user_request,
        plan,
        execution_result,
        verification_result,
        profile,
        selected_profile.default_output_style,
    )
    if html:
        return _as_html(sections)
    return _as_markdown(sections)


def _report_sections(
    user_request: str,
    plan: dict[str, Any],
    execution_result: dict[str, Any],
    verification_result: dict[str, Any],
    profile: str,
    output_style: str,
) -> list[tuple[str, list[str]]]:
    workdir = str(execution_result.get("workdir", "not returned"))
    steps = plan.get("steps", []) if isinstance(plan.get("steps", []), list) else []
    results = (
        execution_result.get("steps", [])
        if isinstance(execution_result.get("steps", []), list)
        else []
    )

    plan_lines = [
        f"{index}. {step.get('tool', 'unknown tool')} with args {json.dumps(step.get('args', {}), sort_keys=True)}"
        for index, step in enumerate(steps, start=1)
        if isinstance(step, dict)
    ] or ["No planned steps returned."]
    completed_lines = [
        f"{index}. {step.get('tool_name', 'unknown tool')}: {_step_status(step)}"
        for index, step in enumerate(results, start=1)
        if isinstance(step, dict)
    ] or ["No executed steps returned."]

    key_values = _reported_values(execution_result)
    key_lines = [f"{key}: {_format_value(value)}" for key, value in key_values]
    keys_found = {key for key, _value in key_values}
    if not keys_found.intersection({"gibbs_free_energy", "gibbs_energy", "final_gibbs_energy"}):
        key_lines.append("Gibbs free energy: not found.")
    if not keys_found.intersection({"homo_lumo_gap", "homo_lumo_gap_ev"}):
        key_lines.append("HOMO-LUMO gap: not found.")

    generated_files = _report_files(execution_result, workdir)
    file_lines = generated_files or ["No generated files returned."]

    warnings = _warnings(execution_result, verification_result)
    return [
        ("Task", [user_request, f"Profile: {profile}", f"Output style: {output_style}", f"Workdir: {workdir}"]),
        ("Plan Summary", plan_lines),
        ("Completed Steps", completed_lines),
        ("Key Results", key_lines),
        ("Generated Files", file_lines),
        (
            "Verification Status",
            ["Passed." if verification_result.get("verified") else "Failed or incomplete."],
        ),
        ("Errors or Warnings", warnings or ["None reported."]),
    ]


def _as_markdown(sections: list[tuple[str, list[str]]]) -> str:
    lines: list[str] = ["# cspilot Execution Report"]
    for title, entries in sections:
        lines.extend(["", f"## {title}"])
        lines.extend(f"- {entry}" for entry in entries)
    return "\n".join(lines) + "\n"


def _as_html(sections: list[tuple[str, list[str]]]) -> str:
    body = ["<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">']
    body.extend(["<title>cspilot Execution Report</title>", "</head>", "<body>"])
    body.append("<h1>cspilot Execution Report</h1>")
    for title, entries in sections:
        body.append(f"<h2>{html_lib.escape(title)}</h2>")
        body.append("<ul>")
        body.extend(f"<li>{html_lib.escape(str(entry))}</li>" for entry in entries)
        body.append("</ul>")
    body.extend(["</body>", "</html>", ""])
    return "\n".join(body)


def _report_files(execution_result: dict[str, Any], workdir: str) -> list[str]:
    files = _generated_files(execution_result)
    root = Path(workdir)
    for name in ("plan.json", "execution_result.json", "verification_result.json"):
        candidate = root / name
        if candidate.exists():
            files.append(str(candidate))
    files.extend(str(path) for path in sorted(root.glob("step_*_result.json")) if path.exists())
    return list(dict.fromkeys(files))


def _step_status(step: dict[str, Any]) -> str:
    if "success" in step:
        return "success" if step["success"] is True else "failed"
    return str(step.get("status", "returned"))


def _warnings(
    execution_result: dict[str, Any],
    verification_result: dict[str, Any],
) -> list[str]:
    warnings = [str(issue) for issue in verification_result.get("issues", [])]
    for key, value in _walk(execution_result):
        if key.lower() in {"error", "error_message"} and value not in (None, ""):
            warnings.append(f"{key}: {value}")
    return list(dict.fromkeys(warnings))


def _format_value(value: Any) -> str:
    if isinstance(value, dict | list):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _reported_values(result: dict[str, Any]) -> list[tuple[str, Any]]:
    keys = {
        "final_energy",
        "final_energy_hartree",
        "electronic_energy",
        "total_energy",
        "energy_hartree",
        "gibbs_free_energy",
        "gibbs_energy",
        "final_gibbs_energy",
        "enthalpy",
        "homo_lumo_gap",
        "homo_lumo_gap_ev",
        "frequencies",
        "vibrational_frequencies",
        "formula",
        "natoms",
        "canonical_smiles",
    }
    reported: list[tuple[str, Any]] = []
    for key, value in _walk(result):
        if key in keys and value is not None:
            reported.append((key, value))
    return reported


def _generated_files(result: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key, value in _walk(result):
        if isinstance(value, str) and (
            (key.endswith("_path") and key not in {"input_path"})
            or key in {"optimized_xyz", "orca_input", "orca_output", "trajectory", "log", "input", "output"}
        ):
            values.append(str(Path(value)))
    return list(dict.fromkeys(values))


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
