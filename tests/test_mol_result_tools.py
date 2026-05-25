from __future__ import annotations

import json
from types import SimpleNamespace

from cspilot.tools import mol_tools
from cspilot.tools.result_tools import find_result_json, get_property_from_result


def test_molecule_name_to_smiles_uses_pubchem(monkeypatch):
    monkeypatch.setattr(
        mol_tools.pubchempy,
        "get_compounds",
        lambda name, search_type: [SimpleNamespace(connectivity_smiles="CCO")],
    )

    result = mol_tools.molecule_name_to_smiles("ethanol")

    assert result == {
        "success": True,
        "name": "ethanol",
        "smiles": "CCO",
        "source": "PubChem",
    }


def test_smiles_to_xyz_writes_lowest_energy_conformer(tmp_path):
    xyz_path = tmp_path / "ethanol.xyz"

    result = mol_tools.smiles_to_xyz("CCO", str(xyz_path), num_confs=3)

    assert result["success"] is True
    assert result["canonical_smiles"] == "CCO"
    assert result["xyz_path"] == str(xyz_path)
    assert result["num_atoms"] == 9
    assert xyz_path.exists()


def test_result_tools_find_latest_and_extract_gibbs_alias(tmp_path):
    older = tmp_path / "result.json"
    newer = tmp_path / "workflow" / "workflow_result.json"
    newer.parent.mkdir()
    older.write_text(json.dumps({"energy": -10.0}), encoding="utf-8")
    newer.write_text(
        json.dumps({"steps": {"orca_freq": {"properties": {"gibbs_free_energy": -9.8}}}}),
        encoding="utf-8",
    )
    older.touch()
    newer.touch()

    found = find_result_json(str(tmp_path))
    extracted = get_property_from_result(str(newer), "Gibbs free energy")

    assert found["success"] is True
    assert found["path"] == str(newer)
    assert extracted["success"] is True
    assert extracted["matched_key"] == "gibbs_free_energy"
    assert extracted["value"] == -9.8
