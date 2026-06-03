from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import AllChem

SUPPORTED_POLYMER_TOPOLOGIES = {"linear"}
SUPPORTED_CAGE_TOPOLOGIES: dict[str, str] = {}
SUPPORTED_OUTPUT_EXTENSIONS = {".mol", ".sdf", ".xyz"}
_STK_IMPORT_SAFE: bool | None = None


def stk_build_from_smiles(smiles: str, output_path: str) -> dict[str, Any]:
    """Create an stk BuildingBlock from SMILES and write it to a molecule file."""
    tool = "stk_build_from_smiles"
    output = Path(output_path).expanduser()
    metadata: dict[str, Any] = {"smiles": smiles}
    try:
        try:
            stk = _import_stk()
            molecule = stk.BuildingBlock(smiles)
            metadata["num_atoms"] = _num_atoms(molecule)
            metadata["source"] = "stk.BuildingBlock"
            _write_molecule_with_fallback(molecule, output, smiles=smiles, metadata=metadata)
        except RuntimeError as stk_exc:
            molecule = _mol_from_smiles(smiles, "smiles")
            metadata["source"] = "rdkit"
            metadata["fallback"] = "rdkit_smiles_build"
            metadata["stk_error"] = str(stk_exc)
            metadata["num_atoms"] = int(molecule.GetNumAtoms())
            _write_rdkit_structure(molecule, output)
        result = _result(tool, True, output, None, metadata)
        result["smiles"] = smiles
        result["output_file"] = str(output)
        result["generated_files"] = [str(output)]
        return _finalize(result)
    except Exception as exc:
        return _finalize(_result(tool, False, output, _format_error(exc), metadata))


def stk_building_block_from_file(input_path: str, output_path: str | None = None) -> dict[str, Any]:
    """Load an stk BuildingBlock from a molecule file and optionally export it."""
    tool = "stk_building_block_from_file"
    input_file = Path(input_path).expanduser()
    output = Path(output_path).expanduser() if output_path else None
    metadata: dict[str, Any] = {"input_path": str(input_file)}
    try:
        stk = _import_stk()
        molecule = stk.BuildingBlock.init_from_file(str(input_file))
        metadata["num_atoms"] = _num_atoms(molecule)
        metadata["source"] = "stk.BuildingBlock.init_from_file"
        if output is not None:
            _write_molecule_with_fallback(molecule, output, smiles=None, metadata=metadata)
        return _finalize(_result(tool, True, output, None, metadata), anchor=input_file)
    except Exception as exc:
        return _finalize(_result(tool, False, output, _format_error(exc), metadata), anchor=input_file)


def stk_linear_polymer_from_smiles(
    monomer_smiles: str,
    repeating_unit: str,
    num_repeating_units: int,
    output_path: str,
) -> dict[str, Any]:
    """Construct a linear polymer with stk.polymer.Linear."""
    tool = "stk_linear_polymer_from_smiles"
    output = Path(output_path).expanduser()
    metadata: dict[str, Any] = {
        "monomer_smiles": monomer_smiles,
        "topology": "linear",
        "repeating_unit": repeating_unit,
        "num_repeating_units": num_repeating_units,
    }
    if num_repeating_units < 1:
        return _finalize(
            _result(tool, False, output, "num_repeating_units must be at least 1", metadata)
        )
    try:
        stk = _import_stk()
        functional_groups = _polymer_functional_groups(stk, monomer_smiles)
        building_block = stk.BuildingBlock(monomer_smiles, functional_groups)
        metadata["functional_groups"] = [fg.__class__.__name__ for fg in functional_groups]
        topology_graph = stk.polymer.Linear(
            building_blocks=(building_block,),
            repeating_unit=repeating_unit,
            num_repeating_units=num_repeating_units,
            orientations=(0,),
        )
        molecule = stk.ConstructedMolecule(topology_graph)
        metadata["num_atoms"] = _num_atoms(molecule)
        metadata["source"] = "stk.ConstructedMolecule/stk.polymer.Linear"
        _write_molecule_with_fallback(molecule, output, smiles=None, metadata=metadata)
        return _finalize(_result(tool, True, output, None, metadata))
    except Exception as exc:
        return _finalize(_result(tool, False, output, _format_error(exc), metadata))


def stk_construct_cage_from_smiles(
    building_block_smiles: list[str],
    topology: str,
    output_path: str,
) -> dict[str, Any]:
    """Return unsupported until a safe cage topology/functional-group preset is added."""
    normalized = topology.strip().lower().replace("-", "_")
    metadata = {
        "building_block_smiles": list(building_block_smiles),
        "requested_topology": normalized,
        "supported_topologies": sorted(SUPPORTED_CAGE_TOPOLOGIES),
        "planned": True,
    }
    return _finalize(
        _result(
            "stk_construct_cage_from_smiles",
            False,
            Path(output_path).expanduser(),
            "Cage construction is not enabled yet. It requires topology-specific "
            "functional-group presets; supported_topologies is currently empty.",
            metadata,
        )
    )


def rdkit_replace_substructure(
    parent_smiles: str,
    old_smarts: str,
    new_smiles: str,
    output_path: str,
) -> dict[str, Any]:
    """Replace a substructure with RDKit and export the edited molecule."""
    tool = "rdkit_replace_substructure"
    output = Path(output_path).expanduser()
    metadata: dict[str, Any] = {
        "parent_smiles": parent_smiles,
        "old_smarts": old_smarts,
        "new_smiles": new_smiles,
    }
    try:
        parent = _mol_from_smiles(parent_smiles, "parent_smiles")
        old = Chem.MolFromSmarts(old_smarts)
        if old is None:
            raise ValueError("old_smarts is not a valid SMARTS pattern")
        new = _mol_from_smiles(new_smiles, "new_smiles")
        replacements = Chem.ReplaceSubstructs(parent, old, new, replaceAll=True)
        if not replacements:
            return _finalize(_result(tool, False, output, "Substructure not found", metadata))
        edited = replacements[0]
        Chem.SanitizeMol(edited)
        edited_smiles = Chem.MolToSmiles(edited)
        metadata["edited_smiles"] = edited_smiles
        metadata["num_atoms"] = int(edited.GetNumAtoms())
        _write_rdkit_structure(edited, output)
        return _finalize(_result(tool, True, output, None, metadata))
    except Exception as exc:
        return _finalize(_result(tool, False, output, _format_error(exc), metadata))


def stk_export_to_xyz(input_path: str, output_path: str) -> dict[str, Any]:
    """Export a molecule file to XYZ with stk first, then RDKit/ASE-style fallback."""
    tool = "stk_export_to_xyz"
    input_file = Path(input_path).expanduser()
    output = Path(output_path).expanduser()
    metadata: dict[str, Any] = {"input_path": str(input_file)}
    if output.suffix.lower() != ".xyz":
        return _finalize(_result(tool, False, output, "output_path must end with .xyz", metadata))
    try:
        stk = _import_stk()
        molecule = stk.BuildingBlock.init_from_file(str(input_file))
        metadata["source"] = "stk.BuildingBlock.init_from_file"
        metadata["num_atoms"] = _num_atoms(molecule)
        _write_molecule_with_fallback(molecule, output, smiles=None, metadata=metadata)
        return _finalize(_result(tool, True, output, None, metadata), anchor=input_file)
    except Exception as stk_exc:
        metadata["stk_error"] = _format_error(stk_exc)
        try:
            if input_file.suffix.lower() == ".xyz":
                _ensure_parent(output)
                shutil.copyfile(input_file, output)
                metadata["fallback"] = "copy_xyz"
                return _finalize(_result(tool, True, output, None, metadata), anchor=input_file)
            molecule = _rdkit_mol_from_file(input_file)
            _write_rdkit_structure(molecule, output)
            metadata["source"] = "rdkit"
            metadata["num_atoms"] = int(molecule.GetNumAtoms())
            metadata["fallback"] = "rdkit"
            return _finalize(_result(tool, True, output, None, metadata), anchor=input_file)
        except Exception as exc:
            return _finalize(_result(tool, False, output, _format_error(exc), metadata), anchor=input_file)


def _import_stk() -> Any:
    os.environ.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    os.environ.setdefault("MPLCONFIGDIR", "/tmp/cspilot-matplotlib")
    if not _stk_import_is_safe():
        raise RuntimeError(
            "Python package stk is installed but cannot be imported safely in this "
            "environment. A dependency aborted the interpreter; install a CPU-compatible "
            "stk/polars stack, for example polars[rtcompat]."
        )
    try:
        import stk
    except ImportError as exc:
        raise RuntimeError("Python package not found: stk. Install cspilot[stk].") from exc
    return stk


def _stk_import_is_safe() -> bool:
    global _STK_IMPORT_SAFE
    if _STK_IMPORT_SAFE is not None:
        return _STK_IMPORT_SAFE
    env = os.environ.copy()
    env.setdefault("POLARS_SKIP_CPU_CHECK", "1")
    env.setdefault("MPLCONFIGDIR", "/tmp/cspilot-matplotlib")
    process = subprocess.run(
        [sys.executable, "-c", "import stk"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    _STK_IMPORT_SAFE = process.returncode == 0
    return _STK_IMPORT_SAFE


def _polymer_functional_groups(stk: Any, smiles: str) -> tuple[Any, ...]:
    factories = []
    if "Br" in smiles:
        factories.append(stk.BromoFactory())
    if not factories:
        raise ValueError(
            "No supported polymer functional group detected. Initial polymer support "
            "expects brominated monomers such as BrCCBr."
        )
    return tuple(factories)


def _write_molecule_with_fallback(
    molecule: Any,
    output_path: Path,
    smiles: str | None,
    metadata: dict[str, Any],
) -> None:
    suffix = output_path.suffix.lower()
    if suffix not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ValueError(f"Unsupported output extension: {suffix}. Use .mol, .sdf, or .xyz.")
    _ensure_parent(output_path)
    try:
        molecule.write(str(output_path))
        metadata["writer"] = "stk.write"
        return
    except Exception as stk_exc:
        metadata["stk_write_error"] = _format_error(stk_exc)
        if suffix != ".xyz":
            raise
    if smiles is not None:
        rdkit_mol = _mol_from_smiles(smiles, "smiles")
        _write_rdkit_structure(rdkit_mol, output_path)
        metadata["writer"] = "rdkit_xyz_from_smiles"
        return
    temp_mol = output_path.with_suffix(".mol")
    molecule.write(str(temp_mol))
    rdkit_mol = _rdkit_mol_from_file(temp_mol)
    _write_rdkit_structure(rdkit_mol, output_path)
    metadata["writer"] = "stk_mol_then_rdkit_xyz"
    metadata["fallback_mol_path"] = str(temp_mol)


def _write_rdkit_structure(molecule: Chem.Mol, output_path: Path) -> None:
    suffix = output_path.suffix.lower()
    if suffix not in SUPPORTED_OUTPUT_EXTENSIONS:
        raise ValueError(f"Unsupported output extension: {suffix}. Use .mol, .sdf, or .xyz.")
    _ensure_parent(output_path)
    molecule = Chem.AddHs(molecule)
    status = AllChem.EmbedMolecule(molecule, AllChem.ETKDGv3())
    if status != 0:
        AllChem.Compute2DCoords(molecule)
    if AllChem.MMFFHasAllMoleculeParams(molecule):
        AllChem.MMFFOptimizeMolecule(molecule, maxIters=200)
    else:
        AllChem.UFFOptimizeMolecule(molecule, maxIters=200)
    if suffix == ".xyz":
        Chem.MolToXYZFile(molecule, str(output_path))
    elif suffix == ".sdf":
        writer = Chem.SDWriter(str(output_path))
        try:
            writer.write(molecule)
        finally:
            writer.close()
    else:
        Chem.MolToMolFile(molecule, str(output_path))


def _rdkit_mol_from_file(path: Path) -> Chem.Mol:
    suffix = path.suffix.lower()
    if suffix == ".mol":
        molecule = Chem.MolFromMolFile(str(path), removeHs=False)
    elif suffix == ".sdf":
        supplier = Chem.SDMolSupplier(str(path), removeHs=False)
        molecule = supplier[0] if supplier and len(supplier) else None
    elif suffix == ".xyz":
        molecule = Chem.MolFromXYZFile(str(path))
    else:
        raise ValueError(f"Unsupported input extension: {suffix}")
    if molecule is None:
        raise ValueError(f"Could not read molecule file: {path}")
    return molecule


def _mol_from_smiles(smiles: str, label: str) -> Chem.Mol:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError(f"{label} is not a valid SMILES string")
    return molecule


def _num_atoms(molecule: Any) -> int | None:
    getter = getattr(molecule, "get_num_atoms", None)
    if getter is None:
        return None
    return int(getter())


def _result(
    tool: str,
    success: bool,
    output_path: Path | None,
    error: str | None,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "success": success,
        "tool": tool,
        "output_path": str(output_path) if output_path else None,
        "error": error,
        "metadata": metadata,
    }


def _finalize(result: dict[str, Any], anchor: Path | None = None) -> dict[str, Any]:
    result_path = _result_json_path(result, anchor)
    result["result_json"] = str(result_path)
    _ensure_parent(result_path)
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _result_json_path(result: dict[str, Any], anchor: Path | None) -> Path:
    output_path = result.get("output_path")
    if output_path:
        output = Path(str(output_path))
        tool = str(result.get("tool", "stk")).replace("/", "_")
        return output.with_name(f"{output.stem}_{tool}_result.json")
    if anchor is not None:
        return anchor.with_name(f"{anchor.stem}_stk_result.json")
    return Path("stk_result.json")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _format_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"
