from __future__ import annotations

from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from agents import function_tool

from cspilot.config import load_settings
from cspilot.tools.agapi_materials_tools import agapi_materials_query
from cspilot.tools.ase_tools import summarize_structure
from cspilot.tools.mace_tools import optimize_with_mace
from cspilot.tools.mol_tools import (
    canonicalize_smiles,
    molecule_name_to_smiles,
    molecule_name_to_xyz,
    smiles_to_xyz,
    validate_smiles,
)
from cspilot.tools.opi_orca_tools import orca_single_point
from cspilot.tools.result_tools import find_result_json, get_property_from_result
from cspilot.tools.xtb_tools import optimize_with_xtb
from cspilot.utils.runner import copy_input, make_run_dir
from cspilot.workflows.xtb_to_orca_freq import run_xtb_to_orca_freq
from cspilot.workflows.xtb_to_orca_sp import run_xtb_to_orca_sp

_agent_workdir: ContextVar[Path] = ContextVar("agent_workdir", default=Path("runs/agent_test"))


def set_agent_workdir(workdir: Path | str) -> Token[Path]:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    return _agent_workdir.set(workdir)


def reset_agent_workdir(token: Token[Path]) -> None:
    _agent_workdir.reset(token)


@function_tool
def inspect_structure(xyz_path: str) -> dict[str, Any]:
    """Inspect an XYZ structure and report values directly computed by ASE.

    Args:
        xyz_path: Path to an XYZ structure file.
    """
    try:
        summary = summarize_structure(Path(xyz_path).expanduser())
        return {"status": "ok", "structure": summary.model_dump(mode="json")}
    except Exception as exc:
        return _failure(exc)


@function_tool
def run_xtb_optimize(xyz_path: str, charge: int = 0, uhf: int = 0) -> dict[str, Any]:
    """Run xTB geometry optimization on an XYZ structure.

    Args:
        xyz_path: Path to an XYZ structure file.
        charge: Molecular charge.
        uhf: Number of unpaired electrons.
    """
    try:
        settings = load_settings()
        run_dir = make_run_dir(_agent_workdir.get(), "xtb-opt")
        run_input = copy_input(Path(xyz_path).expanduser(), run_dir)
        ok, message, process, outputs = optimize_with_xtb(
            run_input,
            run_dir,
            settings,
            charge,
            uhf,
        )
        return {
            "status": "ok" if ok else ("failed" if process is not None else "skipped"),
            "message": message,
            "run_dir": str(run_dir),
            "outputs": outputs,
            "process": process.model_dump(mode="json") if process is not None else None,
        }
    except Exception as exc:
        return _failure(exc)


@function_tool
def run_orca_single_point(
    xyz_path: str,
    method: str,
    basis: str,
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1,
) -> dict[str, Any]:
    """Run an ORCA single-point calculation using OPI.

    Args:
        xyz_path: Path to an XYZ structure file.
        method: ORCA method keyword.
        basis: ORCA basis keyword.
        charge: Molecular charge.
        mult: Spin multiplicity.
        nprocs: Number of ORCA processes.
    """
    try:
        settings = load_settings()
        run_dir = make_run_dir(_agent_workdir.get(), "orca-sp")
        return orca_single_point(
            xyz_path=Path(xyz_path).expanduser(),
            workdir=run_dir,
            method=method,
            basis=basis,
            charge=charge,
            mult=mult,
            nprocs=nprocs,
            orca_command=settings.orca_command,
        )
    except Exception as exc:
        return _failure(exc)


@function_tool
def run_mace_optimize(
    xyz_path: str,
    model_path: str,
    fmax: float = 0.05,
    steps: int = 200,
) -> dict[str, Any]:
    """Run MACE geometry optimization on an XYZ structure.

    Args:
        xyz_path: Path to an XYZ structure file.
        model_path: Path to a MACE model file.
        fmax: Force convergence threshold in eV/A.
        steps: Maximum optimization steps.
    """
    try:
        run_dir = make_run_dir(_agent_workdir.get(), "mace-opt")
        run_input = copy_input(Path(xyz_path).expanduser(), run_dir)
        ok, message, outputs = optimize_with_mace(
            run_input,
            run_dir,
            Path(model_path).expanduser(),
            fmax=fmax,
            steps=steps,
        )
        return {
            "status": "ok" if ok else "skipped",
            "message": message,
            "run_dir": str(run_dir),
            "outputs": outputs,
        }
    except Exception as exc:
        return _failure(exc)


@function_tool
def run_xtb_orca_workflow(
    xyz_path: str,
    method: str = "r2scan-3c",
    basis: str = "def2-SVP",
    charge: int = 0,
    mult: int = 1,
    uhf: int = 0,
    nprocs: int = 1,
) -> dict[str, Any]:
    """Run xTB optimization followed by an ORCA single point using OPI.

    Args:
        xyz_path: Path to an XYZ structure file.
        method: ORCA method keyword.
        basis: ORCA basis keyword.
        charge: Molecular charge.
        mult: Spin multiplicity.
        uhf: Number of unpaired electrons for xTB.
        nprocs: Number of ORCA processes.
    """
    try:
        settings = load_settings().model_copy(update={"runs_dir": _agent_workdir.get()})
        return run_xtb_to_orca_sp(
            input_xyz=Path(xyz_path).expanduser(),
            charge=charge,
            mult=mult,
            method=method,
            basis=basis,
            uhf=uhf,
            nprocs=nprocs,
            settings=settings,
        )
    except Exception as exc:
        return _failure(exc)


@function_tool
def run_xtb_orca_frequency_workflow(
    xyz_path: str,
    method: str = "r2scan-3c",
    basis: str = "def2-SVP",
    charge: int = 0,
    mult: int = 1,
    uhf: int = 0,
    nprocs: int = 1,
) -> dict[str, Any]:
    """Run xTB optimization followed by an ORCA frequency calculation using OPI.

    Args:
        xyz_path: Path to an XYZ structure file.
        method: ORCA method keyword.
        basis: ORCA basis keyword.
        charge: Molecular charge.
        mult: Spin multiplicity.
        uhf: Number of unpaired electrons for xTB.
        nprocs: Number of ORCA processes.
    """
    try:
        settings = load_settings().model_copy(update={"runs_dir": _agent_workdir.get()})
        return run_xtb_to_orca_freq(
            input_xyz=Path(xyz_path).expanduser(),
            charge=charge,
            mult=mult,
            method=method,
            basis=basis,
            uhf=uhf,
            nprocs=nprocs,
            settings=settings,
        )
    except Exception as exc:
        return _failure(exc)


@function_tool
def molecule_name_to_smiles_tool(name: str) -> dict[str, Any]:
    """Look up the SMILES representation of a molecule name from PubChem.

    Args:
        name: Common or systematic molecule name.
    """
    return molecule_name_to_smiles(name)


@function_tool
def smiles_to_xyz_tool(
    smiles: str,
    output_path: str,
    num_confs: int = 20,
    forcefield: str = "MMFF",
) -> dict[str, Any]:
    """Create a minimized XYZ structure from SMILES with RDKit.

    Args:
        smiles: Input SMILES string.
        output_path: Output XYZ file path.
        num_confs: Number of conformers to generate.
        forcefield: Optimization forcefield, MMFF or UFF.
    """
    return smiles_to_xyz(smiles, output_path, num_confs=num_confs, forcefield=forcefield)


@function_tool
def molecule_name_to_xyz_tool(
    name: str,
    output_path: str,
    num_confs: int = 20,
) -> dict[str, Any]:
    """Resolve a molecule name through PubChem and write an RDKit XYZ structure.

    Args:
        name: Common or systematic molecule name.
        output_path: Output XYZ file path.
        num_confs: Number of conformers to generate.
    """
    return molecule_name_to_xyz(name, output_path, num_confs=num_confs)


@function_tool
def validate_smiles_tool(smiles: str) -> dict[str, Any]:
    """Check whether a SMILES string is valid using RDKit.

    Args:
        smiles: SMILES string to validate.
    """
    return validate_smiles(smiles)


@function_tool
def canonicalize_smiles_tool(smiles: str) -> dict[str, Any]:
    """Canonicalize a SMILES string using RDKit.

    Args:
        smiles: SMILES string to canonicalize.
    """
    return canonicalize_smiles(smiles)


@function_tool
def find_result_json_tool(workdir: str, latest: bool = True) -> dict[str, Any]:
    """Find calculation result JSON files in a run directory.

    Args:
        workdir: Directory to search recursively.
        latest: If true, identify the newest matched result file.
    """
    return find_result_json(workdir, latest=latest)


@function_tool
def get_property_from_result_tool(path: str, property_name: str) -> dict[str, Any]:
    """Extract a stored property from a result JSON file using supported aliases.

    Args:
        path: Path to a result JSON file.
        property_name: Requested property name, for example Gibbs free energy.
    """
    return get_property_from_result(path, property_name)


@function_tool(name_override="find_result_json")
def find_result_json_agent_tool(workdir: str, latest: bool = True) -> dict[str, Any]:
    """Find calculation result JSON files from a previous run directory.

    Args:
        workdir: Directory to search recursively.
        latest: If true, identify the newest matched result file.
    """
    return find_result_json(workdir, latest=latest)


@function_tool(name_override="get_property_from_result")
def get_property_from_result_agent_tool(path: str, property_name: str) -> dict[str, Any]:
    """Extract a requested property from a previous calculation result JSON file.

    Args:
        path: Path to a result JSON file.
        property_name: Requested property name, for example Gibbs free energy.
    """
    return get_property_from_result(path, property_name)


@function_tool
def agapi_materials_query_tool(query: str, render_html: bool = False) -> dict[str, Any]:
    """Query optional AGAPI materials search capabilities.

    Args:
        query: Natural-language materials query.
        render_html: Whether AGAPI should return an HTML representation.
    """
    return agapi_materials_query(query, render_html=render_html)


def _failure(exc: Exception) -> dict[str, str]:
    return {"status": "failed", "message": f"{type(exc).__name__}: {exc}"}
