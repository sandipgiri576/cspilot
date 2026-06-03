from __future__ import annotations

from pathlib import Path
from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


def print_banner(console: Console) -> None:
    title = Text("CSPilot", style="bold cyan")
    subtitle = "Computational chemistry agentic workflow package\nCreated by Sandip Giri"
    console.print(Panel(subtitle, title=title, border_style="cyan", box=box.ROUNDED))


def print_plan_summary(console: Console, plan: dict[str, Any]) -> None:
    table = Table(title="Plan", box=box.SIMPLE_HEAVY)
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Tool", style="bold")
    table.add_column("Arguments")
    steps = plan.get("steps") if isinstance(plan, dict) else []
    if isinstance(steps, list) and steps:
        for index, step in enumerate(steps, start=1):
            args = step.get("args", {}) if isinstance(step, dict) else {}
            table.add_row(str(index), str(step.get("tool", "unknown")), _short_dict(args))
    else:
        table.add_row("-", "No planned steps", "")
    console.print(table)


def print_execution_summary(console: Console, execution_result: dict[str, Any]) -> None:
    success = execution_result.get("success") is True
    status = "PASSED" if success else "FAILED"
    style = "green" if success else "red"
    table = Table(title="Execution", box=box.SIMPLE_HEAVY)
    table.add_column("#", justify="right", style="cyan")
    table.add_column("Tool", style="bold")
    table.add_column("Status")
    steps = execution_result.get("steps") if isinstance(execution_result, dict) else []
    if isinstance(steps, list) and steps:
        for index, step in enumerate(steps, start=1):
            if isinstance(step, dict):
                table.add_row(str(index), str(step.get("tool_name", step.get("tool", "unknown"))), _status(step))
    else:
        table.add_row("-", "No executed steps", status)
    console.print(Panel(f"[{style}]{status}[/]", title="Execution Status", border_style=style))
    console.print(table)


def print_verification_summary(console: Console, verification_result: dict[str, Any]) -> None:
    verified = verification_result.get("verified") is True
    status = "PASSED" if verified else "FAILED OR INCOMPLETE"
    style = "green" if verified else "yellow"
    issues = verification_result.get("issues", [])
    body = f"[{style}]{status}[/]"
    if issues:
        body += "\n" + "\n".join(f"- {issue}" for issue in issues)
    console.print(Panel(body, title="Verification", border_style=style))


def print_generated_files(console: Console, workdir: str | Path, execution_result: dict[str, Any]) -> None:
    files = _discover_files(Path(workdir), execution_result)
    table = Table(title="Generated Files", box=box.SIMPLE_HEAVY)
    table.add_column("Type", style="cyan")
    table.add_column("Path")
    if files:
        for kind, path in files:
            table.add_row(kind, str(path))
    else:
        table.add_row("none", "No generated files found.")
    console.print(table)
    for kind, path in files:
        if kind == "ORCA output":
            console.print(f"Your ORCA output file is available at: [bold]{path}[/]")
        elif kind == "Optimized geometry":
            console.print(f"Your optimized geometry is available at: [bold]{path}[/]")


def print_final_message(console: Console, final_report: str, html: bool = False) -> None:
    label = "HTML report" if html else "Markdown report"
    preview = _preview(final_report)
    console.print(Panel(preview or "Report generated.", title=label, border_style="blue"))


def _discover_files(workdir: Path, execution_result: dict[str, Any]) -> list[tuple[str, Path]]:
    candidates: list[Path] = []
    for name in (
        "plan.json",
        "execution_result.json",
        "verification_result.json",
        "final_state.json",
        "final_report.md",
        "final_report.html",
    ):
        path = workdir / name
        if path.exists():
            candidates.append(path)
    candidates.extend(_paths_from_result(execution_result, workdir))
    candidates.extend(workdir.rglob("*.out"))
    candidates.extend(workdir.rglob("*.xyz"))
    candidates.extend(workdir.rglob("xtbopt.log"))
    candidates.extend(workdir.rglob("*.log"))
    unique = list(dict.fromkeys(path for path in candidates if path.exists()))
    return [(_file_kind(path), path) for path in unique]


def _paths_from_result(value: Any, workdir: Path) -> list[Path]:
    paths: list[Path] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if isinstance(item, str) and _looks_like_file_key(str(key)):
                paths.append(_resolve(workdir, item))
            else:
                paths.extend(_paths_from_result(item, workdir))
    elif isinstance(value, list):
        for item in value:
            paths.extend(_paths_from_result(item, workdir))
    return paths


def _looks_like_file_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.endswith("_path") or lowered in {
        "optimized_xyz",
        "orca_input",
        "orca_output",
        "stdout_file",
        "stderr_file",
        "trajectory",
        "log",
        "input",
        "output",
    }


def _resolve(workdir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else workdir / path


def _file_kind(path: Path) -> str:
    name = path.name.lower()
    if name in {"plan.json", "execution_result.json", "verification_result.json", "final_state.json"}:
        return "JSON"
    if name.startswith("final_report"):
        return "Report"
    if name.endswith(".xyz") and ("opt" in name or "lowest" in name):
        return "Optimized geometry"
    if name.endswith(".xyz"):
        return "XYZ"
    if "orca" in name and name.endswith((".out", ".log")):
        return "ORCA output"
    if "xtb" in name:
        return "xTB output"
    return "File"


def _short_dict(value: Any) -> str:
    if not isinstance(value, dict):
        return str(value)
    parts = [f"{key}={item}" for key, item in value.items()]
    text = ", ".join(parts)
    return text if len(text) <= 120 else text[:117] + "..."


def _status(step: dict[str, Any]) -> str:
    if step.get("success") is True:
        return "[green]success[/]"
    if step.get("success") is False:
        return "[red]failed[/]"
    return str(step.get("status", "returned"))


def _preview(report: str) -> str:
    lines = [line for line in report.strip().splitlines() if line.strip()]
    preview = "\n".join(lines[:8])
    return preview[:1200]
