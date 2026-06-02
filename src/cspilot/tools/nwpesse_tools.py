from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cspilot.config import load_settings

ELEMENT_SYMBOLS = {
    "H",
    "He",
    "Li",
    "Be",
    "B",
    "C",
    "N",
    "O",
    "F",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "P",
    "S",
    "Cl",
    "Ar",
    "K",
    "Ca",
    "Sc",
    "Ti",
    "V",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
    "Cu",
    "Zn",
    "Ga",
    "Ge",
    "As",
    "Se",
    "Br",
    "Kr",
    "Rb",
    "Sr",
    "Y",
    "Zr",
    "Nb",
    "Mo",
    "Tc",
    "Ru",
    "Rh",
    "Pd",
    "Ag",
    "Cd",
    "In",
    "Sn",
    "Sb",
    "Te",
    "I",
    "Xe",
    "Cs",
    "Ba",
    "La",
    "Ce",
    "Pr",
    "Nd",
    "Pm",
    "Sm",
    "Eu",
    "Gd",
    "Tb",
    "Dy",
    "Ho",
    "Er",
    "Tm",
    "Yb",
    "Lu",
    "Hf",
    "Ta",
    "W",
    "Re",
    "Os",
    "Ir",
    "Pt",
    "Au",
    "Hg",
    "Tl",
    "Pb",
    "Bi",
    "Po",
    "At",
    "Rn",
}
FRAGMENT_LIBRARY: dict[str, tuple[str, list[tuple[str, float, float, float]]]] = {
    "h2o": (
        "water",
        [
            ("O", 0.000000, 0.000000, -0.110812),
            ("H", 0.000000, -0.783976, 0.443248),
            ("H", 0.000000, 0.783976, 0.443248),
        ],
    ),
    "water": (
        "water",
        [
            ("O", 0.000000, 0.000000, -0.110812),
            ("H", 0.000000, -0.783976, 0.443248),
            ("H", 0.000000, 0.783976, 0.443248),
        ],
    ),
    "o2": ("o2", [("O", 0.000000, 0.000000, -0.604000), ("O", 0.000000, 0.000000, 0.604000)]),
    "co2": (
        "co2",
        [
            ("O", 0.000000, 0.000000, -1.160000),
            ("C", 0.000000, 0.000000, 0.000000),
            ("O", 0.000000, 0.000000, 1.160000),
        ],
    ),
    "nh3": (
        "nh3",
        [
            ("N", 0.000000, 0.000000, 0.000000),
            ("H", 0.000000, 0.937700, 0.381600),
            ("H", 0.812100, -0.468800, 0.381600),
            ("H", -0.812100, -0.468800, 0.381600),
        ],
    ),
    "ch4": (
        "ch4",
        [
            ("C", 0.000000, 0.000000, 0.000000),
            ("H", 0.629118, 0.629118, 0.629118),
            ("H", -0.629118, -0.629118, 0.629118),
            ("H", -0.629118, 0.629118, -0.629118),
            ("H", 0.629118, -0.629118, -0.629118),
        ],
    ),
}
OPTIMIZER_BLOCKS = {
    "xtb_gxtb": """cp $inp$ $xxx$.xyz
xtb $xxx$.xyz --gxtb --opt  > $xxx$.out
energy=`awk 'NR==2{print $2}' xtbopt.xyz` ; sed -i "2c ${energy}" xtbopt.xyz
mv xtbopt.xyz $out$
rm $xxx$.xyz $xxx$.out  charges wbo xtbopt.log xtbrestart *.mol""",
}
BOX_MODES = {"per_fragment_type", "single", "custom"}
ENERGY_RE = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?")


def write_fragment_xyz(
    fragment_name: str,
    output_path: str,
    fragment_library: dict | None = None,
) -> dict[str, Any]:
    """Write a predefined fragment XYZ file for NWPESSe."""
    output = Path(output_path).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    library = {**FRAGMENT_LIBRARY, **(fragment_library or {})}
    key = fragment_name.strip().lower()
    try:
        if key in library:
            title, atoms = library[key]
        else:
            symbol = _element_symbol(fragment_name)
            if symbol is None:
                return _failure(
                    "write_fragment_xyz",
                    f"Fragment '{fragment_name}' is not in the internal library. Provide fragment xyz manually.",
                    fragment_name=fragment_name,
                    output_path=str(output),
                    available_fragments=sorted(FRAGMENT_LIBRARY),
                )
            title = symbol
            atoms = [(symbol, 0.0, 0.0, 0.0)]
        _write_xyz(output, title, atoms)
        return {
            "success": True,
            "tool": "write_fragment_xyz",
            "fragment_name": fragment_name,
            "normalized_name": key,
            "output_path": str(output),
            "num_atoms": len(atoms),
            "error": None,
        }
    except Exception as exc:
        return _failure("write_fragment_xyz", f"{type(exc).__name__}: {exc}", output_path=str(output))


def parse_cluster_formula(formula: str) -> dict[str, Any]:
    """Parse a NWPESSe fragment formula without atomizing arbitrary formulas."""
    text = formula.strip()
    if not text:
        return _failure("parse_cluster_formula", "Formula is empty")
    try:
        if ":" in text or "," in text:
            fragments = _parse_delimited_formula(text)
        elif re.search(r"\s+\d+", text):
            fragments = _parse_space_formula(text)
        else:
            fragments = _parse_grouped_formula(text)
        if not fragments:
            return _failure("parse_cluster_formula", "No fragments found")
        return {"success": True, "tool": "parse_cluster_formula", "formula": formula, "fragments": fragments, "error": None}
    except ValueError as exc:
        return _failure("parse_cluster_formula", str(exc), formula=formula)


def generate_box_config(
    fragments: list[dict],
    box_size: float = 3.0,
    box_mode: str = "per_fragment_type",
    custom_boxes: list[dict] | None = None,
) -> dict[str, Any]:
    """Generate validated NWPESSe placement box lines."""
    normalized_mode = box_mode.strip().lower()
    if normalized_mode not in BOX_MODES:
        return _failure(
            "generate_box_config",
            f"Unsupported box_mode '{box_mode}'. Supported: {sorted(BOX_MODES)}",
            box_mode=box_mode,
        )
    if box_size <= 0:
        return _failure("generate_box_config", "box_size must be positive", box_size=box_size)
    try:
        if normalized_mode == "custom":
            if not custom_boxes:
                return _failure(
                    "generate_box_config",
                    "custom box_mode requires structured custom_boxes.",
                    box_mode=normalized_mode,
                )
            box_lines = [_box_line_from_dict(box) for box in custom_boxes]
        elif normalized_mode == "single":
            box_lines = [_default_box_line(box_size)]
        else:
            unique_names = []
            for fragment in fragments:
                name = str(fragment["name"]).lower()
                if name not in unique_names:
                    unique_names.append(name)
            box_lines = [_default_box_line(box_size) for _ in unique_names]
        return {
            "success": True,
            "tool": "generate_box_config",
            "box_mode": normalized_mode,
            "box_size": box_size,
            "box_lines": box_lines,
            "box_count": len(box_lines),
            "error": None,
        }
    except Exception as exc:
        return _failure(
            "generate_box_config",
            f"{type(exc).__name__}: {exc}",
            box_mode=normalized_mode,
            box_size=box_size,
        )


def write_mol_cluster(
    fragments: list[dict],
    workdir: str,
    cluster_filename: str = "mol.cluster",
) -> dict[str, Any]:
    """Write the NWPESSe mol.cluster file."""
    root = Path(workdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    cluster_path = root / cluster_filename
    lines = [str(len(fragments))]
    normalized: list[dict[str, Any]] = []
    for fragment in fragments:
        name = str(fragment["name"]).lower()
        count = int(fragment["count"])
        filename = str(fragment.get("filename") or f"{name}.xyz")
        lines.append(f"{filename} {count}")
        normalized.append({"name": name, "count": count, "filename": filename})
    cluster_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "success": True,
        "tool": "write_mol_cluster",
        "cluster_file": str(cluster_path),
        "fragments": normalized,
        "error": None,
    }


def write_nwpesse_input(
    result_name: str,
    cluster_file: str,
    max_calculations: int,
    box_blocks: list[str],
    optimizer: str,
    workdir: str,
    input_filename: str = "mol.inp",
) -> dict[str, Any]:
    """Write the NWPESSe mol.inp file with a whitelisted optimizer block."""
    root = Path(workdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    if optimizer not in OPTIMIZER_BLOCKS:
        return _failure(
            "write_nwpesse_input",
            f"Unsupported optimizer '{optimizer}'. Supported: {sorted(OPTIMIZER_BLOCKS)}",
        )
    if max_calculations < 1:
        return _failure("write_nwpesse_input", "max_calculations must be at least 1")
    input_path = root / input_filename
    content = "\n".join(
        [
            result_name,
            Path(cluster_file).name,
            str(max_calculations),
            ">>>>",
            *box_blocks,
            ">>>>",
            OPTIMIZER_BLOCKS[optimizer],
            ">>>>",
            "",
        ]
    )
    input_path.write_text(content, encoding="utf-8")
    return {
        "success": True,
        "tool": "write_nwpesse_input",
        "input_file": str(input_path),
        "result_name": result_name,
        "cluster_file": str(cluster_file),
        "max_calculations": max_calculations,
        "box_blocks": box_blocks,
        "optimizer": optimizer,
        "error": None,
    }


def run_nwpesse(input_file: str, workdir: str, timeout: int = 86400) -> dict[str, Any]:
    """Run NWPESSe with a generated input file."""
    root = Path(workdir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    input_path = Path(input_file).expanduser()
    settings = load_settings()
    stdout_file = root / "nwpesse.stdout"
    stderr_file = root / "nwpesse.stderr"
    run_json = root / "nwpesse_run.json"
    command = [settings.nwpesse_command, input_path.name]
    if shutil.which(settings.nwpesse_command) is None:
        result = {
            "success": False,
            "tool": "run_nwpesse",
            "command": command,
            "returncode": None,
            "stdout_file": str(stdout_file),
            "stderr_file": str(stderr_file),
            "workdir": str(root),
            "error": f"Executable not found: {settings.nwpesse_command}",
        }
        stdout_file.write_text("", encoding="utf-8")
        stderr_file.write_text(result["error"] + "\n", encoding="utf-8")
        _write_json(run_json, result)
        return result
    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        stdout_file.write_text(completed.stdout, encoding="utf-8")
        stderr_file.write_text(completed.stderr, encoding="utf-8")
        result = {
            "success": completed.returncode == 0,
            "tool": "run_nwpesse",
            "command": command,
            "returncode": completed.returncode,
            "stdout_file": str(stdout_file),
            "stderr_file": str(stderr_file),
            "workdir": str(root),
            "error": None if completed.returncode == 0 else "NWPESSe failed",
        }
    except subprocess.TimeoutExpired as exc:
        stdout_file.write_text(_as_text(exc.stdout), encoding="utf-8")
        stderr_file.write_text(_as_text(exc.stderr), encoding="utf-8")
        result = {
            "success": False,
            "tool": "run_nwpesse",
            "command": command,
            "returncode": None,
            "stdout_file": str(stdout_file),
            "stderr_file": str(stderr_file),
            "workdir": str(root),
            "error": f"NWPESSe timed out after {timeout} seconds",
        }
    _write_json(run_json, result)
    return result


def find_lowest_energy_geometry(workdir: str, result_name: str | None = None) -> dict[str, Any]:
    """Find the lowest-energy generated XYZ file using numeric line-2 energies."""
    root = Path(workdir).expanduser()
    searched_dirs = _candidate_search_dirs(root, result_name)
    candidates = []
    seen_paths = set()
    for directory in searched_dirs:
        for path in sorted(directory.glob("*.xyz")):
            resolved = path.resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            parsed = _read_xyz_second_line_energy(path)
            if parsed is None:
                continue
            energy, energy_unit = parsed
            candidates.append({"path": str(path), "energy": energy, "energy_unit": energy_unit})
    for path in sorted(root.rglob("*.xyz")):
        resolved = path.resolve()
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        parsed = _read_xyz_second_line_energy(path)
        if parsed is None:
            continue
        energy, energy_unit = parsed
        candidates.append({"path": str(path), "energy": energy, "energy_unit": energy_unit})
    if not candidates:
        return _failure(
            "find_lowest_energy_geometry",
            "No XYZ candidates with numeric second-line energies were found.",
            workdir=str(root),
            result_name=result_name,
            searched_directories=[str(path) for path in searched_dirs],
            all_candidates=[],
        )
    ordered = sorted(candidates, key=lambda item: item["energy"])
    best = ordered[0]
    copy_path = root / "lowest_energy.xyz"
    shutil.copy2(best["path"], copy_path)
    return {
        "success": True,
        "tool": "find_lowest_energy_geometry",
        "lowest_energy": float(best["energy"]),
        "energy_unit": best["energy_unit"],
        "lowest_geometry": best["path"],
        "lowest_geometry_copy": str(copy_path),
        "candidate_count": len(ordered),
        "all_candidates": ordered,
        "searched_directories": [str(path) for path in searched_dirs],
        "workdir": str(root),
        "result_name": result_name,
        "error": None,
    }


def _parse_delimited_formula(text: str) -> list[dict[str, Any]]:
    fragments = []
    for part in re.split(r"\s*,\s*", text):
        if not part:
            continue
        pieces = part.split(":")
        if len(pieces) != 2 or not pieces[0].strip() or not pieces[1].strip().isdigit():
            raise ValueError(f"Ambiguous fragment specification: {part}")
        fragments.append(_fragment(pieces[0], int(pieces[1])))
    return fragments


def _parse_space_formula(text: str) -> list[dict[str, Any]]:
    tokens = text.split()
    if len(tokens) % 2:
        raise ValueError("Space-separated formula must be name/count pairs.")
    return [_fragment(tokens[index], int(tokens[index + 1])) for index in range(0, len(tokens), 2)]


def _parse_grouped_formula(text: str) -> list[dict[str, Any]]:
    fragments = []
    index = 0
    while index < len(text):
        if text[index] in "([":
            close = ")" if text[index] == "(" else "]"
            end = text.find(close, index + 1)
            if end == -1:
                raise ValueError("Unclosed fragment group.")
            name = text[index + 1 : end]
            index = end + 1
        else:
            match = re.match(r"[A-Za-z][A-Za-z0-9]*", text[index:])
            if not match:
                raise ValueError(f"Could not parse formula near: {text[index:]}")
            name = match.group(0)
            index += len(name)
        count_match = re.match(r"\d+", text[index:])
        count = int(count_match.group(0)) if count_match else 1
        if count_match:
            index += len(count_match.group(0))
        fragments.append(_fragment(name, count))
    return fragments


def _fragment(name: str, count: int) -> dict[str, Any]:
    if count < 1:
        raise ValueError(f"Fragment count must be at least 1 for {name}.")
    normalized = name.strip().lower()
    if not normalized:
        raise ValueError("Fragment name is empty.")
    return {"name": normalized, "count": count, "label": name.strip()}


def _element_symbol(name: str) -> str | None:
    cleaned = name.strip()
    symbol = cleaned[:1].upper() + cleaned[1:].lower()
    return symbol if symbol in ELEMENT_SYMBOLS else None


def _write_xyz(path: Path, title: str, atoms: list[tuple[str, float, float, float]]) -> None:
    lines = [str(len(atoms)), title]
    lines.extend(f"{symbol} {x:.6f} {y:.6f} {z:.6f}" for symbol, x, y, z in atoms)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_xyz_second_line_energy(path: Path) -> tuple[float, str | None] | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    if len(lines) < 2:
        return None
    match = ENERGY_RE.search(lines[1])
    if match is None:
        return None
    unit = "au" if re.search(r"\bau\b", lines[1], flags=re.IGNORECASE) else None
    return float(match.group(0)), unit


def _candidate_search_dirs(root: Path, result_name: str | None) -> list[Path]:
    directories = [root]
    if result_name:
        named = root / f"{result_name}-LM"
        if named.exists() and named.is_dir():
            directories.append(named)
    directories.extend(path for path in sorted(root.glob("*-LM")) if path.is_dir())
    seen = set()
    unique = []
    for directory in directories:
        resolved = directory.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(directory)
    return unique


def _default_box_line(box_size: float) -> str:
    value = _format_box_number(box_size)
    return f"inbox 0. 0. 0. {value} {value} {value}"


def _box_line_from_dict(box: dict) -> str:
    required = ("x0", "y0", "z0", "x1", "y1", "z1")
    missing = [key for key in required if key not in box]
    if missing:
        raise ValueError(f"custom box is missing keys: {missing}")
    values = [_format_box_number(float(box[key])) for key in required]
    return f"inbox {' '.join(values)}"


def _format_box_number(value: float) -> str:
    return f"{value:.1f}" if value.is_integer() else f"{value:g}"


def _as_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _failure(tool: str, error: str, **extra: Any) -> dict[str, Any]:
    return {"success": False, "tool": tool, "error": error, **extra}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
