from __future__ import annotations

from agents import AgentOutputSchema

from cspilot.agents.planner import ExecutionPlan
from cspilot.agents.reporter import generate_report
from cspilot.prompts.system_prompts import get_profile
from cspilot.tools.registry import (
    get_allowed_tools,
    reset_allowed_profile,
    set_allowed_profile,
)


def test_profile_tools_are_scoped_by_domain():
    assert "run_orca_single_point" in get_allowed_tools("chem")
    assert get_allowed_tools("materials") == []
    assert "get_property_from_result_tool" in get_allowed_tools("analysis")
    assert get_allowed_tools("general") == []
    assert get_allowed_tools("general", "Find materials catalysts") == []


def test_active_profile_constrains_executor_registry():
    token = set_allowed_profile("materials")
    try:
        assert get_allowed_tools() == []
    finally:
        reset_allowed_profile(token)


def test_planner_output_schema_supports_tool_specific_arguments():
    schema = AgentOutputSchema(ExecutionPlan, strict_json_schema=False)

    plan = schema.validate_json(
        '{"steps": [{"tool": "smiles_to_xyz_tool", '
        '"args": {"smiles": "C=O", "output_path": "molecule.xyz"}}]}'
    )

    assert plan.steps[0].args["smiles"] == "C=O"


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
