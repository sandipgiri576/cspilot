from __future__ import annotations

from typing import Any

from agents import Agent, Runner
from pydantic import BaseModel, Field

from cspilot.llm import create_agapi_model
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
) -> dict[str, Any]:
    """Generate and validate an explicit allowlisted JSON execution plan."""
    allowed_tools = get_allowed_tools()
    instructions = f"""Produce an execution plan as strict JSON only.
The output schema is {{"steps": [{{"tool": "...", "args": {{}}}}]}}.
Choose only these allowed tools: {allowed_tools}.
Preserve user-provided filenames exactly.
Use defaults when needed: charge=0, mult=1, method="r2scan-3c", basis="def2-SVP".
Prefer run_xtb_orca_workflow for xTB optimization followed by ORCA SP.
Do not add shell commands or unsupported tools."""
    agent = Agent(
        name="cspilot_planner",
        instructions=instructions,
        model=create_agapi_model(model=model, base_url=base_url),
        tools=[],
        output_type=ExecutionPlan,
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
