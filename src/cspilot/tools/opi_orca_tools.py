from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from cspilot.config import Settings
from cspilot.schemas import ProcessResult

TASK_SP = "sp"
TASK_OPT = "opt"
TASK_FREQ = "freq"


def opi_available() -> bool:
    return importlib.util.find_spec("opi") is not None


def orca_single_point(
    xyz_path: Path | str,
    workdir: Path | str,
    method: str,
    basis: str,
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1,
    *,
    orca_command: str | None = None,
) -> dict[str, Any]:
    return _run_orca_task(
        xyz_path=xyz_path,
        workdir=workdir,
        method=method,
        basis=basis,
        charge=charge,
        mult=mult,
        nprocs=nprocs,
        task=TASK_SP,
        orca_command=orca_command,
    )


def orca_optimize(
    xyz_path: Path | str,
    workdir: Path | str,
    method: str,
    basis: str,
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1,
    *,
    orca_command: str | None = None,
) -> dict[str, Any]:
    return _run_orca_task(
        xyz_path=xyz_path,
        workdir=workdir,
        method=method,
        basis=basis,
        charge=charge,
        mult=mult,
        nprocs=nprocs,
        task=TASK_OPT,
        orca_command=orca_command,
    )


def orca_frequency(
    xyz_path: Path | str,
    workdir: Path | str,
    method: str,
    basis: str,
    charge: int = 0,
    mult: int = 1,
    nprocs: int = 1,
    *,
    orca_command: str | None = None,
) -> dict[str, Any]:
    return _run_orca_task(
        xyz_path=xyz_path,
        workdir=workdir,
        method=method,
        basis=basis,
        charge=charge,
        mult=mult,
        nprocs=nprocs,
        task=TASK_FREQ,
        orca_command=orca_command,
    )


def parse_orca_result(output_path: Path | str) -> dict[str, Any]:
    output_path = Path(output_path)
    result: dict[str, Any] = {
        "output_path": str(output_path),
        "status": "missing" if not output_path.exists() else "parsed",
        "terminated_normally": None,
        "properties": {},
        "errors": [],
    }
    if not output_path.exists():
        result["errors"].append(f"ORCA output file not found: {output_path}")
        return result

    opi_result = _parse_with_opi(output_path)
    result.update(opi_result)

    text_result = _parse_orca_text(output_path)
    result["properties"] = _merge_missing(result.get("properties", {}), text_result["properties"])
    if result.get("terminated_normally") is None:
        result["terminated_normally"] = text_result["terminated_normally"]
    if text_result.get("error_message") and not result.get("error_message"):
        result["error_message"] = text_result["error_message"]
    return _jsonable(result)


def write_orca_input(
    structure_path: Path,
    run_dir: Path,
    method: str,
    basis: str,
    charge: int,
    mult: int,
    task: str = TASK_SP,
    nprocs: int = 1,
) -> Path:
    calc = _build_calculator(
        xyz_path=structure_path,
        workdir=run_dir,
        method=method,
        basis=basis,
        charge=charge,
        mult=mult,
        nprocs=nprocs,
        task=task,
    )
    calc.write_input()
    return Path(calc.inpfile)


def single_point_with_orca(
    input_file: Path,
    run_dir: Path,
    settings: Settings,
    method: str,
    basis: str,
    charge: int,
    mult: int,
) -> tuple[bool, str, ProcessResult | None, dict[str, Any]]:
    result = orca_single_point(
        xyz_path=input_file,
        workdir=run_dir,
        method=method,
        basis=basis,
        charge=charge,
        mult=mult,
        orca_command=settings.orca_command,
    )
    result["orca_command"] = settings.orca_command
    ok = result.get("status") == "ok"
    message = (
        "ORCA single point completed"
        if ok
        else result.get("error_message", "ORCA single point failed")
    )
    return ok, str(message), None, result


def _run_orca_task(
    xyz_path: Path | str,
    workdir: Path | str,
    method: str,
    basis: str,
    charge: int,
    mult: int,
    nprocs: int,
    task: str,
    orca_command: str | None = None,
) -> dict[str, Any]:
    xyz_path = Path(xyz_path).resolve()
    workdir = Path(workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)

    result: dict[str, Any] = {
        "status": "failed",
        "task": task,
        "input_xyz": str(xyz_path),
        "workdir": str(workdir),
        "basename": "job",
        "parameters": {
            "method": method,
            "basis": basis,
            "charge": charge,
            "mult": mult,
            "nprocs": nprocs,
        },
        "files": {
            "input": str(workdir / "job.inp"),
            "output": str(workdir / "job.out"),
        },
        "opi_available": opi_available(),
        "orca_command": _resolve_orca_command(orca_command),
    }

    try:
        _configure_opi_orca(result["orca_command"])
        calc = _build_calculator(
            xyz_path=xyz_path,
            workdir=workdir,
            method=method,
            basis=basis,
            charge=charge,
            mult=mult,
            nprocs=nprocs,
            task=task,
        )
        calc.write_input()
        result["files"]["input"] = str(calc.inpfile)

        is_available, availability_message = _orca_executable_available(result["orca_command"])
        if not is_available:
            result["status"] = "skipped"
            result["error_message"] = availability_message
            return _jsonable(result)

        calc.run()

        output = calc.get_output()
        output_path = Path(output.get_outfile())
        result["files"]["output"] = str(output_path)
        parsed = parse_orca_result(output_path)
        result["result"] = parsed
        result["status"] = "ok" if parsed.get("terminated_normally") else "failed"
        if not parsed.get("terminated_normally"):
            result["error_message"] = parsed.get("error_message", "ORCA did not terminate normally")
    except FileNotFoundError as exc:
        result["error_message"] = str(exc)
    except Exception as exc:
        result["error_message"] = f"{type(exc).__name__}: {exc}"

    return _jsonable(result)


def _build_calculator(
    xyz_path: Path,
    workdir: Path,
    method: str,
    basis: str,
    charge: int,
    mult: int,
    nprocs: int,
    task: str,
) -> Any:
    from opi.core import Calculator
    from opi.input.core import SimpleKeyword
    from opi.input.simple_keywords import Scf, Task
    from opi.input.structures import Structure

    calc = Calculator(basename="job", working_dir=workdir, version_check=False)
    calc.structure = Structure.from_xyz(xyz_path, charge=charge, multiplicity=mult)
    calc.input.ncores = nprocs
    calc.input.add_simple_keywords(
        Scf.NOAUTOSTART,
        SimpleKeyword(method),
        SimpleKeyword(basis),
        _task_keyword(Task, task),
    )
    return calc


def _task_keyword(task_enum: Any, task: str) -> Any:
    task_map = {
        TASK_SP: task_enum.SP,
        TASK_OPT: task_enum.OPT,
        TASK_FREQ: task_enum.FREQ,
    }
    try:
        return task_map[task.lower()]
    except KeyError as exc:
        valid = ", ".join(sorted(task_map))
        raise ValueError(f"Unsupported ORCA task '{task}'. Expected one of: {valid}") from exc


def _parse_with_opi(output_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "status": "parsed",
        "terminated_normally": None,
        "properties": {},
        "errors": [],
    }
    if not opi_available():
        result["errors"].append("OPI is not installed; used text parser only.")
        return result

    try:
        from opi.output.core import Output

        output = Output(output_path.stem, working_dir=output_path.parent, version_check=False)
        result["terminated_normally"] = output.terminated_normally()
        if not result["terminated_normally"]:
            result["error_message"] = _safe_call(output.error_message)
        output.parse()
        result["properties"].update(_collect_opi_properties(output))
    except Exception as exc:
        result["errors"].append(f"OPI parse failed: {type(exc).__name__}: {exc}")
    return result


def _collect_opi_properties(output: Any) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    getters = {
        "final_energy_hartree": output.get_final_energy,
        "scf_converged": output.scf_converged,
        "geometry_optimization_converged": output.geometry_optimization_converged,
        "charge": output.get_charge,
        "multiplicity": output.get_mult,
        "homo": output.get_homo,
        "lumo": output.get_lumo,
        "homo_lumo_gap_ev": output.get_hl_gap,
        "dipole": output.get_dipole,
        "zero_point_energy": output.get_zpe,
        "gibbs_free_energy": output.get_free_energy,
        "enthalpy": output.get_enthalpy,
        "entropy": output.get_entropy,
        "ir": output.get_ir,
    }
    for key, getter in getters.items():
        value = _safe_call(getter)
        if value is not None:
            properties[key] = _jsonable(value)

    structure = _safe_call(output.get_structure)
    if structure is not None:
        properties["final_structure_xyz"] = _safe_call(structure.to_xyz_block)

    energies = _safe_call(output.get_energies)
    if energies is not None:
        properties["energies"] = _jsonable(energies)
    return properties


def _parse_orca_text(output_path: Path) -> dict[str, Any]:
    text = output_path.read_text(encoding="utf-8", errors="replace")
    properties: dict[str, Any] = {}

    energy = _last_float_match(r"FINAL SINGLE POINT ENERGY\s+([-+]?\d+(?:\.\d+)?)", text)
    if energy is not None:
        properties["final_energy_hartree"] = energy

    scf_match = re.search(r"SCF CONVERGED AFTER\s+(\d+)\s+CYCLES", text)
    if scf_match:
        properties["scf_converged"] = True
        properties["scf_cycles"] = int(scf_match.group(1))
    elif "SCF NOT CONVERGED" in text or "SCF DID NOT CONVERGE" in text:
        properties["scf_converged"] = False

    if "THE OPTIMIZATION HAS CONVERGED" in text:
        properties["geometry_optimization_converged"] = True
    elif "OPTIMIZATION RUN DONE" in text and "THE OPTIMIZATION HAS NOT CONVERGED" in text:
        properties["geometry_optimization_converged"] = False

    zpe = _last_float_match(r"Zero point energy\s+\.\.\.\s+([-+]?\d+(?:\.\d+)?)", text)
    if zpe is not None:
        properties["zero_point_energy"] = zpe

    gibbs = _last_float_match(r"Final Gibbs free energy\s+\.\.\.\s+([-+]?\d+(?:\.\d+)?)", text)
    if gibbs is not None:
        properties["gibbs_free_energy"] = gibbs

    enthalpy = _last_float_match(r"Total enthalpy\s+\.\.\.\s+([-+]?\d+(?:\.\d+)?)", text)
    if enthalpy is not None:
        properties["enthalpy"] = enthalpy

    return {
        "terminated_normally": "ORCA TERMINATED NORMALLY" in text,
        "properties": properties,
        "error_message": _extract_error_message(text),
    }


def _extract_error_message(text: str) -> str | None:
    if "ORCA TERMINATED NORMALLY" in text:
        return None
    patterns = [
        r"\*\*\* ERROR: (?P<message>.+)",
        r"ORCA finished by error termination.*",
        r"Error : (?P<message>.+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.groupdict().get("message") or match.group(0)
    return None


def _last_float_match(pattern: str, text: str) -> float | None:
    matches = re.findall(pattern, text, flags=re.IGNORECASE)
    return float(matches[-1]) if matches else None


def _merge_missing(primary: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    merged = dict(primary)
    for key, value in fallback.items():
        if key not in merged or merged[key] is None:
            merged[key] = value
    return merged


def _safe_call(func: Any) -> Any:
    try:
        return func()
    except Exception:
        return None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_jsonable(item) for item in value]
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if hasattr(value, "dict"):
        return _jsonable(value.dict())
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    return str(value)


def _resolve_orca_command(orca_command: str | None = None) -> str:
    load_dotenv(".env.cspilot")
    return (
        orca_command
        or os.getenv("ORCA_COMMAND")
        or os.getenv("OPI_ORCA")
        or os.getenv("ORCA_PATH")
        or "orca"
    )


def _configure_opi_orca(orca_command: str) -> None:
    os.environ["OPI_ORCA"] = orca_command


def _orca_executable_available(command: str) -> tuple[bool, str | None]:
    executable = str(Path(command).expanduser()) if "/" in command else shutil.which(command)
    if executable is None:
        return False, f"Executable not found: {command}"
    if not Path(executable).exists():
        return False, f"Executable not found: {executable}"
    try:
        completed = subprocess.run(
            [executable, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception as exc:
        return False, f"Could not validate ORCA executable '{executable}': {exc}"

    version_text = f"{completed.stdout}\n{completed.stderr}"
    normalized_version_text = version_text.lower()
    if "program version" in normalized_version_text and "orca" in normalized_version_text:
        return True, None
    return False, f"Executable at '{executable}' does not look like the ORCA quantum chemistry binary."
