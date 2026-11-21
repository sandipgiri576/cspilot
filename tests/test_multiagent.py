"""Fast offline coverage of decomposition, isolated loops and scientific aggregation."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from cspilot.agents.decomposer import Decomposition, Subtask
from cspilot.multiagent import run_multiagent
from cspilot.tools.aggregation import HARTREE_TO_KJ_MOL, aggregate_results, validate_species


def reaction_fixture(tmp_path):
    from ase import Atoms
    from ase.io import write

    tasks = [
        Subtask(id="methane", request="thermo", smiles="C", role="reactant"),
        Subtask(
            id="oxygen", request="thermo", smiles="[O][O]", mult=3, coefficient=2, role="reactant"
        ),
        Subtask(id="carbon_dioxide", request="thermo", smiles="O=C=O", role="product"),
        Subtask(id="water", request="thermo", smiles="O", coefficient=2, role="product"),
    ]
    plan = Decomposition(kind="reaction", subtasks=tasks).model_dump()
    summaries = []
    for task, symbols, value in zip(
        tasks, ["CH4", "O2", "CO2", "H2O"], [-40.0, -150.0, -188.0, -76.1], strict=True
    ):
        xyz = tmp_path / f"{task.id}.xyz"
        write(xyz, Atoms(symbols))
        out = tmp_path / f"{task.id}.out"
        out.write_text("mock ORCA output")
        record = {
            "task": "opt_freq",
            "status": "ok",
            "parameters": {
                "method": "r2scan-3c",
                "basis": "method-defined",
                "charge": task.charge,
                "mult": task.mult,
            },
            "files": {"optimized_xyz": str(xyz), "output": str(out)},
            "result": {
                "properties": {
                    "enthalpy": value,
                    "gibbs_free_energy": value - 0.01,
                    "energy_unit": "Eh",
                    "geometry_optimization_converged": True,
                    "frequencies": [100.0, 200.0],
                    "imaginary_frequency_count": 0,
                    "temperature_kelvin": 298.15,
                    "pressure_atm": 1.0,
                }
            },
        }
        summaries.append({"id": task.id, "verified": True, "execution_result": {"steps": [record]}})
    return plan, summaries


def test_stoichiometric_enthalpy_is_general_not_model_arithmetic(tmp_path):
    plan, summaries = reaction_fixture(tmp_path)
    result = aggregate_results(plan, summaries)
    assert result["success"], result
    assert result["reaction_energy_hartree"] == pytest.approx(-0.2)
    assert result["reaction_energy_kj_mol"] == pytest.approx(-0.2 * HARTREE_TO_KJ_MOL)
    # Scale every coefficient: per-equation reaction energy must scale too.
    for task in plan["subtasks"]:
        task["coefficient"] *= 0.5
    assert aggregate_results(plan, summaries)["reaction_energy_hartree"] == pytest.approx(-0.1)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "spin",
        "balance",
        "units",
        "temperature",
        "frequency",
        "method",
        "geometry",
        "nonfinite",
    ],
)
def test_reaction_refuses_incomplete_or_incompatible_data(tmp_path, mutation):
    plan, summaries = reaction_fixture(tmp_path)
    record = summaries[0]["execution_result"]["steps"][0]
    props = record["result"]["properties"]
    if mutation == "missing":
        summaries[-1]["verified"] = False
    elif mutation == "spin":
        plan["subtasks"][1]["mult"] = 1
    elif mutation == "balance":
        plan["subtasks"][-1]["coefficient"] = 1
    elif mutation == "units":
        props["energy_unit"] = "eV"
    elif mutation == "temperature":
        props["temperature_kelvin"] = 300
    elif mutation == "frequency":
        record["task"] = "sp"
    elif mutation == "method":
        record["parameters"]["method"] = "b3lyp"
    elif mutation == "geometry":
        record["files"]["optimized_xyz"] = summaries[-1]["execution_result"]["steps"][0]["files"][
            "optimized_xyz"
        ]
    else:
        props["enthalpy"] = float("nan")
    result = aggregate_results(plan, summaries)
    assert result["success"] is False
    assert "reaction_energy_hartree" not in result


def test_invalid_decomposition_is_rejected():
    with pytest.raises(ValidationError):
        Subtask(id="../escape", request="inspect")
    with pytest.raises(ValidationError):
        Decomposition(subtasks=[Subtask(id="water", request="inspect")] * 2)
    with pytest.raises(ValidationError):
        Decomposition(method="r2scan-3c\n%pal nprocs 99 end")
    with pytest.raises(ValidationError):
        Decomposition(kind="conformers", subtasks=[Subtask(id="water", request="compare")])


def test_native_decomposition_repairs_invalid_schema_once(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from cspilot.agents import decomposer

    calls = []
    plan = Decomposition(subtasks=[Subtask(id="water", request="Inspect water")])

    async def run(agent, prompt, **kwargs):
        calls.append(prompt)
        tool = agent.tools[0]
        assert tool.name == "submit_decomposition"
        assert "subtasks" in tool.params_json_schema["required"]
        if len(calls) == 1:
            raise ValueError("wrong fields")
        output = await tool.on_invoke_tool(None, plan.model_dump_json())
        return SimpleNamespace(final_output=output)

    monkeypatch.setattr(decomposer, "create_llm_model", lambda **kwargs: "mock")
    monkeypatch.setattr(decomposer.Runner, "run", run)
    result = asyncio.run(decomposer.decompose_request("inspect water"))
    assert result.subtasks[0].id == "water"
    assert len(calls) == 2 and "wrong fields" in calls[1]


@pytest.mark.parametrize("workers", [1, 2])
def test_isolated_child_loops_and_json_artifacts(tmp_path, monkeypatch, workers):
    from cspilot import graph, multiagent

    async def decompose(*args):
        return Decomposition(
            subtasks=[Subtask(id=name, request="inspect water") for name in ("water_a", "water_b")]
        )

    async def decide(request, observations, **kwargs):
        if observations:
            return {"action": "finish", "summary": "Observed water"}
        return {
            "action": "tool",
            "tool": "inspect_structure",
            "args": {"xyz_path": str(Path("tests/examples/input.xyz").resolve())},
        }

    monkeypatch.setattr(multiagent, "decompose_request", decompose)
    monkeypatch.setattr(graph, "decide_next_action", decide)
    result = run_multiagent("Inspect two supplied waters", tmp_path, workers=workers)
    assert result["verification_result"]["verified"], result
    for name in ("water_a", "water_b"):
        root = tmp_path / "subtasks" / name
        state = json.loads((root / "final_state.json").read_text())
        assert len(state["observations"]) == 1
        assert state["workdir"] == str(root)
        assert (root / "summary.json").is_file()
    for filename in (
        "decomposition.json",
        "summaries.json",
        "aggregate.json",
        "verification_result.json",
        "final_report.md",
    ):
        assert (tmp_path / filename).is_file()


def test_unbalanced_reaction_never_launches_children(tmp_path, monkeypatch):
    from cspilot import multiagent

    plan, _ = reaction_fixture(tmp_path)
    plan["subtasks"][-1]["coefficient"] = 1

    async def decompose(*args):
        return Decomposition.model_validate(plan)

    monkeypatch.setattr(multiagent, "decompose_request", decompose)
    monkeypatch.setattr(multiagent, "_run_child", lambda *args: pytest.fail("must not launch"))
    result = run_multiagent("unbalanced reaction", tmp_path)
    assert not result["verification_result"]["verified"]
    assert "balanced" in result["final_report"]


def test_reaction_does_not_treat_invented_output_as_user_input(tmp_path, monkeypatch):
    from cspilot import multiagent

    plan, _ = reaction_fixture(tmp_path)
    plan["subtasks"][0]["input_xyz"] = "not_supplied.xyz"

    async def decompose(*args):
        return Decomposition.model_validate(plan)

    monkeypatch.setattr(multiagent, "decompose_request", decompose)
    state = {"workdir": str(tmp_path), "user_request": "Calculate reaction enthalpy from SMILES"}
    result = multiagent.decompose_node(state)
    assert result["decomposition"]["subtasks"][0]["input_xyz"] is None
    state["user_request"] += " using not_supplied.xyz"
    assert "errors" in multiagent.decompose_node(state)


def test_conformer_comparison_requires_same_species(tmp_path):
    plan, summaries = reaction_fixture(tmp_path)
    water = plan["subtasks"][-1]
    water["input_xyz"] = str(tmp_path / "water.xyz")
    plan.update(kind="conformers", subtasks=[water, {**water, "id": "water_b"}])
    second_xyz = tmp_path / "water_b.xyz"
    second_xyz.write_text((tmp_path / "water.xyz").read_text())
    plan["subtasks"][1]["input_xyz"] = str(second_xyz)
    second = copy.deepcopy(summaries[-1])
    second["id"] = "water_b"
    second["execution_result"]["steps"][0]["result"]["properties"]["enthalpy"] += 0.001
    result = aggregate_results(plan, [summaries[-1], second])
    assert result["success"]
    assert result["relative_energies_kj_mol"]["water_b"] == pytest.approx(0.001 * HARTREE_TO_KJ_MOL)
    plan["subtasks"][0]["smiles"] = "invalid"
    with pytest.raises(ValueError):
        validate_species(plan)


def test_cli_multiagent_flag_and_labeled_screen_report(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from cspilot import graph
    from cspilot.cli import app

    calls = []

    def run(**kwargs):
        calls.append(kwargs)
        return {
            "final_report": "water report",
            "verification_result": {"verified": True},
            "execution_result": {
                "steps": [
                    {
                        "tool": "aggregate_subtasks",
                        "species_results": [
                            {
                                "id": "water",
                                "results": [{"property": "formula", "value": "H2O"}],
                                "summary_file": "water/summary.json",
                            }
                        ],
                    }
                ]
            },
        }

    monkeypatch.setattr(graph, "run_graph_agent", run)
    result = CliRunner().invoke(
        app,
        [
            "run",
            "inspect water",
            "--multiagent",
            "--workers",
            "2",
            "--no-pretty",
            "--workdir",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls[0]["multiagent"] is True and calls[0]["workers"] == 2
    assert "Subtask: water" in result.output and "H2O" in result.output


def test_single_agent_remains_default(monkeypatch, tmp_path):
    from cspilot import graph, multiagent

    monkeypatch.setattr(multiagent, "run_multiagent", lambda *a, **k: pytest.fail("not opted in"))

    async def decide(*a, **k):
        return {"action": "blocked", "summary": "Missing geometry"}

    monkeypatch.setattr(graph, "decide_next_action", decide)
    assert graph.run_graph_agent("inspect", tmp_path)["agent_mode"] == "single"


def test_child_cannot_overwrite_sibling_output(tmp_path):
    from cspilot.tools.registry import call_tool

    sibling = tmp_path / "sibling.xyz"
    sibling.write_text("existing user data")
    result = call_tool(
        "smiles_to_xyz_tool",
        {"smiles": "O", "output_path": str(sibling)},
        str(tmp_path / "child"),
        confine_outputs=True,
    )
    assert result["success"] is False
    assert "inside" in result["error"]
    assert sibling.read_text() == "existing user data"
