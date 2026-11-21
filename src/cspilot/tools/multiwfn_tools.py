"""Local, allowlisted Multiwfn 3.8 analyses; never accept raw menu input."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from cspilot.config import load_settings
from cspilot.utils.runner import make_run_dir

# Checked against the 2026-Jan-7 build. Each entry includes export and clean exits.
# Population=7: Mulliken=5 (submenu output=1), Hirshfeld=1 (built-in densities=1).
# Bond orders=9: Mayer=1; export matrix=y; return=0; main-menu quit=q.
MENU_MAP = {
    "mulliken": ("7", "5", "1", "y", "0", "0", "q"),
    "hirshfeld": ("7", "1", "1", "y", "0", "q"),
    "mayer": ("9", "1", "y", "0", "q"),
}


def analyze_wavefunction(
    input_path: str | Path,
    workdir: str | Path,
    analysis: str = "mulliken",
    timeout: int = 120,
) -> dict[str, Any]:
    """Analyze a GBW (converted in isolation), Molden or formatted checkpoint file."""
    result: dict[str, Any] = {
        "success": False,
        "tool": "multiwfn_analysis",
        "error": None,
        "metadata": {"menu_version": "3.8", "analysis": analysis},
        "files": {},
    }
    try:
        if analysis not in MENU_MAP:
            raise ValueError(f"Unsupported analysis; choose from {', '.join(MENU_MAP)}")
        if not isinstance(timeout, int) or not 1 <= timeout <= 600:
            raise ValueError("timeout must be between 1 and 600 seconds")
        source = Path(input_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError(f"Wavefunction file does not exist: {source}")
        if source.suffix.lower() not in {".gbw", ".molden", ".input", ".fch", ".fchk"}:
            raise ValueError(
                "Use .gbw, .molden, .molden.input, .fch or .fchk; .out is not a wavefunction"
            )
        settings = load_settings()
        binary = shutil.which(settings.multiwfn_command)
        if not binary:
            raise ValueError("Multiwfn unavailable; configure MULTIWFN_COMMAND")
        root = make_run_dir(Path(workdir).resolve(), f"multiwfn-{analysis}")
        result["workdir"] = str(root)
        result["source_file"] = str(source)
        local = root / (
            "wavefunction"
            + (".molden.input" if source.name.endswith(".molden.input") else source.suffix)
        )
        shutil.copy2(source, local)
        if source.suffix.lower() == ".gbw":
            converter = shutil.which(settings.orca_2mkl_command)
            if not converter:
                orca = shutil.which(settings.orca_command)
                candidate = Path(orca).with_name("orca_2mkl") if orca else None
                converter = str(candidate) if candidate and candidate.is_file() else None
            if not converter:
                raise ValueError(
                    "GBW conversion needs ORCA_2MKL_COMMAND or orca_2mkl beside ORCA_COMMAND"
                )
            converted = subprocess.run(
                [converter, "wavefunction", "-molden"],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            log = root / "conversion.log"
            log.write_text(converted.stdout + converted.stderr, encoding="utf-8")
            result["files"]["conversion_log"] = str(log)
            local = root / "wavefunction.molden.input"
            if converted.returncode or not local.is_file():
                raise ValueError("orca_2mkl failed to produce Molden input; see conversion.log")
        result["files"]["wavefunction"] = str(local)
        script = "\n".join(MENU_MAP[analysis]) + "\n"
        commands = root / "menu.txt"
        commands.write_text(script, encoding="ascii")
        result["files"]["menu"] = str(commands)
        env = {**os.environ, "OMP_NUM_THREADS": "1", "OMP_STACKSIZE": "200M"}
        env.setdefault("Multiwfnpath", str(Path(binary).resolve().parent))
        process = subprocess.run(
            [binary, str(local), "-nt", "1"],
            input=script,
            capture_output=True,
            text=True,
            cwd=root,
            env=env,
            timeout=timeout,
        )
        output = root / "multiwfn.out"
        output.write_text(process.stdout, encoding="utf-8")
        stderr = root / "multiwfn.err"
        stderr.write_text(process.stderr, encoding="utf-8")
        result["files"].update(output=str(output), stderr=str(stderr))
        result["metadata"]["returncode"] = process.returncode
        if process.returncode:
            raise ValueError(
                f"Multiwfn exited with code {process.returncode}; see output and stderr"
            )
        if not re.search(r"Version\s+3\.8\b", process.stdout):
            raise ValueError("Unvalidated Multiwfn version; expected 3.8")
        if analysis == "mayer":
            matrix = root / "bndmat.txt"
            if not matrix.is_file():
                raise ValueError("Multiwfn did not export the bond-order matrix")
            # Multiwfn prints blocks of five columns with integer column/row labels.
            cells: dict[tuple[int, int], float] = {}
            columns: list[int] = []
            for line in matrix.read_text().splitlines():
                fields = line.split()
                if fields and all(v.isdigit() for v in fields):
                    columns = [int(v) for v in fields]
                elif fields and fields[0].isdigit() and len(fields) == len(columns) + 1:
                    for col, value in zip(columns, fields[1:], strict=True):
                        cells[int(fields[0]), col] = float(value.replace("D", "E"))
            count = max((i for i, _ in cells), default=0)
            if len(cells) != count * count:
                raise ValueError("Incomplete bond-order matrix")
            rows = [[cells[i, j] for j in range(1, count + 1)] for i in range(1, count + 1)]
            if not rows or any(len(row) != len(rows) for row in rows):
                raise ValueError("Invalid bond-order matrix shape")
            if not all(math.isfinite(v) for row in rows for v in row):
                raise ValueError("Non-finite bond order")
            result.update(bond_order_matrix=rows, bond_order_unit="dimensionless")
            result["files"]["bond_orders"] = str(matrix)
        else:
            exported = list(root.glob("*.chg"))
            if len(exported) != 1:
                raise ValueError("Multiwfn did not export one atomic-charge file")
            charges = []
            for index, line in enumerate(exported[0].read_text().splitlines(), 1):
                fields = line.split()
                if len(fields) != 5 or not all(math.isfinite(float(v)) for v in fields[1:]):
                    raise ValueError("Invalid atomic charge row")
                charges.append({"atom": index, "element": fields[0], "charge": float(fields[4])})
            atoms = re.search(r"Total atoms:\s*(\d+)", process.stdout)
            net = re.search(r"Net charge:\s*([-+\d.]+)", process.stdout)
            if not charges or not atoms or len(charges) != int(atoms[1]):
                raise ValueError("Incomplete atomic charges")
            total = sum(row["charge"] for row in charges)
            if not net or abs(total - float(net[1])) > 0.005:
                raise ValueError("Atomic charges do not sum to the wavefunction charge")
            result.update(atomic_charges=charges, charge_unit="e", total_charge=total)
            result["files"]["charges"] = str(exported[0])
        result["success"] = True
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    if result.get("workdir"):
        (Path(result["workdir"]) / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
