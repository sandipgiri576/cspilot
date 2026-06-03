from __future__ import annotations

from pathlib import Path

from cspilot.agents.router import route_request
from cspilot.graph import build_graph, run_graph_agent


def test_route_request_stk():
    result = route_request("construct an stk cage topology from building blocks")

    assert result["specialist"] == "stk"
    assert "stk" in result["allowed_tool_groups"]


def test_route_request_chem():
    result = route_request("run an ORCA single point after xTB optimize")

    assert result["specialist"] == "chem"
    assert "chemistry" in result["allowed_tool_groups"]


def test_route_request_materials():
    result = route_request("Find all Al2O3 materials in JARVIS")

    assert result["specialist"] == "materials"
    assert "materials" in result["allowed_tool_groups"]


def test_route_request_explicit_profile():
    result = route_request("optimize benzene", profile="analysis")

    assert result["success"] is True
    assert result["specialist"] == "analysis"
    assert result["reason"] == "Explicit profile 'analysis' was requested."


def test_route_request_analysis_gibbs():
    result = route_request("extract Gibbs from result JSON")

    assert result["specialist"] == "analysis"


def test_build_graph_modes_compile():
    build_graph(agent_mode="single")
    build_graph(agent_mode="multi")


def test_run_graph_agent_single_mode_does_not_call_router(monkeypatch, tmp_path):
    def fail_router(*args, **kwargs):
        raise AssertionError("router should not be called in single mode")

    _mock_graph_dependencies(monkeypatch, {"steps": []})
    monkeypatch.setattr("cspilot.graph.route_request", fail_router)

    state = run_graph_agent("inspect water.xyz", tmp_path, profile="chem", agent_mode="single")

    assert state["profile"] == "chem"
    assert state["route"] is None
    assert state["final_report"] == "ok report"


def test_run_graph_agent_multi_mode_calls_router(monkeypatch, tmp_path):
    called = {"router": False}

    def fake_router(user_request, profile="auto"):
        called["router"] = True
        return {
            "success": True,
            "specialist": "stk",
            "reason": "mock route",
            "allowed_tool_groups": ["stk"],
        }

    _mock_graph_dependencies(monkeypatch, {"steps": []})
    monkeypatch.setattr("cspilot.graph.route_request", fake_router)

    state = run_graph_agent("construct an stk polymer", tmp_path, profile="auto", agent_mode="multi")

    assert called["router"] is True
    assert state["profile"] == "stk"
    assert state["route"]["specialist"] == "stk"


def test_run_graph_agent_single_inspect_water_plan(monkeypatch, tmp_path):
    water = tmp_path / "water.xyz"
    water.write_text("3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n", encoding="utf-8")
    plan = {"steps": [{"tool": "inspect_structure", "args": {"xyz_path": str(water)}}]}

    _mock_graph_dependencies(monkeypatch, plan)

    state = run_graph_agent(f"inspect {water}", tmp_path / "run", profile="chem", agent_mode="single")

    assert state["plan"] == plan
    assert state["execution_result"]["success"] is True
    assert state["verification_result"]["verified"] is True


def test_run_graph_agent_invalid_agent_mode_returns_failure(tmp_path):
    state = run_graph_agent("inspect water.xyz", tmp_path, profile="chem", agent_mode="bad")

    assert state["execution_result"]["success"] is False
    assert "Unknown agent_mode" in state["errors"][0]
    assert state["final_report"]


def test_cli_graph_run_saves_state_on_internal_failure(monkeypatch, tmp_path):
    from typer.testing import CliRunner

    from cspilot.cli import app

    def fake_run_graph_agent(**kwargs):
        return {
            "user_request": kwargs["user_request"],
            "workdir": str(kwargs["workdir"]),
            "profile": kwargs["profile"],
            "agent_mode": kwargs["agent_mode"],
            "html": kwargs["html"],
            "max_retries": kwargs["max_retries"],
            "retry_count": 0,
            "route": None,
            "plan": None,
            "execution_result": {"success": False, "steps": [], "error": "mock"},
            "verification_result": None,
            "final_report": "mock failure report",
            "errors": ["mock"],
        }

    monkeypatch.setattr("cspilot.graph.run_graph_agent", fake_run_graph_agent)
    result = CliRunner().invoke(
        app,
        ["graph-run", "request", "--workdir", str(tmp_path), "--profile", "chem", "--agent-mode", "single"],
    )

    assert result.exit_code == 0
    assert (tmp_path / "final_state.json").exists()
    assert (tmp_path / "final_report.md").exists()


def _mock_graph_dependencies(monkeypatch, plan: dict):
    monkeypatch.setattr("cspilot.graph.create_plan", lambda *args, **kwargs: plan)
    monkeypatch.setattr(
        "cspilot.graph.execute_plan",
        lambda plan, workdir: {
            "success": True,
            "workdir": str(Path(workdir)),
            "steps": [{"success": True, "tool_name": "mock"}],
        },
    )
    monkeypatch.setattr(
        "cspilot.graph.verify_execution",
        lambda execution_result, workdir: {"verified": True, "issues": []},
    )
    monkeypatch.setattr(
        "cspilot.graph.generate_report",
        lambda *args, **kwargs: "ok report",
    )
