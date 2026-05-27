from __future__ import annotations

from typer.testing import CliRunner

from cspilot.agents.openai_agent import _profile_tools
from cspilot.cli import app


def test_agent_command_reports_missing_agapi_configuration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGAPI_API_KEY", raising=False)
    monkeypatch.delenv("AGAPI_BASE_URL", raising=False)
    monkeypatch.delenv("cspilot_MODEL", raising=False)

    result = CliRunner().invoke(
        app,
        ["agent", "inspect input.xyz", "--workdir", str(tmp_path / "agent_run")],
    )

    assert result.exit_code == 1
    assert "Missing required environment variable: cspilot_MODEL" in result.output


def test_chem_agent_exposes_frequency_and_result_query_tool_names():
    names = [tool.name for tool in _profile_tools("chem")]

    assert "run_xtb_orca_frequency_workflow" in names
    assert "find_result_json" in names
    assert "get_property_from_result" in names
