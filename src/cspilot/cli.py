from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Literal

import typer
from rich.console import Console
from rich.table import Table

from cspilot.config import load_settings
from cspilot.schemas import CommandResult
from cspilot.tools.ase_tools import summarize_structure
from cspilot.tools.mace_tools import optimize_with_mace
from cspilot.tools.opi_orca_tools import single_point_with_orca
from cspilot.tools.xtb_tools import optimize_with_xtb
from cspilot.utils.runner import copy_input, make_run_dir, write_json
from cspilot.workflows.mace_to_orca import run_mace_to_orca
from cspilot.workflows.xtb_to_orca_freq import run_xtb_to_orca_freq
from cspilot.workflows.xtb_to_orca_sp import run_xtb_to_orca_sp

app = typer.Typer(help="Computational chemistry workflow CLI.")
workflow_app = typer.Typer(help="Multi-step computational chemistry workflows.")
app.add_typer(workflow_app, name="workflow")
console = Console()


InputPath = Annotated[
    Path,
    typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True),
]


def _finish(result: CommandResult) -> None:
    write_json(result.run_dir / "result.json", result)
    status_style = {"ok": "green", "failed": "red", "skipped": "yellow"}[result.status]
    console.print(f"[{status_style}]{result.status.upper()}[/] {result.command}")
    console.print(f"Run directory: {result.run_dir}")
    if result.message:
        console.print(result.message)


def _finish_workflow(result: dict[str, object]) -> None:
    status = str(result.get("status", "failed"))
    status_style = {"ok": "green", "failed": "red", "skipped": "yellow"}.get(status, "red")
    console.print(f"[{status_style}]{status.upper()}[/] {result.get('workflow')}")
    console.print(f"Run directory: {result.get('workdir')}")
    console.print(f"Result: {result.get('workflow_result_path')}")
    final_energy = result.get("final_energy_hartree")
    if final_energy is not None:
        console.print(f"Final energy: {final_energy} Eh")
    if result.get("message"):
        console.print(str(result["message"]))


@app.command("agent")
def run_agent(
    request: Annotated[str, typer.Argument(help="Natural language computational chemistry request.")],
    workdir: Annotated[
        Path,
        typer.Option(help="Directory for agent results and tool subruns.", resolve_path=True),
    ] = Path("runs/agent_test"),
    model: Annotated[str | None, typer.Option(help="AGAPI model identifier.")] = None,
    base_url: Annotated[str | None, typer.Option(help="OpenAI-compatible AGAPI base URL.")] = None,
    agent_profile: Annotated[
        Literal["chem", "materials", "general"],
        typer.Option(help="Agent instruction and tool profile."),
    ] = "chem",
) -> None:
    """Run a tool-using computational chemistry agent through AGAPI."""
    from cspilot.agents.openai_agent import run_agent_request

    try:
        result = asyncio.run(
            run_agent_request(
                request,
                workdir,
                model=model,
                base_url=base_url,
                profile=agent_profile,
            )
        )
    except ValueError as exc:
        console.print(f"[red]Configuration error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(result["final_output"])
    console.print(f"Result: {result['result_path']}")


@app.command()
def inspect(input_path: InputPath) -> None:
    """Inspect a structure file with ASE."""
    settings = load_settings()
    run_dir = make_run_dir(settings.runs_dir, "inspect")
    run_input = copy_input(input_path, run_dir)
    summary = summarize_structure(run_input)

    table = Table(title="Structure")
    table.add_column("Property")
    table.add_column("Value")
    table.add_row("Formula", summary.formula)
    table.add_row("Atoms", str(summary.natoms))
    table.add_row("PBC", str(summary.pbc))
    table.add_row("Center of mass", ", ".join(f"{value:.6f}" for value in summary.center_of_mass))
    console.print(table)

    _finish(
        CommandResult(
            command="inspect",
            status="ok",
            run_dir=run_dir,
            input_path=input_path,
            structure=summary,
            outputs={"result_json": str(run_dir / "result.json")},
        )
    )


@app.command("xtb-opt")
def xtb_opt(
    input_path: InputPath,
    charge: Annotated[int, typer.Option(help="Molecular charge.")] = 0,
    uhf: Annotated[int, typer.Option(help="Number of unpaired electrons for xTB.")] = 0,
) -> None:
    """Run an xTB geometry optimization."""
    settings = load_settings()
    run_dir = make_run_dir(settings.runs_dir, "xtb-opt")
    run_input = copy_input(input_path, run_dir)
    summary = summarize_structure(run_input)
    ok, message, process, outputs = optimize_with_xtb(run_input, run_dir, settings, charge, uhf)

    payload_outputs = dict(outputs)
    if process is not None:
        payload_outputs["process"] = process.model_dump(mode="json")

    _finish(
        CommandResult(
            command="xtb-opt",
            status="ok" if ok else ("failed" if process is not None else "skipped"),
            run_dir=run_dir,
            input_path=input_path,
            structure=summary,
            parameters={"charge": charge, "uhf": uhf},
            outputs=payload_outputs,
            message=message,
        )
    )


@app.command("orca-sp")
def orca_sp(
    input_path: InputPath,
    method: Annotated[str, typer.Option(help="ORCA method keyword.")] = "r2scan-3c",
    basis: Annotated[str, typer.Option(help="ORCA basis keyword.")] = "def2-SVP",
    charge: Annotated[int, typer.Option(help="Molecular charge.")] = 0,
    mult: Annotated[int, typer.Option(help="Spin multiplicity.")] = 1,
) -> None:
    """Run an ORCA single point calculation."""
    settings = load_settings()
    run_dir = make_run_dir(settings.runs_dir, "orca-sp")
    run_input = copy_input(input_path, run_dir)
    summary = summarize_structure(run_input)
    ok, message, process, outputs = single_point_with_orca(
        run_input,
        run_dir,
        settings,
        method,
        basis,
        charge,
        mult,
    )

    payload_outputs = dict(outputs)
    if process is not None:
        payload_outputs["process"] = process.model_dump(mode="json")

    _finish(
        CommandResult(
            command="orca-sp",
            status="ok" if ok else ("failed" if process is not None else "skipped"),
            run_dir=run_dir,
            input_path=input_path,
            structure=summary,
            parameters={"method": method, "basis": basis, "charge": charge, "mult": mult},
            outputs=payload_outputs,
            message=message,
        )
    )


@app.command("mace-opt")
def mace_opt(
    input_path: InputPath,
    model: Annotated[Path, typer.Option(help="Path to a MACE model file.", resolve_path=True)],
    fmax: Annotated[float, typer.Option(help="Force convergence threshold in eV/A.")] = 0.05,
    steps: Annotated[int, typer.Option(help="Maximum optimizer steps.")] = 200,
) -> None:
    """Run a MACE geometry optimization."""
    settings = load_settings()
    run_dir = make_run_dir(settings.runs_dir, "mace-opt")
    run_input = copy_input(input_path, run_dir)
    summary = summarize_structure(run_input)
    ok, message, outputs = optimize_with_mace(run_input, run_dir, model, fmax=fmax, steps=steps)

    _finish(
        CommandResult(
            command="mace-opt",
            status="ok" if ok else "skipped",
            run_dir=run_dir,
            input_path=input_path,
            structure=summary,
            parameters={"model": str(model), "fmax": fmax, "steps": steps},
            outputs=outputs,
            message=message,
        )
    )


@workflow_app.command("xtb-orca-sp")
def workflow_xtb_orca_sp(
    input_path: InputPath,
    charge: Annotated[int, typer.Option(help="Molecular charge.")] = 0,
    mult: Annotated[int, typer.Option(help="Spin multiplicity.")] = 1,
    method: Annotated[str, typer.Option(help="ORCA method keyword.")] = "r2scan-3c",
    basis: Annotated[str, typer.Option(help="ORCA basis keyword.")] = "def2-SVP",
    uhf: Annotated[int, typer.Option(help="Number of unpaired electrons for xTB.")] = 0,
    nprocs: Annotated[int, typer.Option(help="ORCA processor count.")] = 1,
) -> None:
    """Run xTB optimization followed by an ORCA single point."""
    _finish_workflow(
        run_xtb_to_orca_sp(
            input_path,
            charge=charge,
            mult=mult,
            method=method,
            basis=basis,
            uhf=uhf,
            nprocs=nprocs,
        )
    )


@workflow_app.command("mace-orca")
def workflow_mace_orca(
    input_path: InputPath,
    charge: Annotated[int, typer.Option(help="Molecular charge.")] = 0,
    mult: Annotated[int, typer.Option(help="Spin multiplicity.")] = 1,
    method: Annotated[str, typer.Option(help="ORCA method keyword.")] = "r2scan-3c",
    basis: Annotated[str, typer.Option(help="ORCA basis keyword.")] = "def2-SVP",
    model: Annotated[
        Path | None,
        typer.Option(help="Path to a MACE model file. Defaults to MACE_MODEL or model_path."),
    ] = None,
    fmax: Annotated[float, typer.Option(help="MACE force convergence threshold in eV/A.")] = 0.05,
    steps: Annotated[int, typer.Option(help="Maximum MACE optimizer steps.")] = 200,
    nprocs: Annotated[int, typer.Option(help="ORCA processor count.")] = 1,
) -> None:
    """Run MACE optimization followed by an ORCA single point."""
    _finish_workflow(
        run_mace_to_orca(
            input_path,
            charge=charge,
            mult=mult,
            method=method,
            basis=basis,
            model=model,
            fmax=fmax,
            steps=steps,
            nprocs=nprocs,
        )
    )


@workflow_app.command("xtb-orca-freq")
def workflow_xtb_orca_freq(
    input_path: InputPath,
    charge: Annotated[int, typer.Option(help="Molecular charge.")] = 0,
    mult: Annotated[int, typer.Option(help="Spin multiplicity.")] = 1,
    method: Annotated[str, typer.Option(help="ORCA method keyword.")] = "r2scan-3c",
    basis: Annotated[str, typer.Option(help="ORCA basis keyword.")] = "def2-SVP",
    uhf: Annotated[int, typer.Option(help="Number of unpaired electrons for xTB.")] = 0,
    nprocs: Annotated[int, typer.Option(help="ORCA processor count.")] = 1,
) -> None:
    """Run xTB optimization followed by an ORCA frequency calculation."""
    _finish_workflow(
        run_xtb_to_orca_freq(
            input_path,
            charge=charge,
            mult=mult,
            method=method,
            basis=basis,
            uhf=uhf,
            nprocs=nprocs,
        )
    )


if __name__ == "__main__":
    app()
