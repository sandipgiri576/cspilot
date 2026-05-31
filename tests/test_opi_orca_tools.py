from __future__ import annotations

from pathlib import Path

import pytest

from cspilot.tools.opi_orca_tools import orca_single_point, parse_orca_result


def test_orca_single_point_writes_opi_input_when_orca_is_missing(tmp_path):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("2\nhydrogen\nH 0 0 0\nH 0 0 0.74\n", encoding="utf-8")
    workdir = tmp_path / "run"

    result = orca_single_point(
        xyz_path=xyz,
        workdir=workdir,
        method="r2scan-3c",
        basis="def2-SVP",
        charge=0,
        mult=1,
        nprocs=4,
        orca_command=str(tmp_path / "missing_orca"),
    )

    assert result["status"] in {"skipped", "failed", "ok"}
    assert (workdir / "job.inp").exists()
    input_text = (workdir / "job.inp").read_text(encoding="utf-8")
    assert "!r2scan-3c" in input_text
    assert "!def2-svp" in input_text
    assert "!sp" in input_text
    assert "nprocs 4" in input_text


def test_parse_orca_result_uses_opi_and_text_fallbacks():
    output_path = Path("opi-example/exmp045_existing_calc/RUN/job.out")
    if not output_path.exists():
        pytest.skip(f"ORCA example output fixture not found: {output_path}")

    result = parse_orca_result(output_path)

    assert result["terminated_normally"] is True
    assert result["properties"]["final_energy_hartree"] == -75.95933513032561
    assert result["properties"]["scf_converged"] is True
    assert result["properties"]["charge"] == 0
    assert result["properties"]["multiplicity"] == 1
