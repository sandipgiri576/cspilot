from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from cspilot.config import Settings, load_settings
from cspilot.utils.runner import make_run_dir


def init_workflow_run(workflow_name: str, settings: Settings | None = None) -> tuple[Settings, Path]:
    settings = settings or load_settings()
    return settings, make_run_dir(settings.runs_dir, workflow_name)


def copy_workflow_input(input_xyz: Path | str, workdir: Path) -> Path:
    input_xyz = Path(input_xyz).resolve()
    target = workdir / "input.xyz"
    shutil.copy2(input_xyz, target)
    return target


def write_workflow_result(workdir: Path, result: dict[str, Any]) -> Path:
    result_path = workdir / "workflow_result.json"
    result["workflow_result_path"] = str(result_path)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result_path


def base_workflow_result(workflow: str, input_xyz: Path | str, workdir: Path) -> dict[str, Any]:
    return {
        "workflow": workflow,
        "status": "failed",
        "input_xyz": str(Path(input_xyz).resolve()),
        "workdir": str(workdir),
        "created_at": datetime.now().isoformat(),
        "steps": {},
        "final_energy_hartree": None,
    }


def extract_final_energy(orca_result: dict[str, Any]) -> float | None:
    properties = orca_result.get("result", {}).get("properties", {})
    energy = properties.get("final_energy_hartree")
    return float(energy) if energy is not None else None


def optimizer_failed(result: dict[str, Any], step_name: str, message: str) -> dict[str, Any]:
    result["status"] = "skipped"
    result["message"] = message
    result["failed_step"] = step_name
    return result
