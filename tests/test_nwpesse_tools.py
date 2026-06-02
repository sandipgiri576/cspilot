from __future__ import annotations

from pathlib import Path

from cspilot.tools.nwpesse_tools import (
    find_lowest_energy_geometry,
    generate_box_config,
    parse_cluster_formula,
    write_fragment_xyz,
    write_mol_cluster,
    write_nwpesse_input,
)
from cspilot.workflows import nwpesse_workflows


def test_parse_grouped_cluster_formula():
    result = parse_cluster_formula("(h2o)4Mg")

    assert result["success"] is True
    assert result["fragments"] == [
        {"name": "h2o", "count": 4, "label": "h2o"},
        {"name": "mg", "count": 1, "label": "Mg"},
    ]


def test_parse_colon_cluster_formula():
    result = parse_cluster_formula("h2o:4,mg:1")

    assert result["success"] is True
    assert result["fragments"] == [
        {"name": "h2o", "count": 4, "label": "h2o"},
        {"name": "mg", "count": 1, "label": "mg"},
    ]


def test_write_single_atom_mg_xyz(tmp_path):
    output = tmp_path / "mg.xyz"

    result = write_fragment_xyz("Mg", str(output))

    assert result["success"] is True
    assert output.read_text(encoding="utf-8").splitlines() == [
        "1",
        "Mg",
        "Mg 0.000000 0.000000 0.000000",
    ]


def test_write_mol_cluster(tmp_path):
    result = write_mol_cluster(
        [{"name": "h2o", "count": 4}, {"name": "mg", "count": 1}],
        str(tmp_path),
    )

    assert result["success"] is True
    assert Path(result["cluster_file"]).read_text(encoding="utf-8") == "2\nh2o.xyz 4\nmg.xyz 1\n"


def test_write_nwpesse_input(tmp_path):
    result = write_nwpesse_input(
        result_name="nwpesse_result",
        cluster_file=str(tmp_path / "mol.cluster"),
        max_calculations=10,
        box_blocks=["inbox 0. 0. 0. 3. 3. 3.", "inbox 0. 0. 0. 3. 3. 3."],
        optimizer="xtb_gxtb",
        workdir=str(tmp_path),
    )

    text = Path(result["input_file"]).read_text(encoding="utf-8")
    assert result["success"] is True
    assert text.startswith("nwpesse_result\nmol.cluster\n10\n>>>>\n")
    assert "xtb $xxx$.xyz --gxtb --opt" in text


def test_find_lowest_energy_geometry_from_nwpesse_lm_folder(tmp_path):
    lm_dir = tmp_path / "nwpesse_result-LM"
    lm_dir.mkdir()
    (lm_dir / "1.xyz").write_text("1\nEnergy =   -505.100 au\nH 0 0 0\n", encoding="utf-8")
    (lm_dir / "2.xyz").write_text(
        "1\nEnergy =   -505.86549251 au\nH 0 0 0\n",
        encoding="utf-8",
    )
    (lm_dir / "3.xyz").write_text("1\nEnergy =   -504.900 au\nH 0 0 0\n", encoding="utf-8")

    result = find_lowest_energy_geometry(str(tmp_path), result_name="nwpesse_result")

    assert result["success"] is True
    assert result["lowest_energy"] == -505.86549251
    assert result["energy_unit"] == "au"
    assert result["lowest_geometry"].endswith("2.xyz")
    assert result["candidate_count"] == 3
    assert Path(result["lowest_geometry_copy"]).exists()
    assert [candidate["energy"] for candidate in result["all_candidates"]] == [
        -505.86549251,
        -505.1,
        -504.9,
    ]


def test_generate_box_config_per_unique_fragment_type():
    water = parse_cluster_formula("(h2o)4")["fragments"]
    water_mg = parse_cluster_formula("(h2o)4Mg")["fragments"]

    water_boxes = generate_box_config(water, box_size=3.0)
    water_mg_boxes = generate_box_config(water_mg, box_size=3.0)

    assert water_boxes["box_lines"] == ["inbox 0. 0. 0. 3.0 3.0 3.0"]
    assert water_mg_boxes["box_lines"] == [
        "inbox 0. 0. 0. 3.0 3.0 3.0",
        "inbox 0. 0. 0. 3.0 3.0 3.0",
    ]


def test_generate_box_config_single_mode():
    fragments = parse_cluster_formula("(h2o)4Mg")["fragments"]

    result = generate_box_config(fragments, box_size=5.0, box_mode="single")

    assert result["box_lines"] == ["inbox 0. 0. 0. 5.0 5.0 5.0"]
    assert result["box_count"] == 1


def test_find_lowest_energy_geometry_supports_energy_line_variants(tmp_path):
    variants = [
        ("1.xyz", "Energy =   -5.0 au"),
        ("2.xyz", "Energy = -6.0"),
        ("3.xyz", "-7.0"),
        ("4.xyz", "E = -8.0 au"),
        ("5.xyz", "energy -9.0"),
    ]
    for filename, line2 in variants:
        (tmp_path / filename).write_text(f"1\n{line2}\nH 0 0 0\n", encoding="utf-8")

    result = find_lowest_energy_geometry(str(tmp_path))

    assert result["success"] is True
    assert result["lowest_energy"] == -9.0
    assert result["lowest_geometry"].endswith("5.xyz")
    assert result["candidate_count"] == 5


def test_nwpesse_workflow_can_be_mocked(tmp_path, monkeypatch):
    def fake_run_nwpesse(input_file: str, workdir: str, timeout: int = 86400):
        root = Path(workdir)
        (root / "nwpesse_result-LM").mkdir()
        (root / "nwpesse_result-LM" / "0.xyz").write_text(
            "1\nEnergy = -1.25 au\nMg 0 0 0\n",
            encoding="utf-8",
        )
        return {
            "success": True,
            "tool": "run_nwpesse",
            "returncode": 0,
            "stdout_file": str(root / "nwpesse.stdout"),
            "stderr_file": str(root / "nwpesse.stderr"),
            "workdir": str(root),
            "error": None,
        }

    monkeypatch.setattr(nwpesse_workflows, "run_nwpesse", fake_run_nwpesse)

    result = nwpesse_workflows.nwpesse_global_minimum_search(
        formula="(h2o)4Mg",
        fragments=None,
        workdir=str(tmp_path),
    )

    assert result["success"] is True
    assert result["lowest_energy"] == -1.25
    assert result["lowest_geometry_copy"] == str(tmp_path / "lowest_energy.xyz")
    assert result["box_config"]["box_count"] == 2
    assert (tmp_path / "workflow_result.json").exists()
