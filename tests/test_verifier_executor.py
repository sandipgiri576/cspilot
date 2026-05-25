from __future__ import annotations

import json

import pytest

from cspilot.agents.executor import execute_plan
from cspilot.agents.reporter import make_report
from cspilot.agents.verifier import verify_tool_result
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
