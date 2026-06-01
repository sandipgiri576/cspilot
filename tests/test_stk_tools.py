from __future__ import annotations

from cspilot.config import Settings
from cspilot.tools.stk_tools import (
    stk_build_from_smiles,
    stk_construct_cage_from_smiles,
    stk_export_to_xyz,
)
from cspilot.workflows import stk_workflows


def test_stk_build_benzene_from_smiles(tmp_path):
    output = tmp_path / "benzene.mol"

    result = stk_build_from_smiles("C1=CC=CC=C1", str(output))

    assert result["success"] is True
    assert result["tool"] == "stk_build_from_smiles"
    assert output.exists()
    assert (tmp_path / "benzene_stk_build_from_smiles_result.json").exists()


def test_stk_export_to_xyz_creates_file(tmp_path):
    mol_path = tmp_path / "benzene.mol"
    xyz_path = tmp_path / "benzene.xyz"
    build_result = stk_build_from_smiles("C1=CC=CC=C1", str(mol_path))
    assert build_result["success"] is True

    result = stk_export_to_xyz(str(mol_path), str(xyz_path))

    assert result["success"] is True
    assert xyz_path.exists()
    assert xyz_path.read_text(encoding="utf-8").splitlines()[0].strip().isdigit()


def test_stk_smiles_to_xtb_opt_can_be_mocked(tmp_path, monkeypatch):
    def fake_optimize(input_file, run_dir, settings, charge, uhf):
        optimized = run_dir / "xtbopt.xyz"
        optimized.write_text(input_file.read_text(encoding="utf-8"), encoding="utf-8")
        return True, "mock xTB optimization completed", None, {"optimized_xyz": str(optimized)}

    monkeypatch.setattr(stk_workflows, "optimize_with_xtb", fake_optimize)
    monkeypatch.setattr(stk_workflows, "load_settings", lambda: Settings())

    result = stk_workflows.stk_smiles_to_xtb_opt("C1=CC=CC=C1", tmp_path, charge=0, uhf=0)

    assert result["success"] is True
    assert (tmp_path / "workflow_result.json").exists()
    assert result["steps"]["xtb_opt"]["status"] == "ok"


def test_unsupported_cage_topology_returns_failure(tmp_path):
    result = stk_construct_cage_from_smiles(["NCCN"], "four_plus_six", str(tmp_path / "cage.mol"))

    assert result["success"] is False
    assert result["error"]
    assert result["metadata"]["supported_topologies"] == []
