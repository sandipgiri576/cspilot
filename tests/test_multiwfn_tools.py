import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from cspilot.tools import multiwfn_tools as mw
from cspilot.tools.registry import get_allowed_tools, normalize_tool_args


def test_registry_and_menu_map():
    assert "multiwfn_analysis_tool" in get_allowed_tools("chem")
    assert "multiwfn_analysis_tool" in get_allowed_tools("analysis")
    assert normalize_tool_args("multiwfn_analysis_tool", {"input_file": "water.gbw", "analysis": "mulliken"}) == {"input_path": "water.gbw", "analysis": "mulliken"}
    assert mw.MENU_MAP["mulliken"] == ("7", "5", "1", "y", "0", "0", "q")
    assert mw.MENU_MAP["hirshfeld"] == ("7", "1", "1", "y", "0", "q")


@pytest.mark.parametrize("operation", ["mulliken", "hirshfeld", "mayer"])
def test_gbw_conversion_and_parsed_outputs(tmp_path, monkeypatch, operation):
    source = tmp_path / "water.gbw"
    source.write_bytes(b"fixture")
    monkeypatch.setattr(mw.shutil, "which", lambda name: "/bin/" + name)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        root = Path(kwargs["cwd"])
        if command[0].endswith("orca_2mkl"):
            (root / "wavefunction.molden.input").write_text("fixture")
            return SimpleNamespace(returncode=0, stdout="converted", stderr="")
        assert kwargs["input"] == "\n".join(mw.MENU_MAP[operation]) + "\n"
        assert "shell" not in kwargs
        if operation == "mayer":
            (root / "bndmat.txt").write_text(" Note: diagonal\n 1 2 3\n1 1.6 .8 .8\n2 .8 .8 0.0\n3 .8 0.0 .8\n")
        else:
            (root / "wavefunction.chg").write_text("O 0 0 0 -0.8\nH 0 1 0 0.4\nH 0 -1 0 0.4\n")
        return SimpleNamespace(returncode=0, stdout="Version 3.8\nNet charge: 0.0\nTotal atoms: 3", stderr="")

    monkeypatch.setattr(mw.subprocess, "run", run)
    result = mw.analyze_wavefunction(source, tmp_path, operation)
    assert result["success"], result
    assert source.read_bytes() == b"fixture"
    assert len(calls) == 2
    assert Path(result["files"]["menu"]).exists()
    assert (Path(result["workdir"]) / "result.json").exists()
    if operation != "mayer":
        assert result["total_charge"] == pytest.approx(0)
    else:
        assert result["bond_order_matrix"][0][1] == .8


@pytest.mark.parametrize("failure", ["timeout", "exit", "missing", "version", "charge"])
def test_failure_never_becomes_a_scientific_success(tmp_path, monkeypatch, failure):
    source = tmp_path / "water.fch"
    source.write_text("fixture")
    monkeypatch.setattr(mw.shutil, "which", lambda name: "/bin/" + name)

    def run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 1)
        root = Path(kwargs["cwd"])
        if failure != "missing":
            charge = -1 if failure == "charge" else -.8
            (root / "wavefunction.chg").write_text(f"O 0 0 0 {charge}\nH 0 1 0 0.4\nH 0 -1 0 0.4\n")
        return SimpleNamespace(returncode=1 if failure == "exit" else 0,
            stdout=f"Version {'4.0' if failure == 'version' else '3.8'}\nNet charge: 0.0\nTotal atoms: 3", stderr="")

    monkeypatch.setattr(mw.subprocess, "run", run)
    result = mw.analyze_wavefunction(source, tmp_path)
    assert result["success"] is False
    assert result["error"]
    assert "atomic_charges" not in result


def test_unsupported_commands_rejected_before_subprocess(tmp_path, monkeypatch):
    monkeypatch.setattr(mw.subprocess, "run", lambda *a, **kw: pytest.fail("must not execute"))
    assert not mw.analyze_wavefunction("water.gbw", tmp_path, "7\n1\n")['success']
