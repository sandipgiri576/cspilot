from __future__ import annotations

from cspilot.agents.repair import repair_plan


def test_repair_missing_input_uses_existing_xyz(tmp_path):
    generated = tmp_path / "generated.xyz"
    generated.write_text("1\ncomment\nH 0 0 0\n", encoding="utf-8")
    plan = {
        "steps": [
            {
                "tool": "run_xtb_optimize",
                "args": {"input_xyz": "missing.xyz", "charge": 0, "uhf": 0},
            }
        ]
    }
    execution_result = {
        "success": False,
        "failed_step_index": 1,
        "failed_tool": "run_xtb_optimize",
        "error": "FileNotFoundError: missing.xyz does not exist",
        "steps": [],
    }

    result = repair_plan("optimize benzene", plan, execution_result, str(tmp_path))

    assert result["success"] is True
    assert result["level"] == "deterministic_file_repair"
    repaired_args = result["repaired_plan"]["steps"][0]["args"]
    assert repaired_args["input_xyz"].endswith("generated.xyz")
    assert (tmp_path / "repair_attempt_001.json").exists()


def test_repair_missing_named_molecule_inserts_xyz_generation(tmp_path):
    plan = {
        "steps": [
            {
                "tool": "run_xtb_optimize",
                "args": {"input_xyz": "benzene.xyz", "charge": 0, "uhf": 0},
            }
        ]
    }
    execution_result = {
        "success": False,
        "failed_step_index": 1,
        "failed_tool": "run_xtb_optimize",
        "error": "FileNotFoundError: benzene.xyz does not exist",
        "steps": [],
    }

    result = repair_plan("optimize benzene", plan, execution_result, str(tmp_path))

    assert result["success"] is True
    assert result["level"] == "workflow_repair"
    steps = result["repaired_plan"]["steps"]
    assert steps[0] == {
        "tool": "molecule_name_to_xyz_tool",
        "args": {"name": "benzene", "output_path": "benzene.xyz"},
    }
    assert steps[1]["tool"] == "run_xtb_optimize"
    assert steps[1]["args"]["input_xyz"] == "benzene.xyz"


def test_repair_missing_smiles_inserts_smiles_to_xyz(tmp_path):
    plan = {
        "steps": [
            {
                "tool": "run_xtb_orca_workflow",
                "args": {"input_xyz": "stk_molecule.xyz", "method": "r2scan-3c", "basis": "def2-SVP"},
            }
        ]
    }
    execution_result = {
        "success": False,
        "failed_step_index": 1,
        "failed_tool": "run_xtb_orca_workflow",
        "error": "No such file: stk_molecule.xyz",
        "steps": [],
    }

    result = repair_plan('optimize "c1ccccc1" with xTB then ORCA', plan, execution_result, str(tmp_path))

    assert result["success"] is True
    assert result["level"] == "workflow_repair"
    assert result["repaired_plan"]["steps"][0]["tool"] == "smiles_to_xyz_tool"
    assert result["repaired_plan"]["steps"][0]["args"]["output_path"] == "stk_molecule.xyz"
    assert result["repaired_plan"]["steps"][1]["args"]["input_xyz"] == "stk_molecule.xyz"
