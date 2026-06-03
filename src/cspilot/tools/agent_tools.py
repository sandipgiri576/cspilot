from __future__ import annotations

from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from agents import function_tool

from cspilot.config import load_settings
from cspilot.tools.agapi_materials_tools import agapi_materials_query
from cspilot.tools.ase_tools import summarize_structure
from cspilot.tools.greencatai_tools import greencatai_design_mbh_catalysts
from cspilot.tools.mace_tools import optimize_with_mace
from cspilot.tools.mol_tools import (
    canonicalize_smiles,
    molecule_name_to_smiles,
    molecule_name_to_xyz,
    smiles_to_xyz,
    validate_smiles,
)
from cspilot.tools.nwpesse_tools import parse_cluster_formula
from cspilot.tools.opi_orca_tools import orca_single_point
from cspilot.tools.result_tools import find_result_json, get_property_from_result
from cspilot.tools.stk_tools import (
    rdkit_replace_substructure,
    stk_build_from_smiles,
    stk_building_block_from_file,
    stk_construct_cage_from_smiles,
    stk_export_to_xyz,
    stk_linear_polymer_from_smiles,
)
from cspilot.tools.xtb_tools import optimize_with_xtb
from cspilot.utils.runner import copy_input, make_run_dir
from cspilot.workflows.nwpesse_workflows import nwpesse_global_minimum_search
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


@function_tool
def design_mbh_catalysts_tool(
    output_dir: str,
    search_space: str = "configs/search_space.json",
    scoring: str = "configs/scoring.json",
    library: str | None = None,
    max_candidates: int = 100,
    generations: int = 3,
    population_size: int = 30,
    top_n_xtb: int = 0,
    top_n_orca: int = 0,
) -> dict[str, Any]:
    """Run GreenCatAI MBH catalyst design through its public API.

    Args:
        output_dir: Directory where GreenCatAI should write design artifacts.
        search_space: GreenCatAI search-space JSON path.
        scoring: GreenCatAI scoring JSON path.
        library: Optional validated external amine library JSON path.
        max_candidates: Maximum seed candidates to generate.
        generations: Number of GA generations.
        population_size: Candidate population size.
        top_n_xtb: Number of top candidates to pass to xTB in GreenCatAI.
        top_n_orca: Number of top candidates to pass to ORCA in GreenCatAI.
    """
    return greencatai_design_mbh_catalysts(
        output_dir=output_dir,
        search_space=search_space,
        scoring=scoring,
        library=library,
        max_candidates=max_candidates,
        generations=generations,
        population_size=population_size,
        top_n_xtb=top_n_xtb,
        top_n_orca=top_n_orca,
    )


@function_tool
def stk_build_from_smiles_tool(
    smiles: str,
    output_path: str,
) -> dict[str, Any]:
    """Create an stk building block from SMILES and export it.

    Args:
        smiles: Input SMILES string.
        output_path: Output molecule path ending in .mol, .sdf, or .xyz.
    """
    result = stk_build_from_smiles(smiles, output_path)
    result["tool"] = "stk_build_from_smiles_tool"
    result["smiles"] = smiles
    result["output_file"] = str(result.get("output_file") or result.get("output_path") or output_path)
    result["generated_files"] = list(
        dict.fromkeys([*result.get("generated_files", []), result["output_file"]])
    )
    return result


@function_tool
def stk_building_block_from_file_tool(
    input_path: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Load an stk building block from a molecule file and optionally export it.

    Args:
        input_path: Input molecule file path.
        output_path: Optional output molecule path ending in .mol, .sdf, or .xyz.
    """
    return stk_building_block_from_file(input_path, output_path)


@function_tool
def stk_linear_polymer_from_smiles_tool(
    monomer_smiles: str,
    repeating_unit: str,
    num_repeating_units: int,
    output_path: str,
) -> dict[str, Any]:
    """Construct a linear polymer using stk.polymer.Linear.

    Args:
        monomer_smiles: Monomer building-block SMILES.
        repeating_unit: stk repeating unit string.
        num_repeating_units: Number of repeat units.
        output_path: Output molecule path ending in .mol, .sdf, or .xyz.
    """
    return stk_linear_polymer_from_smiles(
        monomer_smiles,
        repeating_unit,
        num_repeating_units,
        output_path,
    )


@function_tool
def stk_construct_cage_from_smiles_tool(
    building_block_smiles: list[str],
    topology: str,
    output_path: str,
) -> dict[str, Any]:
    """Return unsupported until safe cage presets are implemented.

    Args:
        building_block_smiles: Building-block SMILES strings.
        topology: Requested topology name.
        output_path: Output molecule path ending in .mol, .sdf, or .xyz.
    """
    return stk_construct_cage_from_smiles(building_block_smiles, topology, output_path)


@function_tool
def rdkit_replace_substructure_tool(
    parent_smiles: str,
    old_smarts: str,
    new_smiles: str,
    output_path: str,
) -> dict[str, Any]:
    """Replace a SMILES substructure with RDKit and export the edited molecule.

    Args:
        parent_smiles: Parent molecule SMILES.
        old_smarts: SMARTS pattern to replace.
        new_smiles: Replacement SMILES.
        output_path: Output molecule path ending in .mol, .sdf, or .xyz.
    """
    return rdkit_replace_substructure(parent_smiles, old_smarts, new_smiles, output_path)


@function_tool
def stk_export_to_xyz_tool(input_path: str, output_path: str) -> dict[str, Any]:
    """Export a molecule file to XYZ using stk with RDKit fallback.

    Args:
        input_path: Input molecule file.
        output_path: Output XYZ path.
    """
    return stk_export_to_xyz(input_path, output_path)


@function_tool
def parse_cluster_formula_tool(formula: str) -> dict[str, Any]:
    """Parse a NWPESSe cluster formula into fragment/count records.

    Args:
        formula: Fragment formula such as (h2o)4Mg or h2o:4,mg:1.
    """
    return parse_cluster_formula(formula)


@function_tool
def nwpesse_global_minimum_search_tool(
    formula: str | None = None,
    fragments: list[str] | None = None,
    workdir: str = "runs/nwpesse",
    result_name: str = "nwpesse_result",
    max_calculations: int = 10,
    box_size: float = 3.0,
    box_mode: str = "per_fragment_type",
    optimizer: str = "xtb_gxtb",
    fragment_dir: str | None = None,
    timeout: int = 86400,
) -> dict[str, Any]:
    """Run an NWPESSe global-minimum search from fragment definitions.

    Args:
        formula: Fragment formula such as (h2o)4Mg. Do not use PubChem for this.
        fragments: Optional explicit fragment counts as name:count strings.
        workdir: Directory for NWPESSe input, output, and workflow JSON.
        result_name: NWPESSe result base name.
        max_calculations: Maximum number of candidate calculations.
        box_size: Cubic inbox size.
        box_mode: Placement mode: per_fragment_type or single. Custom boxes are not accepted from the agent tool.
        optimizer: Whitelisted optimizer block name.
        fragment_dir: Optional directory containing fragment xyz files.
        timeout: External NWPESSe timeout in seconds.
    """
    root = _agent_workdir.get() / Path(workdir).name if not Path(workdir).is_absolute() else Path(workdir)
    fragment_records = _parse_fragment_strings(fragments or [])
    return nwpesse_global_minimum_search(
        formula=formula,
        fragments=fragment_records or None,
        workdir=str(root),
        result_name=result_name,
        max_calculations=max_calculations,
        box_size=box_size,
        box_mode=box_mode,
        optimizer=optimizer,
        fragment_dir=fragment_dir,
        timeout=timeout,
    )


def _failure(exc: Exception) -> dict[str, str]:
    return {"status": "failed", "message": f"{type(exc).__name__}: {exc}"}


def _parse_fragment_strings(values: list[str]) -> list[dict[str, object]]:
    fragments = []
    for value in values:
        name, separator, count = value.partition(":")
        if separator != ":" or not name.strip() or not count.strip().isdigit():
            raise ValueError(f"Fragment must be name:count, got {value!r}.")
        fragments.append({"name": name.strip().lower(), "count": int(count)})
    return fragments
