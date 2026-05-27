from __future__ import annotations

import sys
from types import ModuleType

from agents import AgentOutputSchema

from cspilot.agents.planner import ExecutionPlan
from cspilot.agents.reporter import generate_report
from cspilot.prompts.system_prompts import get_profile
from cspilot.tools.agapi_materials_tools import agapi_materials_query
from cspilot.tools.registry import (
    get_allowed_tools,
    reset_allowed_profile,
    set_allowed_profile,
)


def test_profile_tools_are_scoped_by_domain():
    assert "run_orca_single_point" in get_allowed_tools("chem")
    assert "agapi_materials_query_tool" not in get_allowed_tools("chem")
    assert get_allowed_tools("materials") == ["agapi_materials_query_tool"]
    assert "get_property_from_result_tool" in get_allowed_tools("analysis")
    assert get_allowed_tools("general") == []
    assert get_allowed_tools("general", "Find materials using JARVIS") == [
        "agapi_materials_query_tool"
    ]


def test_active_profile_constrains_executor_registry():
    token = set_allowed_profile("materials")
    try:
        assert get_allowed_tools() == ["agapi_materials_query_tool"]
    finally:
        reset_allowed_profile(token)


def test_agapi_materials_tool_reports_optional_dependency_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "agapi", None)
    monkeypatch.setitem(sys.modules, "agapi.agents", None)

    result = agapi_materials_query("Find all Al2O3 materials")

    assert result["success"] is False
    assert result["source"] == "AGAPI"
    assert "unavailable" in result["error"]


def test_agapi_materials_tool_delegates_to_prebuilt_agent(monkeypatch):
    calls = {}

    class FakeAgent:
        def __init__(self, api_key):
            calls["api_key"] = api_key

        def query_sync(self, query, render_html=False):
            calls["query"] = query
            calls["render_html"] = render_html
            return "Al2O3 results"

    agapi_agents = ModuleType("agapi.agents")
    agapi_agents.AGAPIAgent = FakeAgent
    monkeypatch.setitem(sys.modules, "agapi.agents", agapi_agents)
    monkeypatch.setenv("AGAPI_API_KEY", "test-key")

    result = agapi_materials_query("Find all Al2O3 materials", render_html=True)

    assert calls == {
        "api_key": "test-key",
        "query": "Find all Al2O3 materials",
        "render_html": True,
    }
    assert result["success"] is True
    assert result["html"] is None
    assert result["text"] == "Al2O3 results"


def test_planner_output_schema_supports_tool_specific_arguments():
    schema = AgentOutputSchema(ExecutionPlan, strict_json_schema=False)

    plan = schema.validate_json(
        '{"steps": [{"tool": "agapi_materials_query_tool", '
        '"args": {"query": "Find all Al2O3 materials", "render_html": true}}]}'
    )

    assert plan.steps[0].args["render_html"] is True


def test_report_records_selected_profile():
    report = generate_report(
        "Search materials",
        {"steps": []},
        {"success": True, "workdir": "runs/test", "steps": []},
        {"verified": True, "issues": []},
        profile="materials",
    )

    assert "Profile: materials" in report
    assert get_profile("materials").default_output_style in report
