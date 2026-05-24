from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cspilot.cli import app


def test_inspect_creates_result_json(tmp_path, monkeypatch):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("2\nwater fragment\nH 0 0 0\nH 0 0 1\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["inspect", str(xyz)])

    assert result.exit_code == 0
    result_files = list(Path("runs").glob("*/result.json"))
    assert len(result_files) == 1
    payload = json.loads(result_files[0].read_text(encoding="utf-8"))
    assert payload["command"] == "inspect"
    assert payload["status"] == "ok"
    assert payload["structure"]["natoms"] == 2


def test_xtb_missing_executable_still_writes_result_json(tmp_path, monkeypatch):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("1\nhydrogen\nH 0 0 0\n", encoding="utf-8")
    (tmp_path / ".env.cspilot").write_text("XTB_COMMAND=not-a-real-xtb\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(app, ["xtb-opt", str(xyz), "--charge", "0", "--uhf", "0"])

    assert result.exit_code == 0
    result_file = next(Path("runs").glob("*/result.json"))
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["command"] == "xtb-opt"
    assert payload["status"] == "skipped"
