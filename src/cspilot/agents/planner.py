from __future__ import annotations

from typing import Any

from agents import Agent, AgentOutputSchema, Runner
from pydantic import BaseModel, Field

from cspilot.llm import create_agapi_model
from cspilot.prompts.system_prompts import get_profile
from cspilot.tools.registry import get_allowed_tools


class PlanStep(BaseModel):
    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    steps: list[PlanStep] = Field(default_factory=list)


async def create_plan(
    user_request: str,
    model: str | None = None,
    base_url: str | None = None,
    profile: str = "chem",
) -> dict[str, Any]:
    """Generate and validate an explicit allowlisted JSON execution plan."""
    selected_profile = get_profile(profile)
    allowed_tools = get_allowed_tools(profile, user_request)
    instructions = f"""{selected_profile.system_prompt}

Produce an execution plan as strict JSON only.
The output schema is {{"steps": [{{"tool": "...", "args": {{}}}}]}}.
Choose only these allowed tools: {allowed_tools}.
Allowed tool groups for this profile: {selected_profile.allowed_tool_groups}.
Default output style: {selected_profile.default_output_style}.
Preserve user-provided filenames exactly.
Use defaults when needed: charge=0, mult=1, method="r2scan-3c", basis="def2-SVP".
Prefer run_xtb_orca_workflow for xTB optimization followed by ORCA SP.
Use nwpesse_global_minimum_search for requests containing "global minimum",
"global minima", "NWPESSe", "cluster search", or "find minimum structure".
Treat formulas such as "(h2o)4Mg" as fragment clusters, not PubChem molecule names.
For NWPESSe, do not use name-to-SMILES or name-to-XYZ tools; use formula/fragments
and ask for fragment_dir when a fragment is unavailable.
Map requested trial/count language to max_calculations and box-size language to box_size.
For NWPESSe per_fragment_type boxes, one unique fragment type gives one inbox line;
multiple unique fragment types give one inbox line per type. If the user asks for
"single box", set box_mode="single". If the user asks for a larger box or gives a
box size, set box_size. Do not write raw mol.inp, box blocks, or optimizer bash.
Only produce structured arguments.
Do not add shell commands or unsupported tools.
If the allowed tools list is empty, return {{"steps": []}}."""
    agent = Agent(
        name="cspilot_planner",
        instructions=instructions,
        model=create_agapi_model(model=model, base_url=base_url),
        tools=[],
        output_type=AgentOutputSchema(ExecutionPlan, strict_json_schema=False),
    )
    result = await Runner.run(agent, user_request)
    plan = (
        result.final_output
        if isinstance(result.final_output, ExecutionPlan)
        else ExecutionPlan.model_validate(result.final_output)
    )
    for step in plan.steps:
        if step.tool not in allowed_tools:
            raise ValueError(f"Planner returned disallowed tool: {step.tool}")
    return plan.model_dump(mode="json")
