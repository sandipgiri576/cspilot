from __future__ import annotations

import importlib.util
from pathlib import Path

from ase.io import write

from cspilot.config import Settings
from cspilot.schemas import ProcessResult
from cspilot.tools.ase_tools import load_structure
from cspilot.utils.runner import executable_available, run_process


def opi_available() -> bool:
    return importlib.util.find_spec("opi") is not None


def write_orca_input(
    structure_path: Path,
    run_dir: Path,
    method: str,
    basis: str,
    charge: int,
    mult: int,
) -> Path:
    atoms = load_structure(structure_path)
    xyz_path = run_dir / "input.xyz"
    inp_path = run_dir / "orca.inp"
    write(xyz_path, atoms)

    try:
        from opi.input.core import Input, SimpleKeyword
        from opi.input.structures import XyzFile

        orca_input = Input()
        orca_input.add_simple_keywords(SimpleKeyword(method), SimpleKeyword(basis))
        xyz_file = XyzFile(xyz_path, charge=charge, multiplicity=mult)
        text = f"{orca_input.format_before_coords()}\n{xyz_file.format_orca(run_dir)}\n"
    except ImportError:
        text = "\n".join([f"! {method} {basis}", "", f"* xyzfile {charge} {mult} {xyz_path.name}", ""])

    inp_path.write_text(text, encoding="utf-8")
    return inp_path


def single_point_with_orca(
    input_file: Path,
    run_dir: Path,
    settings: Settings,
    method: str,
    basis: str,
    charge: int,
    mult: int,
) -> tuple[bool, str, ProcessResult | None, dict[str, str | bool]]:
    inp_path = write_orca_input(input_file, run_dir, method, basis, charge, mult)
    outputs: dict[str, str | bool] = {
        "orca_input": str(inp_path),
        "orca_output": str(run_dir / "orca.out"),
        "opi_available": opi_available(),
    }

    if not executable_available(settings.orca_command):
        return False, f"Executable not found: {settings.orca_command}", None, outputs

    process = run_process([settings.orca_command, inp_path.name], cwd=run_dir)
    ok = process.returncode == 0
    message = "ORCA single point completed" if ok else "ORCA single point failed"
    return ok, message, process, outputs
