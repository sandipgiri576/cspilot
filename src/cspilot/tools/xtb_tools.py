from __future__ import annotations

from pathlib import Path

from cspilot.config import Settings
from cspilot.schemas import ProcessResult
from cspilot.utils.runner import executable_available, run_process


def optimize_with_xtb(
    input_file: Path,
    run_dir: Path,
    settings: Settings,
    charge: int,
    uhf: int,
) -> tuple[bool, str, ProcessResult | None, dict[str, str]]:
    if not executable_available(settings.xtb_command):
        return False, f"Executable not found: {settings.xtb_command}", None, {}

    command = [
        settings.xtb_command,
        input_file.name,
        "--opt",
        "--chrg",
        str(charge),
        "--uhf",
        str(uhf),
    ]
    process = run_process(command, cwd=run_dir)
    outputs = {
        "optimized_xyz": str(run_dir / "xtbopt.xyz"),
        "log": str(run_dir / "xtbopt.log"),
    }
    ok = process.returncode == 0
    message = "xTB optimization completed" if ok else "xTB optimization failed"
    return ok, message, process, outputs
