from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Annotated, Literal

import click
import typer
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

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


class SearchFallbackGroup(TyperGroup):
    def resolve_command(self, ctx: click.Context, args: list[str]):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            if args and (" " in args[0] or "?" in args[0]):
                command = self.commands.get("search")
                if command is not None:
                    return "search", command, args
            raise


app = typer.Typer(cls=SearchFallbackGroup, help="Computational chemistry workflow CLI.")
workflow_app = typer.Typer(help="Multi-step computational chemistry workflows.")
stk_app = typer.Typer(help="stk molecule construction and editing tools.")
greencatai_app = typer.Typer(help="GreenCatAI catalyst-design wrappers.")
app.add_typer(workflow_app, name="workflow")
app.add_typer(stk_app, name="stk")
app.add_typer(greencatai_app, name="greencatai")
console = Console()


InputPath = Annotated[
    Path,
    typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True),
]
Profile = Literal["chem", "materials", "analysis", "thermo", "general"]


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


@app.command("search")
def search_command(
    request: Annotated[str, typer.Argument(help="General natural-language question.")],
    workdir: Annotated[
        Path,
        typer.Option(help="Directory for search result JSON.", resolve_path=True),
    ] = Path("runs/search"),
    model: Annotated[str | None, typer.Option(help="AGAPI model identifier.")] = None,
    base_url: Annotated[str | None, typer.Option(help="OpenAI-compatible AGAPI base URL.")] = None,
) -> None:
    """Answer a general question through the AGAPI-backed general agent."""
    from cspilot.agents.openai_agent import run_agent_request

    try:
        result = asyncio.run(
            run_agent_request(
                request,
                workdir,
                model=model,
                base_url=base_url,
                profile="general",
            )
        )
    except ValueError as exc:
        console.print(f"[red]Configuration error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    console.print(result["model_output"] or result["final_output"])
    console.print(f"Result: {result['result_path']}")


@app.command("docs-check")
def docs_check_command(
    root: Annotated[Path, typer.Option(help="Project root to check.", resolve_path=True)] = Path(),
) -> None:
    """Run lightweight documentation consistency checks."""
    from cspilot.docs_checker import check_documentation_consistency

    result = check_documentation_consistency(root)
    if result["success"]:
        console.print("[green]Documentation consistency check passed.[/]")
    else:
        console.print("[red]Documentation consistency check failed.[/]")
        for issue in result["issues"]:
            console.print(f"- {issue}")
        raise typer.Exit(code=1)


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


@app.command("plan")
def plan_command(
    request: Annotated[str, typer.Argument(help="Natural language workflow request.")],
    workdir: Annotated[
        Path,
        typer.Option(help="Directory in which to save plan.json.", resolve_path=True),
    ] = Path("runs/test"),
    profile: Annotated[Profile, typer.Option(help="Planning tool and prompt profile.")] = "chem",
) -> None:
    """Create a JSON execution plan using the configured AGAPI planner."""
    from cspilot.agents.planner import create_plan

    workdir.mkdir(parents=True, exist_ok=True)
    try:
        plan = asyncio.run(create_plan(request, profile=profile))
    except ValueError as exc:
        console.print(f"[red]Planning error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    plan_path = workdir / "plan.json"
    _write_cli_json(plan_path, plan)
    console.print_json(json=json.dumps(plan))
    console.print(f"Plan: {plan_path}")


@app.command("execute")
def execute_command(
    plan_path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True),
    ],
    workdir: Annotated[
        Path,
        typer.Option(help="Directory in which to save execution outputs.", resolve_path=True),
    ] = Path("runs/test"),
    profile: Annotated[Profile, typer.Option(help="Tool allowlist profile.")] = "chem",
) -> None:
    """Execute an existing JSON plan through allowlisted local tools."""
    from cspilot.agents.executor import execute_plan
    from cspilot.tools.registry import reset_allowed_profile, set_allowed_profile

    workdir.mkdir(parents=True, exist_ok=True)
    profile_token = set_allowed_profile(profile)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        execution_result = execute_plan(plan, str(workdir))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        console.print(f"[red]Execution error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        reset_allowed_profile(profile_token)
    result_path = workdir / "execution_result.json"
    _write_cli_json(result_path, execution_result)
    _print_execution_summary(execution_result, result_path)


@app.command("run")
def run_command(
    request: Annotated[str, typer.Argument(help="Natural language workflow request.")],
    workdir: Annotated[
        Path,
        typer.Option(help="Directory in which to save plan and execution outputs.", resolve_path=True),
    ] = Path("runs/test"),
    profile: Annotated[Profile, typer.Option(help="Planning tool and report profile.")] = "chem",
    html: Annotated[bool, typer.Option(help="Write final_report.html instead of Markdown.")] = False,
) -> None:
    """Plan, execute, verify, and report an allowlisted workflow."""
    from cspilot.agents.executor import execute_plan
    from cspilot.agents.planner import create_plan
    from cspilot.agents.reporter import generate_report
    from cspilot.agents.verifier import verify_execution
    from cspilot.tools.registry import reset_allowed_profile, set_allowed_profile

    workdir.mkdir(parents=True, exist_ok=True)
    profile_token = set_allowed_profile(profile, request)
    try:
        plan = asyncio.run(create_plan(request, profile=profile))
        _write_cli_json(workdir / "plan.json", plan)
        execution_result = execute_plan(plan, str(workdir))
        _write_cli_json(workdir / "execution_result.json", execution_result)
        verification_result = verify_execution(execution_result, str(workdir))
        _write_cli_json(workdir / "verification_result.json", verification_result)
        report = generate_report(
            request,
            plan,
            execution_result,
            verification_result,
            html=html,
            profile=profile,
        )
    except (OSError, ValueError) as exc:
        console.print(f"[red]Run error:[/] {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        reset_allowed_profile(profile_token)

    report_path = workdir / ("final_report.html" if html else "final_report.md")
    report_path.write_text(report, encoding="utf-8")
    _print_execution_summary(execution_result, workdir / "execution_result.json")
    status = "PASSED" if verification_result["verified"] else "FAILED"
    style = "green" if verification_result["verified"] else "red"
    console.print(f"Verification: [{style}]{status}[/]")
    console.print(f"Report: {report_path}")


def _print_tool_json(result: dict[str, object]) -> None:
    console.print_json(json.dumps(result))
    if result.get("success") is False:
        raise typer.Exit(code=1)


def _write_cli_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _print_execution_summary(execution_result: dict[str, object], result_path: Path) -> None:
    success = execution_result.get("success") is True
    status = "COMPLETED" if success else "FAILED OR UNVERIFIED"
    style = "green" if success else "red"
    steps = execution_result.get("steps", [])
    count = len(steps) if isinstance(steps, list) else 0
    console.print(f"[{style}]{status}[/] execution with {count} step(s)")
    console.print(f"Result: {result_path}")


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


@stk_app.command("building-block-smiles")
def stk_building_block_smiles_command(
    smiles: Annotated[str, typer.Argument(help="Input SMILES string.")],
    output_path: Annotated[Path, typer.Argument(help="Output .mol, .sdf, or .xyz file.")],
    functional_groups: Annotated[
        list[str] | None,
        typer.Option("--functional-group", "-f", help="Safe functional group name to detect."),
    ] = None,
) -> None:
    """Create an stk building block from SMILES."""
    from cspilot.tools.stk_tools import stk_building_block_from_smiles

    _print_tool_json(
        stk_building_block_from_smiles(
            smiles=smiles,
            output_path=str(output_path),
            functional_groups=functional_groups,
        )
    )


@stk_app.command("building-block-file")
def stk_building_block_file_command(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True),
    ],
    output_path: Annotated[Path | None, typer.Option(help="Optional output copy/export path.")] = None,
) -> None:
    """Load an stk building block from a molecule file."""
    from cspilot.tools.stk_tools import stk_building_block_from_file

    _print_tool_json(stk_building_block_from_file(str(input_path), str(output_path) if output_path else None))


@stk_app.command("linear-polymer")
def stk_linear_polymer_command(
    monomer_smiles: Annotated[str, typer.Argument(help="Monomer building-block SMILES.")],
    repeating_unit: Annotated[str, typer.Argument(help="stk repeating unit string.")],
    num_repeating_units: Annotated[int, typer.Argument(help="Number of repeating units.")],
    output_path: Annotated[Path, typer.Argument(help="Output .mol, .sdf, or .xyz file.")],
) -> None:
    """Construct a linear polymer with stk.polymer.Linear."""
    from cspilot.tools.stk_tools import stk_construct_linear_polymer

    _print_tool_json(
        stk_construct_linear_polymer(
            monomer_smiles=monomer_smiles,
            repeating_unit=repeating_unit,
            num_repeating_units=num_repeating_units,
            output_path=str(output_path),
        )
    )


@stk_app.command("simple-cage")
def stk_simple_cage_command(
    output_path: Annotated[Path, typer.Argument(help="Output .mol, .sdf, or .xyz file.")],
    building_block_smiles: Annotated[
        list[str],
        typer.Option("--building-block", "-b", help="Building-block SMILES. Repeat option."),
    ],
    topology: Annotated[str, typer.Option(help="Whitelisted topology name.")] = "four_plus_six",
) -> None:
    """Construct a simple cage from a small topology whitelist."""
    from cspilot.tools.stk_tools import stk_construct_simple_cage

    _print_tool_json(
        stk_construct_simple_cage(
            building_block_smiles=building_block_smiles,
            topology=topology,
            output_path=str(output_path),
        )
    )


@stk_app.command("replace-smiles")
def stk_replace_smiles_command(
    parent_smiles: Annotated[str, typer.Argument(help="Parent molecule SMILES.")],
    old_substructure: Annotated[str, typer.Argument(help="Substructure SMILES/SMARTS to replace.")],
    new_substructure: Annotated[str, typer.Argument(help="Replacement SMILES.")],
    output_path: Annotated[Path, typer.Argument(help="Output .mol, .sdf, or .xyz file.")],
) -> None:
    """Replace a SMILES substructure and export the edited molecule."""
    from cspilot.tools.stk_tools import stk_edit_replace_smiles

    _print_tool_json(
        stk_edit_replace_smiles(
            parent_smiles=parent_smiles,
            old_substructure=old_substructure,
            new_substructure=new_substructure,
            output_path=str(output_path),
        )
    )


@stk_app.command("export-xyz")
def stk_export_xyz_command(
    input_path: Annotated[
        Path,
        typer.Argument(exists=True, file_okay=True, dir_okay=False, readable=True, resolve_path=True),
    ],
    output_path: Annotated[Path, typer.Argument(help="Output XYZ path.")],
) -> None:
    """Export a molecule file to XYZ using stk/RDKit fallback."""
    from cspilot.tools.stk_tools import stk_export_to_xyz

    _print_tool_json(stk_export_to_xyz(str(input_path), str(output_path)))


@greencatai_app.command("design-mbh")
def greencatai_design_mbh_command(
    output_dir: Annotated[Path, typer.Option(help="Output directory for GreenCatAI artifacts.")] = Path("runs/mbh_api"),
    search_space: Annotated[Path, typer.Option(help="GreenCatAI search-space JSON.")] = Path("configs/search_space.json"),
    scoring: Annotated[Path, typer.Option(help="GreenCatAI scoring JSON.")] = Path("configs/scoring.json"),
    library: Annotated[Path | None, typer.Option(help="Optional validated amine library JSON.")] = None,
    max_candidates: Annotated[int, typer.Option(help="Maximum seed candidates to generate.")] = 100,
    generations: Annotated[int, typer.Option(help="Number of GA generations.")] = 3,
    population_size: Annotated[int, typer.Option(help="Candidate population size.")] = 30,
    top_n_xtb: Annotated[int, typer.Option(help="Number of top candidates for xTB screening.")] = 0,
    top_n_orca: Annotated[int, typer.Option(help="Number of top candidates for ORCA screening.")] = 0,
) -> None:
    """Run the stable GreenCatAI MBH design API."""
    from cspilot.tools.greencatai_tools import greencatai_design_mbh_catalysts

    _print_tool_json(
        greencatai_design_mbh_catalysts(
            output_dir=str(output_dir),
            search_space=str(search_space),
            scoring=str(scoring),
            library=str(library) if library else None,
            max_candidates=max_candidates,
            generations=generations,
            population_size=population_size,
            top_n_xtb=top_n_xtb,
            top_n_orca=top_n_orca,
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
