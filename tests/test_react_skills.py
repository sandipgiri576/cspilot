from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from cspilot.agents import planner
from cspilot.cli import app
from cspilot.graph import run_graph_agent
from cspilot.skill_loader import SkillLoader


def test_skills_load_roles_and_new_domain(tmp_path):
    (tmp_path / "common.md").write_text("## Planner\nShared rule\n## Reporter\n- field: value\n")
    (tmp_path / "custom.md").write_text("## Planner\nCustom rule\n## Reporter\n- field: charge\n")
    loader = SkillLoader(tmp_path)
    assert loader.load("custom") == "Shared rule\n\nCustom rule"
    assert loader.report_fields("custom") == {"value", "charge"}
    assert loader.load("missing") == "Shared rule"
    with pytest.raises(ValueError):
        loader.load("../custom")


def test_decision_prompt_contains_skill_and_observations(monkeypatch):
    async def run(agent, prompt, **kwargs):
        assert "For a NEW Gibbs free energy" in agent.instructions
        assert json.loads(prompt)["observations"][0]["result"]["value"] == -12.5
        names = {tool.name for tool in agent.tools}
        assert "get_property_from_result_tool" in names
        assert "run_orca_single_point" not in names
        return SimpleNamespace(final_output={"action": "finish"})

    monkeypatch.setattr(planner, "create_llm_model", lambda **kw: "mock")
    monkeypatch.setattr(planner.Runner, "run", run)
    result = asyncio.run(
        planner.decide_next_action(
            "print Gibbs",
            [{"result": {"value": -12.5}}],
            profile="thermo",
        )
    )
    assert result["action"] == "finish"


def test_next_action_uses_returned_path(monkeypatch, tmp_path):
    xyz = tmp_path / "actual.xyz"
    xyz.write_text("1\nH\nH 0 0 0\n")

    async def decide(request, observations, **kwargs):
        if not observations:
            return {"action": "tool", "tool": "inspect_structure", "args": {"input_xyz": str(xyz)}}
        result = observations[0]["result"]
        assert result["structure"]["natoms"] == 1
        assert observations[0]["verification"]["verified"]
        return {"action": "finish"}

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    state = run_graph_agent("inspect hydrogen", tmp_path / "run")
    assert state["verification_result"]["verified"]
    assert len(state["observations"]) == 1
    for name in (
        "observations.json",
        "decision_001.json",
        "decision_002.json",
        "step_001_result.json",
        "final_state.json",
        "verification_result.json",
    ):
        json.loads((tmp_path / "run" / name).read_text())


def test_dynamic_two_step_file_handoff(monkeypatch, tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text('{"custom_property": 42.5}')

    async def decide(request, observations, **kwargs):
        if not observations:
            return {
                "action": "tool",
                "tool": "find_result_json_tool",
                "args": {"workdir": str(tmp_path)},
            }
        if len(observations) == 1:
            return {
                "action": "tool",
                "tool": "get_property_from_result_tool",
                "args": {
                    "path": observations[0]["result"]["path"],
                    "property_name": "custom_property",
                },
            }
        assert observations[-1]["result"]["value"] == 42.5
        return {"action": "finish"}

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    state = run_graph_agent("print custom_property", tmp_path / "agent", profile="analysis")
    assert len(state["observations"]) == 2
    assert state["verification_result"]["verified"]
    assert "42.5" in state["final_report"]


@pytest.mark.parametrize("mode", ["limit", "blocked", "disallowed", "model_error"])
def test_loop_terminates_and_keeps_artifacts(monkeypatch, tmp_path, mode):
    async def decide(*args, **kwargs):
        if mode == "blocked":
            return {"action": "blocked", "summary": "No supported tool."}
        if mode == "model_error":
            raise RuntimeError("backend unavailable")
        return {
            "action": "tool",
            "tool": "run_shell" if mode == "disallowed" else "inspect_structure",
            "args": {"input_xyz": "missing.xyz"},
        }

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    state = run_graph_agent("request", tmp_path, max_steps=2, max_retries=0)
    assert not state["verification_result"]["verified"]
    assert len(state["observations"]) <= 1
    assert (tmp_path / "final_state.json").is_file()
    assert (tmp_path / "final_report.md").is_file()


def test_failure_feedback_can_change_action(monkeypatch, tmp_path):
    xyz = tmp_path / "present.xyz"
    xyz.write_text("1\nH\nH 0 0 0\n")

    async def decide(request, observations, **kwargs):
        if len(observations) == 2:
            return {"action": "finish"}
        if observations:
            assert not observations[-1]["verification"]["verified"]
        return {
            "action": "tool",
            "tool": "inspect_structure",
            "args": {"input_xyz": str(xyz) if observations else "missing.xyz"},
        }

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    state = run_graph_agent("inspect", tmp_path / "run")
    assert len(state["observations"]) == 2
    assert state["observations"][-1]["verification"]["verified"]
    # Preserve failed attempts in the conservative overall verification.
    assert not state["verification_result"]["verified"]
    assert "Step 1" in state["final_report"]


def test_successful_calls_cannot_exceed_step_limit(monkeypatch, tmp_path):
    xyz = tmp_path / "input.xyz"
    xyz.write_text("1\nH\nH 0 0 0\n")

    async def decide(*args, **kwargs):
        return {"action": "tool", "tool": "inspect_structure", "args": {"input_xyz": str(xyz)}}

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    state = run_graph_agent("inspect", tmp_path / "run", max_steps=2)
    assert state["stop_reason"] == "max_steps"
    assert len(state["observations"]) == 2
    assert state["retry_count"] == 0
    assert not state["verification_result"]["verified"]


@pytest.mark.parametrize("flags", [[], ["--no-pretty"], ["--html"], ["--html", "--no-pretty"]])
def test_cli_displays_stored_value_and_saves_json(monkeypatch, tmp_path, flags):
    source = tmp_path / "result.json"
    source.write_text('{"custom": 123.45}')

    async def decide(request, observations, **kwargs):
        return (
            {"action": "finish"}
            if observations
            else {
                "action": "tool",
                "tool": "get_property_from_result_tool",
                "args": {"path": str(source), "property_name": "custom"},
            }
        )

    monkeypatch.setattr("cspilot.graph.decide_next_action", decide)
    run = tmp_path / "run"
    result = CliRunner().invoke(
        app,
        [
            "run",
            "print custom on screen",
            "--profile",
            "analysis",
            "--workdir",
            str(run),
            *flags,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "123.45" in result.output
    assert (run / "final_state.json").is_file()
