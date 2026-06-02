from __future__ import annotations

import json

import pytest

from cspilot.agents.executor import execute_plan
from cspilot.agents.reporter import generate_report, make_report
from cspilot.agents.verifier import verify_execution, verify_tool_result
from cspilot.tools.registry import call_tool, get_allowed_tools


def test_verify_tool_result_rejects_missing_file_and_non_numeric_energy(tmp_path):
    result = {
        "success": True,
        "properties": {"final_energy_hartree": "missing"},
        "outputs": {"optimized_xyz": str(tmp_path / "absent.xyz")},
    }

    verification = verify_tool_result(result, str(tmp_path))

    assert verification["verified"] is False
    assert any("not numeric" in issue for issue in verification["issues"])
    assert any("optimized XYZ" in issue for issue in verification["issues"])


def test_make_report_reports_only_returned_values_and_verification(tmp_path):
    generated = tmp_path / "job.out"
    generated.write_text("completed", encoding="utf-8")
    report = make_report(
        "calculate energy",
        [
            {
                "tool_name": "run_orca_single_point",
                "status": "ok",
                "workdir": str(tmp_path),
                "properties": {"final_energy_hartree": -75.2},
                "files": {"output": str(generated)},
            }
        ],
        {"verified": True, "issues": [], "workdir": str(tmp_path)},
    )

    assert "final_energy_hartree: -75.2" in report
    assert f"Workdir: {tmp_path}" in report
    assert str(generated) in report
    assert "Verification: passed." in report
    assert "gibbs" not in report.lower()


def test_registry_rejects_unknown_tool(tmp_path):
    assert "inspect_structure" in get_allowed_tools()
    with pytest.raises(ValueError, match="Unknown or disallowed tool"):
        call_tool("run_shell", {"command": "echo no"}, str(tmp_path))


def test_execute_plan_saves_allowlisted_step_results(tmp_path):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("1\nhydrogen\nH 0 0 0\n", encoding="utf-8")
    plan = {"steps": [{"tool": "inspect_structure", "args": {"xyz_path": str(xyz)}}]}

    result = execute_plan(plan, str(tmp_path / "execute"))

    assert result["success"] is True
    assert (tmp_path / "execute" / "plan.json").exists()
    assert (tmp_path / "execute" / "step_001_result.json").exists()
    execution_file = tmp_path / "execute" / "execution_result.json"
    assert execution_file.exists()
    saved = json.loads(execution_file.read_text(encoding="utf-8"))
    assert saved["steps"][0]["structure"]["natoms"] == 1


def test_verify_nwpesse_success_does_not_require_thermochemistry(tmp_path):
    geometry = tmp_path / "lowest_energy.xyz"
    geometry.write_text("1\nEnergy = -505.86549251 au\nMg 0 0 0\n", encoding="utf-8")
    result = {
        "workflow": "nwpesse_global_minimum_search",
        "success": True,
        "lowest_energy": -505.86549251,
        "energy_unit": "au",
        "lowest_geometry_copy": str(geometry),
        "candidate_count": 10,
    }

    verification = verify_tool_result(result, str(tmp_path))

    assert verification["verified"] is True
    assert not any("energy_unit" in issue for issue in verification["issues"])
    assert not any("Gibbs" in issue or "gibbs" in issue for issue in verification["issues"])


def test_verify_nwpesse_nested_execution_result(tmp_path):
    geometry = tmp_path / "lowest_energy.xyz"
    geometry.write_text("1\nEnergy = -505.86549251 au\nMg 0 0 0\n", encoding="utf-8")
    execution_result = {
        "results": [
            {
                "workflow": "nwpesse_global_minimum_search",
                "success": True,
                "lowest_energy": -505.86549251,
                "energy_unit": "au",
                "lowest_geometry_copy": str(geometry),
                "candidate_count": 3,
            }
        ]
    }

    verification = verify_execution(execution_result, str(tmp_path))

    assert verification["verified"] is True


def test_verify_nwpesse_rejects_non_numeric_lowest_energy(tmp_path):
    geometry = tmp_path / "lowest_energy.xyz"
    geometry.write_text("1\nEnergy = -505.86549251 au\nMg 0 0 0\n", encoding="utf-8")
    result = {
        "workflow": "nwpesse_global_minimum_search",
        "success": True,
        "lowest_energy": "not-a-number",
        "energy_unit": "au",
        "lowest_geometry_copy": str(geometry),
        "candidate_count": 10,
    }

    verification = verify_tool_result(result, str(tmp_path))

    assert verification["verified"] is False
    assert any("lowest_energy" in issue and "not numeric" in issue for issue in verification["issues"])


def test_generate_report_for_nwpesse_omits_irrelevant_thermochemistry(tmp_path):
    geometry = tmp_path / "lowest_energy.xyz"
    geometry.write_text("1\nEnergy = -505.86549251 au\nMg 0 0 0\n", encoding="utf-8")
    execution_result = {
        "success": True,
        "workdir": str(tmp_path),
        "steps": [
            {
                "tool_name": "nwpesse_global_minimum_search_tool",
                "workflow": "nwpesse_global_minimum_search",
                "success": True,
                "fragments": [{"name": "h2o", "count": 4}, {"name": "mg", "count": 1}],
                "max_calculations": 10,
                "box_mode": "per_fragment_type",
                "box_size": 3.0,
                "candidate_count": 10,
                "lowest_energy": -505.86549251,
                "energy_unit": "au",
                "lowest_geometry_copy": str(geometry),
            }
        ],
    }

    report = generate_report(
        "Find the global minimum for (H2O)4Mg",
        {"steps": [{"tool": "nwpesse_global_minimum_search_tool", "args": {}}]},
        execution_result,
        {"verified": True, "issues": []},
    )

    assert "NWPESSe global-minimum search" in report
    assert "lowest_energy: -505.86549251 au" in report
    assert str(geometry) in report
    assert "Gibbs free energy" not in report
    assert "HOMO-LUMO" not in report
