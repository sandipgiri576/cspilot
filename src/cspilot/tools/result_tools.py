from __future__ import annotations

import json
import re
from fnmatch import fnmatch
from pathlib import Path
from typing import Any

RESULT_FILENAMES = {
    "result.json",
    "workflow_result.json",
    "final_state.json",
    "execution_result.json",
}

PROPERTY_ALIASES = {
    "gibbs": ["gibbs_free_energy", "gibbs_energy", "final_gibbs_energy", "G"],
    "gibbs free energy": ["gibbs_free_energy", "gibbs_energy", "final_gibbs_energy", "G"],
    "free energy": ["gibbs_free_energy", "gibbs_energy", "final_gibbs_energy", "G"],
    "enthalpy": ["enthalpy", "thermal_enthalpy", "H"],
    "electronic energy": [
        "final_energy",
        "final_energy_hartree",
        "electronic_energy",
        "total_energy",
        "energy_hartree",
    ],
    "total energy": [
        "final_energy",
        "final_energy_hartree",
        "electronic_energy",
        "total_energy",
        "energy_hartree",
    ],
    "final energy": [
        "final_energy",
        "final_energy_hartree",
        "electronic_energy",
        "total_energy",
        "energy_hartree",
    ],
    "homo lumo gap": ["homo_lumo_gap", "homo_lumo_gap_ev", "gap", "HOMO_LUMO_gap"],
    "gap": ["homo_lumo_gap", "homo_lumo_gap_ev", "gap", "HOMO_LUMO_gap"],
    "frequencies": ["frequencies", "vibrational_frequencies"],
}


def find_result_json(workdir: str, latest: bool = True) -> dict[str, Any]:
    """Find supported result JSON files recursively below a working directory."""
    root = Path(workdir).expanduser()
    if not root.exists():
        return {"success": False, "workdir": str(root), "error": "Workdir not found"}

    matches = [
        path
        for path in root.rglob("*.json")
        if path.name in RESULT_FILENAMES or fnmatch(path.name, "step_*_result.json")
    ]
    matches.sort(key=lambda path: (path.stat().st_mtime, str(path)), reverse=True)
    if not matches:
        return {"success": False, "workdir": str(root), "error": "No result JSON files found"}

    paths = [str(path) for path in matches]
    result: dict[str, Any] = {"success": True, "workdir": str(root), "paths": paths}
    if latest:
        result["path"] = paths[0]
    return result


def load_result_json(path: str) -> dict[str, Any]:
    """Load a result JSON file."""
    result_path = Path(path).expanduser()
    if not result_path.exists():
        return {"success": False, "path": str(result_path), "error": "Result file not found"}
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"success": False, "path": str(result_path), "error": f"Could not load JSON: {exc}"}
    return {"success": True, "path": str(result_path), "data": data}


def get_property_from_result(path: str, property_name: str) -> dict[str, Any]:
    """Look up a named calculated property recursively in result JSON."""
    loaded = load_result_json(path)
    if not loaded["success"]:
        return {
            "success": False,
            "property": property_name,
            "source_file": str(Path(path).expanduser()),
            "error": loaded["error"],
        }

    lookup_name = _normalize_key(property_name)
    aliases = PROPERTY_ALIASES.get(lookup_name, [property_name])
    expected = {_normalize_key(alias) for alias in aliases}
    found = _recursive_find(loaded["data"], expected)
    if found is None:
        return {
            "success": False,
            "property": property_name,
            "source_file": str(Path(path).expanduser()),
            "error": "Property not found",
        }

    matched_key, value = found
    return {
        "success": True,
        "property": property_name,
        "matched_key": matched_key,
        "value": value,
        "source_file": str(Path(path).expanduser()),
    }


def _recursive_find(data: Any, expected: set[str]) -> tuple[str, Any] | None:
    if isinstance(data, dict):
        for key, value in data.items():
            if _normalize_key(str(key)) in expected:
                return str(key), value
        for value in data.values():
            found = _recursive_find(value, expected)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _recursive_find(item, expected)
            if found is not None:
                return found
    return None


def _normalize_key(key: str) -> str:
    return re.sub(r"[_-]+", " ", key.strip().lower())
