from __future__ import annotations

from pathlib import Path
from typing import Any

import pubchempy
from rdkit import Chem
from rdkit.Chem import AllChem


def molecule_name_to_smiles(name: str) -> dict[str, Any]:
    """Resolve a molecule name to a SMILES string through PubChem."""
    try:
        compounds = pubchempy.get_compounds(str(name), "name")
    except Exception as exc:
        return {
            "success": False,
            "name": name,
            "error": f"PubChem query failed: {exc}",
        }

    if not compounds or not compounds[0].connectivity_smiles:
        return {
            "success": False,
            "name": name,
            "error": "Molecule name not found in PubChem",
        }

    return {
        "success": True,
        "name": name,
        "smiles": compounds[0].connectivity_smiles,
        "source": "PubChem",
    }


def validate_smiles(smiles: str) -> dict[str, Any]:
    """Validate a SMILES string with RDKit."""
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {
            "success": False,
            "smiles": smiles,
            "valid": False,
            "error": "Invalid SMILES",
        }
    return {
        "success": True,
        "smiles": smiles,
        "valid": True,
        "canonical_smiles": Chem.MolToSmiles(molecule),
    }


def canonicalize_smiles(smiles: str) -> dict[str, Any]:
    """Convert a valid SMILES string to RDKit canonical SMILES."""
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {
            "success": False,
            "smiles": smiles,
            "error": "Invalid SMILES",
        }
    return {
        "success": True,
        "smiles": smiles,
        "canonical_smiles": Chem.MolToSmiles(molecule),
    }


def smiles_to_xyz(
    smiles: str,
    output_path: str,
    num_confs: int = 20,
    forcefield: str = "MMFF",
) -> dict[str, Any]:
    """Generate and minimize 3D conformers, then write the lowest-energy XYZ."""
    molecule = Chem.MolFromSmiles(smiles)
    if molecule is None:
        return {"success": False, "smiles": smiles, "error": "Invalid SMILES"}
    if num_confs < 1:
        return {"success": False, "smiles": smiles, "error": "num_confs must be at least 1"}

    forcefield = forcefield.upper()
    if forcefield not in {"MMFF", "UFF"}:
        return {
            "success": False,
            "smiles": smiles,
            "error": "Unsupported forcefield; expected MMFF or UFF",
        }

    canonical_smiles = Chem.MolToSmiles(molecule)
    molecule = Chem.AddHs(molecule)
    parameters = AllChem.ETKDGv3()
    parameters.randomSeed = 0xF00D
    conformer_ids = list(AllChem.EmbedMultipleConfs(molecule, numConfs=num_confs, params=parameters))
    if not conformer_ids:
        return {
            "success": False,
            "smiles": smiles,
            "canonical_smiles": canonical_smiles,
            "error": "RDKit could not generate conformers",
        }

    try:
        if forcefield == "MMFF":
            optimization_results = AllChem.MMFFOptimizeMoleculeConfs(molecule)
        else:
            optimization_results = AllChem.UFFOptimizeMoleculeConfs(molecule)
    except Exception as exc:
        return {
            "success": False,
            "smiles": smiles,
            "canonical_smiles": canonical_smiles,
            "error": f"{forcefield} optimization failed: {exc}",
        }

    if not optimization_results:
        return {
            "success": False,
            "smiles": smiles,
            "canonical_smiles": canonical_smiles,
            "error": f"{forcefield} did not produce conformer energies",
        }

    best_conf_id, _ = min(
        zip(conformer_ids, optimization_results, strict=True),
        key=lambda item: item[1][1],
    )
    xyz_path = Path(output_path).expanduser()
    xyz_path.parent.mkdir(parents=True, exist_ok=True)
    Chem.MolToXYZFile(molecule, str(xyz_path), confId=int(best_conf_id))
    return {
        "success": True,
        "smiles": smiles,
        "canonical_smiles": canonical_smiles,
        "xyz_path": str(xyz_path),
        "num_atoms": molecule.GetNumAtoms(),
        "forcefield": forcefield,
    }


def molecule_name_to_xyz(name: str, output_path: str, num_confs: int = 20) -> dict[str, Any]:
    """Resolve a name with PubChem and generate a lowest-energy XYZ structure."""
    lookup = molecule_name_to_smiles(name)
    if not lookup["success"]:
        return lookup

    result = smiles_to_xyz(
        smiles=str(lookup["smiles"]),
        output_path=output_path,
        num_confs=num_confs,
    )
    result["name"] = name
    result["source"] = "PubChem"
    return result
