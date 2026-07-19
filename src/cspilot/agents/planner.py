from __future__ import annotations

import json
import re
from typing import Any

from agents import Agent, AgentOutputSchema, Runner
from pydantic import BaseModel, Field

from cspilot.llm import (
    LLMProvider,
    create_llm_model,
    create_openrouter_model,
    resolve_llm_provider,
    should_fallback_to_openrouter,
)
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
    llm_provider: LLMProvider = "auto",
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
For molecule generation followed by xTB/ORCA, prefer stk_to_xtb_orca if that
exact tool is present in the allowed tools list. If it is not present and you
use stk_build_from_smiles_tool followed by run_xtb_orca_workflow, always give
stk_build_from_smiles_tool an output_path ending in .xyz, then pass the exact
same filename to run_xtb_orca_workflow as input_xyz in the next step.
Use canonical argument names: input_xyz for input structures and output_path
for generated files. Do not use input_file, xyz_file, file, or output_file.
Do not include workdir in step args unless a listed tool explicitly requires it;
the executor supplies the workdir. Do not invent filenames unless needed. If a
filename is required and the user did not provide one, use a safe simple name
from the molecule when obvious, such as benzene.xyz or caffeine.xyz; otherwise
use stk_molecule.xyz.
Before any step that uses input_xyz, ensure that the referenced file either
already exists because the user provided that exact filename, or is created by
an earlier step in the plan. Never start a plan with run_xtb_optimize,
run_orca_single_point, run_xtb_orca_workflow, inspect_structure, or
run_mace_optimize on a guessed filename such as benzene.xyz. If the user asks
to optimize or calculate a molecule by name and no XYZ file is provided, first
use molecule_name_to_xyz_tool with output_path set to the later input_xyz. If
the user provides SMILES and no XYZ file, first use smiles_to_xyz_tool. If the
user requested stk construction, first use an stk construction tool with an XYZ
output_path and pass that same path to later calculation steps.
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
    selected_provider = resolve_llm_provider(profile=profile, requested=llm_provider)
    try:
        result = await _run_planner_agent(
            user_request,
            instructions,
            create_llm_model(
                provider=selected_provider,
                profile=profile,
                model=model,
                base_url=base_url,
            ),
        )
    except Exception as exc:
        if selected_provider != "agapi" or not should_fallback_to_openrouter(exc):
            raise
        result = await _run_planner_agent(
            user_request,
            instructions,
            create_openrouter_model(),
        )
    plan = _coerce_execution_plan(result.final_output)
    plan = _sanitize_plan(plan)
    for step in plan.steps:
        if step.tool not in allowed_tools:
            raise ValueError(f"Planner returned disallowed tool: {step.tool}")
    return plan.model_dump(mode="json")


def _sanitize_plan(plan: ExecutionPlan) -> ExecutionPlan:
    cleaned_steps: list[PlanStep] = []
    saw_combined_xtb_orca = False
    for step in plan.steps:
        args = dict(step.args)
        if "input_smiles" in args and "smiles" not in args:
            args["smiles"] = args.pop("input_smiles")
        if "smiles_string" in args and "smiles" not in args:
            args["smiles"] = args.pop("smiles_string")
        if step.tool == "run_xtb_orca_workflow":
            saw_combined_xtb_orca = True
        if saw_combined_xtb_orca and step.tool == "run_orca_single_point":
            continue
        cleaned_steps.append(PlanStep(tool=step.tool, args=args))
    return ExecutionPlan(steps=cleaned_steps)


def _coerce_execution_plan(output: Any) -> ExecutionPlan:
    if isinstance(output, ExecutionPlan):
        return output
    if isinstance(output, str):
        cleaned = _strip_json_fence(output)
        try:
            return ExecutionPlan.model_validate_json(cleaned)
        except ValueError:
            return ExecutionPlan.model_validate(json.loads(cleaned))
    return ExecutionPlan.model_validate(output)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1).strip()
    return stripped


async def _run_planner_agent(
    user_request: str,
    instructions: str,
    model: Any,
) -> Any:
    agent = Agent(
        name="cspilot_planner",
        instructions=instructions,
        model=model,
        tools=[],
        output_type=AgentOutputSchema(ExecutionPlan, strict_json_schema=False),
    )
    return await Runner.run(agent, user_request)
