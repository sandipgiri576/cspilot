from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from cspilot.cli import app


def test_xtb_orca_sp_workflow_writes_result_when_xtb_is_missing(tmp_path, monkeypatch):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("2\nhydrogen\nH 0 0 0\nH 0 0 0.74\n", encoding="utf-8")
    (tmp_path / ".env.cspilot").write_text(
        "\n".join(
            [
                "XTB_COMMAND=missing-xtb",
                "ORCA_COMMAND=missing-orca",
                "CSPILOT_RUNS_DIR=runs",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "xtb-orca-sp",
            str(xyz),
            "--charge",
            "0",
            "--mult",
            "1",
            "--method",
            "r2scan-3c",
            "--basis",
            "def2-SVP",
        ],
    )

    assert result.exit_code == 0
    result_file = next(Path("runs").glob("*/workflow_result.json"))
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["workflow"] == "xtb-orca-sp"
    assert payload["status"] == "skipped"
    assert payload["failed_step"] == "xtb_opt"


def test_mace_orca_workflow_writes_result_without_mace_install(tmp_path, monkeypatch):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("1\nhydrogen\nH 0 0 0\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "mace-orca",
            str(xyz),
            "--charge",
            "0",
            "--mult",
            "1",
        ],
    )

    assert result.exit_code == 0
    result_file = next(Path("runs").glob("*/workflow_result.json"))
    payload = json.loads(result_file.read_text(encoding="utf-8"))
    assert payload["workflow"] == "mace-orca"
    assert payload["status"] == "skipped"
    assert payload["failed_step"] == "mace_opt"
