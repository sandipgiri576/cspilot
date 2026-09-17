from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cspilot.agents import planner
from cspilot.agents.reporter import terminal_report
from cspilot.agents.router import route_request
from cspilot.agents.verifier import verify_execution, verify_request_completion, verify_tool_result
from cspilot.cli import app
from cspilot.config import Settings
from cspilot.tools.opi_orca_tools import orca_frequency, parse_orca_result
from cspilot.tools.registry import get_allowed_tools
from cspilot.workflows.xtb_to_orca_freq import run_xtb_to_orca_freq


@pytest.mark.parametrize("prompt,profile", [
    ("what is the SMILES string of caffine?", "chem"),
    ("what is the gibbs free enegy of benzene at orca with r2scan-3c", "thermo"),
    ("Optimize geometry and compute thermochemistry like Gibbs free energy, enthalpy, etc.", "thermo"),
    ("extract Gibbs free energy from previous result.json", "analysis"),
])
def test_request_routes(prompt, profile):
    assert route_request(prompt)["specialist"] == profile
    tools = get_allowed_tools(profile)
    if profile == "thermo":
        assert "run_xtb_orca_frequency_workflow" in tools
        assert "molecule_name_to_xyz_tool" in tools
        assert "run_orca_single_point" not in tools


def test_smiles_lookup_does_not_require_geometry(tmp_path):
    result = {"tool_name": "molecule_name_to_smiles_tool", "success": True,
              "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"}
    verification = verify_execution({"success": True, "steps": [result]}, str(tmp_path))
    assert verification["verified"]
    assert verify_request_completion("SMILES of caffeine", result) == []


def test_geometry_alone_cannot_complete_thermochemistry():
    issues = verify_request_completion("compute thermochemistry", {"success": True, "xyz_path": "a.xyz"})
    assert any("gibbs_free_energy" in issue for issue in issues)
    assert any("enthalpy" in issue for issue in issues)


def test_plain_clarification_is_blocked_not_finished():
    decision = planner.AgentDecision.model_validate({
        "summary": "Please specify the molecule or XYZ file.",
    })
    assert decision.action == "blocked"


def test_report_method_comes_from_calculation_parameters():
    execution = {"steps": [{
        "parameters": {"method": "r2scan-3c", "basis": "method-defined"},
        "result": {"properties": {"gibbs_free_energy": -232.1,
                                  "energies": {"method": "SCF"}}},
    }]}
    report = terminal_report(execution, {"verified": True})
    assert "Method: r2scan-3c" in report
    assert "Method: SCF" not in report


def test_native_selection_does_not_execute_the_tool(monkeypatch, tmp_path):
    async def run(agent, prompt, **kwargs):
        names = {tool.name for tool in agent.tools}
        assert "finish" not in names
        assert "blocked" in names
        tool = next(tool for tool in agent.tools if tool.name == "molecule_name_to_xyz_tool")
        value = await tool.on_invoke_tool(
            SimpleNamespace(tool_name=tool.name),
            json.dumps({"name": "benzene", "output_path": str(tmp_path / "benzene.xyz")}),
        )
        assert not (tmp_path / "benzene.xyz").exists()
        return SimpleNamespace(final_output=value)

    monkeypatch.setattr(planner, "create_llm_model", lambda **kwargs: "mock")
    monkeypatch.setattr(planner.Runner, "run", run)
    decision = asyncio.run(planner.decide_next_action("calculate benzene Gibbs", []))
    assert decision["tool"] == "molecule_name_to_xyz_tool"
    assert decision["args"]["name"] == "benzene"


def test_orca_opt_freq_uses_composite_basis(tmp_path):
    xyz = tmp_path / "water.xyz"
    xyz.write_text("3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n")
    result = orca_frequency(xyz, tmp_path / "orca", "r2scan-3c", "def2-SVP",
                            optimize=True, orca_command=str(tmp_path / "missing"))
    text = Path(result["files"]["input"]).read_text().lower()
    assert "!opt" in text and "!freq" in text
    assert "r2scan-3c" in text and "def2-svp" not in text
    assert result["task"] == "opt_freq"
    assert result["parameters"]["basis"] == "method-defined"


def test_frequency_workflow_requests_orca_optimization(monkeypatch, tmp_path):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("1\nHe\nHe 0 0 0\n")
    called = {}

    def xtb(input_file, run_dir, settings, charge, uhf):
        output = run_dir / "xtbopt.xyz"
        output.write_text(xyz.read_text())
        return True, "ok", None, {"optimized_xyz": str(output)}

    def frequency(input_xyz, workdir, method, basis, **kwargs):
        called.update(kwargs)
        assert Path(input_xyz).name == "xtbopt.xyz"
        return {"status": "ok", "result": {"properties": {"final_energy_hartree": -2.0}}}

    monkeypatch.setattr("cspilot.workflows.xtb_to_orca_freq.optimize_with_xtb", xtb)
    monkeypatch.setattr("cspilot.workflows.xtb_to_orca_freq.orca_frequency", frequency)
    result = run_xtb_to_orca_freq(xyz, settings=Settings(runs_dir=tmp_path / "runs"))
    assert called["optimize"] is True
    assert result["status"] == "ok"


def test_thermochemistry_parser_and_verifier(monkeypatch, tmp_path):
    output = tmp_path / "job.out"
    output.write_text(
        "THE OPTIMIZATION HAS CONVERGED\n"
        "FINAL SINGLE POINT ENERGY -232.1\n"
        "Temperature ... 298.15 K\nPressure ... 1.00 atm\n"
        "0: 0.00 cm**-1\n6: 400.00 cm**-1\n"
        "Zero point energy ... 0.1 Eh\n"
        "Total Enthalpy ... -232.0 Eh\nFinal Gibbs free energy ... -232.05 Eh\n"
        "ORCA TERMINATED NORMALLY\n"
    )
    monkeypatch.setattr("cspilot.tools.opi_orca_tools.opi_available", lambda: False)
    parsed = parse_orca_result(output)
    assert parsed["properties"]["enthalpy"] == -232.0
    assert parsed["properties"]["energy_unit"] == "Eh"
    assert parsed["properties"]["temperature_kelvin"] == 298.15
    result = {"task": "opt_freq", "status": "ok", "files": {"output": str(output)}, "result": parsed}
    assert verify_tool_result(result, str(tmp_path))["verified"]
    parsed["properties"]["imaginary_frequency_count"] = 1
    assert not verify_tool_result(result, str(tmp_path))["verified"]


def test_bare_prompt_uses_agent_and_shows_only_relevant_results(monkeypatch, tmp_path):
    async def decide(request, observations, **kwargs):
        return {"action": "finish"} if observations else {
            "action": "tool", "tool": "molecule_name_to_smiles_tool", "args": {"name": "caffeine"}}

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    monkeypatch.setattr("cspilot.graph.call_tool", lambda *args: {
        "tool_name": "molecule_name_to_smiles_tool", "success": True,
        "name": "caffeine", "smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C", "source": "PubChem",
    })
    result = CliRunner().invoke(app, [
        "what is the SMILES string of caffine?", "--workdir", str(tmp_path), "--no-pretty",
    ])
    assert result.exit_code == 0, result.output
    assert "SMILES: CN1" in result.output
    assert "Verification: passed" in result.output
    assert "Gibbs" not in result.output
