"""Deterministic stoichiometry and comparison; no model-generated arithmetic."""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Iterator
from numbers import Real
from pathlib import Path
from typing import Any

from ase.io import read
from rdkit import Chem

# CODATA Hartree energy * Avogadro constant / 1000 (kJ mol^-1).
HARTREE_TO_KJ_MOL = 2625.4996394799


def molecule_composition(smiles: str, charge: int, mult: int) -> Counter:
    """Return an explicit-hydrogen elemental composition for a molecular state."""

    mol = Chem.MolFromSmiles(smiles)
    if mol is None or Chem.GetFormalCharge(mol) != charge:
        raise ValueError("Invalid SMILES or molecular charge mismatch")
    mol = Chem.AddHs(mol)
    electrons = sum(a.GetAtomicNum() for a in mol.GetAtoms()) - charge
    if (electrons - (mult - 1)) % 2 or mult - 1 > electrons:
        raise ValueError("Multiplicity is incompatible with electron count")
    counts = Counter(a.GetSymbol() for a in mol.GetAtoms())
    if counts == Counter(O=2) and charge == 0 and mult != 3:
        raise ValueError("Ground-state O2 requires triplet multiplicity (3)")
    return counts


def validate_species(plan: dict[str, Any]) -> None:
    """Validate molecular identity, spin parity, and reaction balance."""
    if plan["kind"] == "conformers":
        inputs = [task.get("input_xyz") for task in plan["subtasks"]]
        if not all(inputs) or len({str(Path(p).resolve()) for p in inputs}) != len(inputs):
            raise ValueError("Conformer comparison requires distinct supplied XYZ paths")
    balance: Counter = Counter()
    charge_balance = 0.0
    for task in plan["subtasks"]:
        if task.get("input_xyz") and not Path(task["input_xyz"]).is_file():
            raise ValueError(f"Missing supplied geometry: {task['input_xyz']}")
        if not task.get("smiles"):
            continue
        counts = molecule_composition(task["smiles"], task["charge"], task["mult"])
        if plan["kind"] == "reaction":
            factor = task["coefficient"] * (1 if task["role"] == "product" else -1)
            for atom, count in counts.items():
                balance[atom] += factor * count
            charge_balance += factor * task["charge"]
    if plan["kind"] == "reaction" and (
        any(abs(v) > 1e-8 for v in balance.values()) or abs(charge_balance) > 1e-8
    ):
        raise ValueError("Reaction is not balanced in atoms and charge")


def _records(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("task") in {"sp", "opt", "freq", "opt_freq"} and "parameters" in value:
            yield value
        for child in value.values():
            yield from _records(child)
    elif isinstance(value, list):
        for child in value:
            yield from _records(child)


def aggregate_results(plan: dict[str, Any], summaries: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate verified independent-agent results without model arithmetic."""
    result: dict[str, Any] = {
        "success": False,
        "tool": "aggregate_subtasks",
        "error": None,
        "metadata": {"kind": plan["kind"]},
        "species_results": [],
    }
    try:
        validate_species(plan)
        expected = [s["id"] for s in plan["subtasks"]]
        if [s["id"] for s in summaries] != expected:
            raise ValueError("Missing, duplicate or out-of-order subtask summaries")
        if any(s.get("verified") is not True for s in summaries):
            raise ValueError("All child agents must verify before aggregation")
        if plan["kind"] == "collection":
            result["species_results"] = [
                {"id": s["id"], "summary_file": s["summary_file"], "results": s["results"]}
                for s in summaries
            ]
        else:
            key = plan["property"]
            thermal = key != "final_energy_hartree"
            values = []
            for task, summary in zip(plan["subtasks"], summaries, strict=True):
                records = list(_records(summary["execution_result"]))
                if not records:
                    raise ValueError(f"{task['id']}: no ORCA record")
                record = records[-1]
                props = record.get("result", {}).get("properties", {})
                settings = record["parameters"]
                value = props.get(key)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, Real)
                    or not math.isfinite(value)
                ):
                    raise ValueError(f"{task['id']}: missing finite {key}")
                if props.get("energy_unit") != "Eh" or record.get("status") != "ok":
                    raise ValueError("Require successful ORCA values in Eh")
                basis = (
                    "method-defined"
                    if plan["method"].lower() in {"r2scan-3c", "b97-3c", "pbeh-3c", "hf-3c"}
                    else plan["basis"]
                )
                if (
                    str(settings.get("method", "")).lower() != plan["method"].lower()
                    or str(settings.get("basis", "")).lower() != basis.lower()
                    or settings.get("charge") != task["charge"]
                    or settings.get("mult") != task["mult"]
                ):
                    raise ValueError(
                        f"{task['id']}: calculation settings differ from specification"
                    )
                if thermal and (
                    record.get("task") != "opt_freq"
                    or not props.get("geometry_optimization_converged")
                    or not props.get("frequencies")
                    or props.get("imaginary_frequency_count") != 0
                    or props.get("temperature_kelvin") != plan["temperature_kelvin"]
                    or props.get("pressure_atm") != plan["pressure_atm"]
                ):
                    raise ValueError(
                        f"{task['id']}: unverified optimization/frequencies or incompatible conditions"
                    )
                geometry = record.get("files", {}).get("optimized_xyz") or record.get("input_xyz")
                actual = Counter(read(geometry).get_chemical_symbols())
                if actual != molecule_composition(task["smiles"], task["charge"], task["mult"]):
                    raise ValueError(f"{task['id']}: calculated geometry has wrong composition")
                output = record.get("files", {}).get("output")
                if not output or not Path(output).is_file():
                    raise ValueError("Missing ORCA output provenance")
                result["species_results"].append(
                    {
                        "id": task["id"],
                        "role": task["role"],
                        "coefficient": task["coefficient"],
                        "property": key,
                        "value": value,
                        "unit": "Eh",
                        "source_file": output,
                        "charge": task["charge"],
                        "mult": task["mult"],
                    }
                )
                values.append(value)
            if plan["kind"] == "reaction":
                delta = math.fsum(
                    value * task["coefficient"] * (1 if task["role"] == "product" else -1)
                    for task, value in zip(plan["subtasks"], values, strict=True)
                )
                if not math.isfinite(delta * HARTREE_TO_KJ_MOL):
                    raise ValueError("Non-finite reaction sum")
                result.update(
                    reaction_property=key,
                    reaction_energy_hartree=delta,
                    reaction_energy_kj_mol=delta * HARTREE_TO_KJ_MOL,
                )
            else:
                minimum = min(values)
                relative = {
                    task["id"]: (v - minimum) * HARTREE_TO_KJ_MOL
                    for task, v in zip(plan["subtasks"], values, strict=True)
                }
                if not all(math.isfinite(v) for v in relative.values()):
                    raise ValueError("Non-finite relative energy")
                result["relative_energies_kj_mol"] = relative
            result["metadata"].update(
                method=plan["method"],
                phase=plan["phase"],
                temperature_kelvin=plan["temperature_kelvin"],
                pressure_atm=plan["pressure_atm"],
            )
        result["success"] = True
    except (ValueError, KeyError, TypeError, OSError, IndexError, OverflowError) as exc:
        result["error"] = str(exc)
    return result
