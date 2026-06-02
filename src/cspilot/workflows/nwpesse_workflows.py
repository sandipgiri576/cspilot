from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from cspilot.tools.nwpesse_tools import (
    find_lowest_energy_geometry,
    generate_box_config,
    parse_cluster_formula,
    run_nwpesse,
    write_fragment_xyz,
    write_mol_cluster,
    write_nwpesse_input,
)


def nwpesse_global_minimum_search(
    formula: str | None,
    fragments: list[dict] | None,
    workdir: str,
    result_name: str = "nwpesse_result",
    max_calculations: int = 10,
    box_size: float = 3.0,
    box_mode: str = "per_fragment_type",
    box_blocks: list[str] | None = None,
    custom_boxes: list[dict] | None = None,
    optimizer: str = "xtb_gxtb",
    fragment_dir: str | None = None,
    timeout: int = 86400,
) -> dict[str, Any]:
    """Prepare and run an NWPESSe global-minimum search."""
    root = Path(workdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    result_path = root / "workflow_result.json"
    steps: dict[str, Any] = {}
    try:
        steps["formula"] = formula
        fragment_specs = _resolve_fragment_specs(formula, fragments)
        steps["fragments"] = fragment_specs
        prepared = _prepare_fragment_files(fragment_specs, root, fragment_dir)
        steps["prepare_fragments"] = prepared
        if not prepared["success"]:
            return _finalize(root, result_path, False, steps, prepared["error"])

        cluster = write_mol_cluster(prepared["fragments"], str(root))
        steps["write_mol_cluster"] = cluster
        if not cluster["success"]:
            return _finalize(root, result_path, False, steps, cluster["error"])

        box_config = generate_box_config(
            prepared["fragments"],
            box_size=box_size,
            box_mode=box_mode,
            custom_boxes=custom_boxes,
        )
        if box_blocks is not None:
            box_config = {
                "success": True,
                "tool": "generate_box_config",
                "box_mode": "custom_legacy",
                "box_size": box_size,
                "box_lines": box_blocks,
                "box_count": len(box_blocks),
                "error": None,
            }
        steps["box_config"] = box_config
        if not box_config["success"]:
            return _finalize(root, result_path, False, steps, box_config["error"])

        inp = write_nwpesse_input(
            result_name=result_name,
            cluster_file=str(cluster["cluster_file"]),
            max_calculations=max_calculations,
            box_blocks=list(box_config["box_lines"]),
            optimizer=optimizer,
            workdir=str(root),
        )
        steps["write_nwpesse_input"] = inp
        if not inp["success"]:
            return _finalize(root, result_path, False, steps, inp["error"])

        run = run_nwpesse(str(inp["input_file"]), str(root), timeout=timeout)
        steps["run_nwpesse"] = run
        lowest = find_lowest_energy_geometry(str(root), result_name=result_name)
        steps["find_lowest_energy_geometry"] = lowest
        success = bool(run["success"]) and bool(lowest["success"])
        error = None if success else run.get("error") or lowest.get("error")
        return _finalize(root, result_path, success, steps, error)
    except Exception as exc:
        return _finalize(root, result_path, False, steps, f"{type(exc).__name__}: {exc}")


def _resolve_fragment_specs(formula: str | None, fragments: list[dict] | None) -> list[dict[str, Any]]:
    if formula and fragments:
        raise ValueError("Provide either formula or fragments, not both.")
    if formula:
        parsed = parse_cluster_formula(formula)
        if not parsed["success"]:
            raise ValueError(str(parsed["error"]))
        return list(parsed["fragments"])
    if fragments:
        return [{"name": str(item["name"]).lower(), "count": int(item["count"])} for item in fragments]
    raise ValueError("Provide a formula or at least one fragment.")


def _prepare_fragment_files(
    fragments: list[dict[str, Any]],
    workdir: Path,
    fragment_dir: str | None,
) -> dict[str, Any]:
    prepared = []
    issues = []
    source_dir = Path(fragment_dir).expanduser() if fragment_dir else None
    for fragment in fragments:
        name = str(fragment["name"]).lower()
        count = int(fragment["count"])
        target = workdir / f"{name}.xyz"
        if source_dir is not None:
            source = _find_fragment_file(source_dir, name)
            if source is None:
                issues.append(f"Missing fragment xyz for '{name}' in {source_dir}")
                continue
            shutil.copy2(source, target)
            prepared.append({"name": name, "count": count, "filename": target.name, "source": str(source)})
            continue
        written = write_fragment_xyz(name, str(target))
        if not written["success"]:
            issues.append(str(written["error"]))
            continue
        prepared.append({"name": name, "count": count, "filename": target.name, "source": "internal_library"})
    return {
        "success": not issues,
        "tool": "prepare_nwpesse_fragments",
        "fragments": prepared,
        "issues": issues,
        "error": "; ".join(issues) if issues else None,
    }


def _find_fragment_file(source_dir: Path, name: str) -> Path | None:
    expected = f"{name}.xyz"
    for path in source_dir.glob("*.xyz"):
        if path.name.lower() == expected:
            return path
    return None


def _finalize(
    workdir: Path,
    result_path: Path,
    success: bool,
    steps: dict[str, Any],
    error: str | None,
) -> dict[str, Any]:
    lowest = steps.get("find_lowest_energy_geometry") or {}
    cluster = steps.get("write_mol_cluster") or {}
    inp = steps.get("write_nwpesse_input") or {}
    box_config = steps.get("box_config") or {}
    result = {
        "success": success,
        "workflow": "nwpesse_global_minimum_search",
        "workdir": str(workdir),
        "formula": _formula_from_steps(steps),
        "fragments": steps.get("fragments"),
        "mol_cluster_path": cluster.get("cluster_file"),
        "mol_input_path": inp.get("input_file"),
        "run_result": steps.get("run_nwpesse"),
        "steps": steps,
        "lowest_energy": lowest.get("lowest_energy"),
        "energy_unit": lowest.get("energy_unit"),
        "lowest_geometry": lowest.get("lowest_geometry"),
        "lowest_geometry_copy": lowest.get("lowest_geometry_copy"),
        "candidate_count": lowest.get("candidate_count"),
        "all_candidates": lowest.get("all_candidates"),
        "box_config": box_config,
        "box_mode": box_config.get("box_mode"),
        "box_size": box_config.get("box_size"),
        "error": error,
        "workflow_result_path": str(result_path),
    }
    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def _formula_from_steps(steps: dict[str, Any]) -> str | None:
    if steps.get("formula") is not None:
        return str(steps["formula"])
    fragments = steps.get("fragments")
    if not isinstance(fragments, list):
        return None
    return "".join(f"({item.get('name')}){item.get('count')}" for item in fragments)
