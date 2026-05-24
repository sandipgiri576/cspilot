from __future__ import annotations

from pathlib import Path
from typing import Any

from cspilot.config import Settings
from cspilot.tools.opi_orca_tools import orca_frequency
from cspilot.tools.xtb_tools import optimize_with_xtb
from cspilot.workflows._common import (
    base_workflow_result,
    copy_workflow_input,
    extract_final_energy,
    init_workflow_run,
    optimizer_failed,
    write_workflow_result,
)


def run_xtb_to_orca_freq(
    input_xyz: Path | str,
    charge: int = 0,
    mult: int = 1,
    method: str = "r2scan-3c",
    basis: str = "def2-SVP",
    uhf: int = 0,
    nprocs: int = 1,
    settings: Settings | None = None,
) -> dict[str, Any]:
    settings, workdir = init_workflow_run("xtb-orca-freq", settings)
    result = base_workflow_result("xtb-orca-freq", input_xyz, workdir)

    input_copy = copy_workflow_input(input_xyz, workdir)
    xtb_dir = workdir / "01_xtb_opt"
    xtb_dir.mkdir()
    xtb_input = copy_workflow_input(input_copy, xtb_dir)
    xtb_ok, xtb_message, xtb_process, xtb_outputs = optimize_with_xtb(
        xtb_input,
        xtb_dir,
        settings,
        charge,
        uhf,
    )
    result["steps"]["xtb_opt"] = {
        "status": "ok" if xtb_ok else ("failed" if xtb_process is not None else "skipped"),
        "message": xtb_message,
        "outputs": xtb_outputs,
        "process": xtb_process.model_dump(mode="json") if xtb_process is not None else None,
    }

    optimized_xyz = Path(xtb_outputs.get("optimized_xyz", xtb_dir / "xtbopt.xyz"))
    if not xtb_ok or not optimized_xyz.exists():
        optimizer_failed(result, "xtb_opt", xtb_message)
        write_workflow_result(workdir, result)
        return result

    orca_dir = workdir / "02_orca_freq"
    orca_result = orca_frequency(
        optimized_xyz,
        orca_dir,
        method,
        basis,
        charge=charge,
        mult=mult,
        nprocs=nprocs,
        orca_command=settings.orca_command,
    )
    result["steps"]["orca_freq"] = orca_result
    result["final_energy_hartree"] = extract_final_energy(orca_result)
    result["status"] = "ok" if orca_result.get("status") == "ok" else "failed"
    if result["status"] != "ok":
        result["message"] = orca_result.get("error_message", "ORCA frequency failed")

    write_workflow_result(workdir, result)
    return result
