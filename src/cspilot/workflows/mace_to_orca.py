from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from cspilot.config import Settings
from cspilot.tools.mace_tools import optimize_with_mace
from cspilot.tools.opi_orca_tools import orca_single_point
from cspilot.workflows._common import (
    base_workflow_result,
    copy_workflow_input,
    extract_final_energy,
    init_workflow_run,
    optimizer_failed,
    write_workflow_result,
)


def run_mace_to_orca(
    input_xyz: Path | str,
    charge: int = 0,
    mult: int = 1,
    method: str = "r2scan-3c",
    basis: str = "def2-SVP",
    model: Path | str | None = None,
    fmax: float = 0.05,
    steps: int = 200,
    nprocs: int = 1,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings, workdir = init_workflow_run("mace-orca", settings)
    result = base_workflow_result("mace-orca", input_xyz, workdir)

    input_copy = copy_workflow_input(input_xyz, workdir)
    model_path = Path(model or os.getenv("MACE_MODEL", "model_path")).expanduser()
    mace_dir = workdir / "01_mace_opt"
    mace_dir.mkdir()
    mace_input = copy_workflow_input(input_copy, mace_dir)
    mace_ok, mace_message, mace_outputs = optimize_with_mace(
        mace_input,
        mace_dir,
        model_path,
        fmax=fmax,
        steps=steps,
    )
    result["steps"]["mace_opt"] = {
        "status": "ok" if mace_ok else "skipped",
        "message": mace_message,
        "model": str(model_path),
        "outputs": mace_outputs,
    }

    optimized_xyz = Path(mace_outputs.get("optimized_xyz", mace_dir / "mace_opt.xyz"))
    if not mace_ok or not optimized_xyz.exists():
        optimizer_failed(result, "mace_opt", mace_message)
        write_workflow_result(workdir, result)
        return result

    orca_dir = workdir / "02_orca_sp"
    orca_result = orca_single_point(
        optimized_xyz,
        orca_dir,
        method,
        basis,
        charge=charge,
        mult=mult,
        nprocs=nprocs,
        orca_command=settings.orca_command,
    )
    result["steps"]["orca_sp"] = orca_result
    result["final_energy_hartree"] = extract_final_energy(orca_result)
    result["status"] = "ok" if orca_result.get("status") == "ok" else "failed"
    if result["status"] != "ok":
        result["message"] = orca_result.get("error_message", "ORCA single point failed")

    write_workflow_result(workdir, result)
    return result
