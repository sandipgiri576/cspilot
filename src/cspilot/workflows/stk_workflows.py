from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from cspilot.config import load_settings
from cspilot.tools.stk_tools import stk_build_from_smiles, stk_export_to_xyz
from cspilot.tools.xtb_tools import optimize_with_xtb


def stk_smiles_to_xtb_opt(
    smiles: str,
    workdir: str | Path,
    charge: int = 0,
    uhf: int = 0,
) -> dict[str, Any]:
    """Build an stk molecule from SMILES, export XYZ, and run xTB optimization."""
    root = Path(workdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    build_path = root / "stk_build.mol"
    xyz_path = root / "stk_build.xyz"
    xtb_dir = root / "xtb_opt"
    xtb_dir.mkdir(parents=True, exist_ok=True)

    build_result = stk_build_from_smiles(smiles, str(build_path))
    export_result: dict[str, Any] | None = None
    xtb_result: dict[str, Any] | None = None
    success = bool(build_result.get("success"))
    error = None if success else build_result.get("error")

    if success:
        export_result = stk_export_to_xyz(str(build_path), str(xyz_path))
        success = bool(export_result.get("success"))
        error = None if success else export_result.get("error")

    if success:
        settings = load_settings()
        xtb_input = xtb_dir / xyz_path.name
        shutil.copyfile(xyz_path, xtb_input)
        ok, message, process, outputs = optimize_with_xtb(
            xtb_input,
            xtb_dir,
            settings,
            charge,
            uhf,
        )
        xtb_result = {
            "success": bool(ok),
            "status": "ok" if ok else ("failed" if process is not None else "skipped"),
            "message": message,
            "outputs": outputs,
            "process": process.model_dump(mode="json") if process is not None else None,
        }
        success = bool(ok)
        error = None if ok else message

    result = {
        "success": success,
        "workflow": "stk_smiles_to_xtb_opt",
        "workdir": str(root),
        "smiles": smiles,
        "charge": charge,
        "uhf": uhf,
        "steps": {
            "stk_build": build_result,
            "stk_export_xyz": export_result,
            "xtb_opt": xtb_result,
        },
        "output_path": str(xyz_path) if xyz_path.exists() else None,
        "error": error,
        "workflow_result_path": str(root / "workflow_result.json"),
    }
    (root / "workflow_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result

