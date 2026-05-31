from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rdkit import Chem
from rdkit.Chem import AllChem

SUPPORTED_FUNCTIONAL_GROUPS = {
    "bromo": "BromoFactory",
    "iodo": "IodoFactory",
    "fluoro": "FluoroFactory",
    "alcohol": "AlcoholFactory",
    "aldehyde": "AldehydeFactory",
    "primary_amino": "PrimaryAminoFactory",
    "secondary_amino": "SecondaryAminoFactory",
    "carboxylic_acid": "CarboxylicAcidFactory",
    "boronic_acid": "BoronicAcidFactory",
}
SUPPORTED_CAGE_TOPOLOGIES = {
    "four_plus_six": "FourPlusSix",
}
SUPPORTED_OUTPUT_EXTENSIONS = {".mol", ".sdf", ".xyz"}


def stk_building_block_from_smiles(
    smiles: str,
    output_path: str,
    functional_groups: list[str] | None = None,
) -> dict[str, Any]:
    """Create an stk building block from SMILES and write a molecule file."""
    try:
        stk = _import_stk()
        factories = _functional_group_factories(stk, functional_groups or [])
        building_block = stk.BuildingBlock(smiles=smiles, functional_groups=factories)
        output = Path(output_path).expanduser()
        _write_stk_or_rdkit(building_block, smiles, output)
        return {
            "success": True,
            "smiles": smiles,
            "output_path": str(output),
            "num_atoms": _num_atoms(building_block),
            "functional_groups": functional_groups or [],
            "source": "stk",
        }
    except Exception as exc:
        return _failure(exc, smiles=smiles, output_path=output_path)


def stk_building_block_from_file(
    input_path: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    """Load an stk building block from a molecule file and optionally export it."""
    try:
        stk = _import_stk()
        input_file = Path(input_path).expanduser()
        building_block = stk.BuildingBlock.init_from_file(str(input_file))
        result: dict[str, Any] = {
            "success": True,
            "input_path": str(input_file),
            "num_atoms": _num_atoms(building_block),
            "source": "stk",
        }
        if output_path is not None:
            output = Path(output_path).expanduser()
            _write_stk_or_copy(building_block, input_file, output)
            result["output_path"] = str(output)
        return result
    except Exception as exc:
        return _failure(exc, input_path=input_path, output_path=output_path)


def stk_construct_linear_polymer(
    monomer_smiles: str,
    repeating_unit: str,
    num_repeating_units: int,
    output_path: str,
) -> dict[str, Any]:
    """Construct a simple linear polymer with stk when available."""
    if num_repeating_units < 1:
        return {
            "success": False,
            "monomer_smiles": monomer_smiles,
            "error": "num_repeating_units must be at least 1",
        }
    try:
        stk = _import_stk()
        building_block = stk.BuildingBlock(smiles=monomer_smiles)
        topology_graph = stk.polymer.Linear(
            building_blocks=(building_block,),
            repeating_unit=repeating_unit,
            num_repeating_units=num_repeating_units,
            orientations=(0,),
        )
        molecule = stk.ConstructedMolecule(topology_graph)
        output = Path(output_path).expanduser()
        _write_stk_molecule(molecule, output)
        return {
            "success": True,
            "monomer_smiles": monomer_smiles,
            "repeating_unit": repeating_unit,
            "num_repeating_units": num_repeating_units,
            "output_path": str(output),
            "num_atoms": _num_atoms(molecule),
            "source": "stk",
        }
    except Exception as exc:
        return _failure(
            exc,
            monomer_smiles=monomer_smiles,
            repeating_unit=repeating_unit,
            num_repeating_units=num_repeating_units,
            output_path=output_path,
        )


def stk_construct_simple_cage(
    building_block_smiles: list[str],
    topology: str,
    output_path: str,
) -> dict[str, Any]:
    """Construct a cage from a small whitelist of stk topology graphs."""
    normalized = topology.strip().lower().replace("-", "_")
    if normalized not in SUPPORTED_CAGE_TOPOLOGIES:
        return {
            "success": False,
            "topology": topology,
            "supported_topologies": sorted(SUPPORTED_CAGE_TOPOLOGIES),
            "error": "Unsupported cage topology",
        }
    try:
        stk = _import_stk()
        topology_class = getattr(stk.cage, SUPPORTED_CAGE_TOPOLOGIES[normalized])
        building_blocks = tuple(stk.BuildingBlock(smiles=smiles) for smiles in building_block_smiles)
        topology_graph = topology_class(building_blocks=building_blocks)
        molecule = stk.ConstructedMolecule(topology_graph)
        output = Path(output_path).expanduser()
        _write_stk_molecule(molecule, output)
        return {
            "success": True,
            "building_block_smiles": building_block_smiles,
            "topology": normalized,
            "output_path": str(output),
            "num_atoms": _num_atoms(molecule),
            "source": "stk",
        }
    except Exception as exc:
        return _failure(
            exc,
            building_block_smiles=building_block_smiles,
            topology=topology,
            output_path=output_path,
            supported_topologies=sorted(SUPPORTED_CAGE_TOPOLOGIES),
        )


def stk_edit_replace_smiles(
    parent_smiles: str,
    old_substructure: str,
    new_substructure: str,
    output_path: str,
) -> dict[str, Any]:
    """Replace a substructure with RDKit and export the edited molecule."""
    try:
        parent = _mol_from_smiles(parent_smiles, "parent_smiles")
        old = _mol_from_smiles(old_substructure, "old_substructure")
        new = _mol_from_smiles(new_substructure, "new_substructure")
        replacements = Chem.ReplaceSubstructs(parent, old, new, replaceAll=True)
        if not replacements:
            return {
                "success": False,
                "parent_smiles": parent_smiles,
                "old_substructure": old_substructure,
                "new_substructure": new_substructure,
                "error": "Substructure not found",
            }
        edited = replacements[0]
        Chem.SanitizeMol(edited)
        edited_smiles = Chem.MolToSmiles(edited)
        output = Path(output_path).expanduser()
        _write_rdkit_structure(edited, output)
        return {
            "success": True,
            "parent_smiles": parent_smiles,
            "old_substructure": old_substructure,
            "new_substructure": new_substructure,
            "edited_smiles": edited_smiles,
            "output_path": str(output),
            "num_atoms": int(edited.GetNumAtoms()),
            "source": "rdkit",
        }
    except Exception as exc:
        return _failure(
            exc,
            parent_smiles=parent_smiles,
            old_substructure=old_substructure,
            new_substructure=new_substructure,
            output_path=output_path,
        )


def stk_export_to_xyz(input_path: str, output_path: str) -> dict[str, Any]:
    """Export a molecule file to XYZ with stk first, then RDKit fallback."""
    input_file = Path(input_path).expanduser()
    output = Path(output_path).expanduser()
    try:
        stk = _import_stk()
        molecule = stk.BuildingBlock.init_from_file(str(input_file))
        _write_stk_molecule(molecule, output)
        return {
            "success": True,
            "input_path": str(input_file),
            "output_path": str(output),
            "num_atoms": _num_atoms(molecule),
            "source": "stk",
        }
    except Exception as stk_exc:
        try:
            molecule = _rdkit_mol_from_file(input_file)
            _write_rdkit_structure(molecule, output)
            return {
                "success": True,
                "input_path": str(input_file),
                "output_path": str(output),
                "num_atoms": int(molecule.GetNumAtoms()),
                "source": "rdkit",
                "stk_error": f"{type(stk_exc).__name__}: {stk_exc}",
            }
        except Exception as exc:
            return _failure(exc, input_path=input_path, output_path=output_path)


def _import_stk() -> Any:
    try:
        import stk
    except ImportError as exc:
        raise RuntimeError("Python package not found: stk. Install cspilot[stk].") from exc
    return stk


def _functional_group_factories(stk: Any, names: list[str]) -> tuple[Any, ...]:
    factories = []
    unsupported = [name for name in names if name not in SUPPORTED_FUNCTIONAL_GROUPS]
    if unsupported:
        supported = ", ".join(sorted(SUPPORTED_FUNCTIONAL_GROUPS))
        raise ValueError(f"Unsupported functional group(s): {unsupported}. Supported: {supported}")
    for name in names:
        factory_name = SUPPORTED_FUNCTIONAL_GROUPS[name]
        factory_class = getattr(stk, factory_name, None)
        if factory_class is None:
            raise ValueError(f"stk does not provide {factory_name} in this installation.")
        factories.append(factory_class())
    return tuple(factories)


def _write_stk_or_rdkit(molecule: Any, smiles: str, output_path: Path) -> None:
    try:
        _write_stk_molecule(molecule, output_path)
    except Exception:
        rdkit_mol = _mol_from_smiles(smiles, "smiles")
        _write_rdkit_structure(rdkit_mol, output_path)


def _write_stk_or_copy(molecule: Any, input_path: Path, output_path: Path) -> None:
    try:
        _write_stk_molecule(molecule, output_path)
    except Exception:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output_path)


def _write_stk_molecule(molecule: Any, output_path: Path) -> None:
    _validate_output_extension(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    molecule.write(str(output_path))


def _write_rdkit_structure(molecule: Chem.Mol, output_path: Path) -> None:
    _validate_output_extension(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    molecule = Chem.AddHs(Chem.Mol(molecule))
    status = AllChem.EmbedMolecule(molecule, AllChem.ETKDGv3())
    if status != 0:
        raise ValueError("RDKit could not generate 3D coordinates.")
    AllChem.UFFOptimizeMolecule(molecule)
    suffix = output_path.suffix.lower()
    if suffix == ".xyz":
        Chem.MolToXYZFile(molecule, str(output_path))
    elif suffix == ".mol":
        Chem.MolToMolFile(molecule, str(output_path))
    elif suffix == ".sdf":
        writer = Chem.SDWriter(str(output_path))
        try:
            writer.write(molecule)
        finally:
            writer.close()


def _rdkit_mol_from_file(input_path: Path) -> Chem.Mol:
    suffix = input_path.suffix.lower()
    if suffix == ".mol":
        molecule = Chem.MolFromMolFile(str(input_path), removeHs=False)
    elif suffix == ".sdf":
        supplier = Chem.SDMolSupplier(str(input_path), removeHs=False)
        molecule = next((mol for mol in supplier if mol is not None), None)
    elif suffix == ".xyz":
        molecule = Chem.MolFromXYZFile(str(input_path))
    else:
        raise ValueError(f"Unsupported input extension: {suffix}")
    if molecule is None:
        raise ValueError(f"Could not read molecule file: {input_path}")
    return molecule


def _mol_from_smiles(smiles: str, label: str) -> Chem.Mol:
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        raise ValueError(f"Invalid {label}: {smiles}")
    return molecule


def _validate_output_extension(output_path: Path) -> None:
    suffix = output_path.suffix.lower()
    if suffix not in SUPPORTED_OUTPUT_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_OUTPUT_EXTENSIONS))
        raise ValueError(f"Unsupported output extension '{suffix}'. Supported: {supported}")


def _num_atoms(molecule: Any) -> int | None:
    getter = getattr(molecule, "get_num_atoms", None)
    if getter is None:
        return None
    return int(getter())


def _failure(exc: Exception, **payload: Any) -> dict[str, Any]:
    return {
        "success": False,
        **payload,
        "error": f"{type(exc).__name__}: {exc}",
    }
