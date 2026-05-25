from __future__ import annotations

from typer.testing import CliRunner

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
