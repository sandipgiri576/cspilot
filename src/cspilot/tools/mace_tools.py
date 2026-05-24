from __future__ import annotations

from pathlib import Path
from typing import Any

from ase.optimize import BFGS

from cspilot.tools.ase_tools import load_structure, save_structure


def optimize_with_mace(
    input_file: Path,
    run_dir: Path,
    model_path: Path,
    fmax: float = 0.05,
    steps: int = 200,
) -> tuple[bool, str, dict[str, Any]]:
    try:
        from mace.calculators import MACECalculator
    except ImportError:
        return False, "Python package not found: mace-torch", {}

    if not model_path.exists():
        return False, f"MACE model not found: {model_path}", {}

    atoms = load_structure(input_file)
    atoms.calc = MACECalculator(model_paths=str(model_path), device="cpu", default_dtype="float64")

    trajectory = run_dir / "mace_opt.traj"
    logfile = run_dir / "mace_opt.log"
    optimizer = BFGS(atoms, trajectory=str(trajectory), logfile=str(logfile))
    optimizer.run(fmax=fmax, steps=steps)

    optimized_xyz = run_dir / "mace_opt.xyz"
    save_structure(atoms, optimized_xyz)
    return (
        True,
        "MACE optimization completed",
        {
            "optimized_xyz": str(optimized_xyz),
            "trajectory": str(trajectory),
            "log": str(logfile),
            "energy_ev": float(atoms.get_potential_energy()),
        },
    )
