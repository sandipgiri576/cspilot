from __future__ import annotations

from pathlib import Path

from ase import Atoms
from ase.io import read, write

from cspilot.schemas import StructureSummary


def load_structure(path: Path) -> Atoms:
    """Load an atomic structure from a file supported by ASE."""
    return read(path)


def save_structure(atoms: Atoms, path: Path) -> None:
    """Save an atomic structure using the format inferred from its path."""
    write(path, atoms)


def summarize_structure(path: Path) -> StructureSummary:
    """Return a JSON-compatible summary of an atomic structure."""
    atoms = load_structure(path)
    charge = atoms.get_initial_charges().sum()
    return StructureSummary(
        path=path,
        formula=atoms.get_chemical_formula(),
        natoms=len(atoms),
        charge=float(charge) if charge else None,
        pbc=tuple(bool(value) for value in atoms.pbc),
        cell=atoms.cell.array.tolist(),
        center_of_mass=atoms.get_center_of_mass().tolist(),
    )
