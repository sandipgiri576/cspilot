from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from cspilot.schemas import CommandResult, ProcessResult


def make_run_dir(base_dir: Path, command_name: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    run_dir = base_dir / f"{timestamp}-{command_name}"
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def copy_input(input_path: Path, run_dir: Path, name: str = "input.xyz") -> Path:
    target = run_dir / name
    shutil.copy2(input_path, target)
    return target


def run_process(command: list[str], cwd: Path) -> ProcessResult:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    return ProcessResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def executable_available(command: str) -> bool:
    return shutil.which(command) is not None


def write_json(path: Path, payload: CommandResult | dict[str, Any]) -> None:
    data = payload.model_dump(mode="json") if isinstance(payload, CommandResult) else payload
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
