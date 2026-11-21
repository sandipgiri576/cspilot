"""Select bounded agent actions and create optional saved execution plans."""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from agents import Agent, AgentOutputSchema, FunctionTool, ModelSettings, Runner
from pydantic import BaseModel, Field, model_validator

from cspilot.llm import create_llm_model
from cspilot.prompts.system_prompts import get_profile
from cspilot.skill_loader import SkillLoader
from cspilot.tools.registry import get_allowed_tools, get_tool_catalog


class AgentDecision(BaseModel):
    """Represent one tool, finish, or blocked action from the planner."""

    action: Literal["tool", "finish", "blocked"]
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_tool_fields(cls, value: Any) -> Any:
        """Normalize provider-specific action fields before validation."""
        if isinstance(value, dict):
            value = dict(value)
            if isinstance(value.get("action"), dict):
                # Some providers wrap the same structured decision twice.
                nested = value["action"]
                if set(nested) <= {"action", "tool", "args", "summary"} and "action" in nested:
                    value = {**value, **nested}
            # A clarification emitted as text must never be treated as completion.
            if (
                "action" not in value
                and "summary" in value
                and not any(key in value for key in ("tool", "name", "arguments", "args"))
            ):
                value["action"] = "blocked"
            # Some OpenAI-compatible models use native function-call field names.
            if "tool" not in value and "name" in value:
                value["tool"] = value.pop("name")
            if "args" not in value and "arguments" in value:
                value["args"] = value.pop("arguments")
            if isinstance(value.get("args"), str):
                value["args"] = json.loads(value["args"])
        return value

    @model_validator(mode="after")
    def validate_action(self) -> AgentDecision:
        """Reject incomplete tools and terminal actions containing tool data."""
        if self.action == "tool" and not self.tool:
            raise ValueError("A tool action requires a tool name.")
        if self.action != "tool" and (self.tool or self.args):
            raise ValueError("Terminal decisions cannot contain a tool call.")
        return self


async def decide_next_action(
    user_request: str,
    observations: list[dict[str, Any]],
    profile: str = "chem",
    workdir: str = ".",
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Choose one action from the request and actual observed tool results."""
    instructions = f"""Select the next action for a scientific agent.
{get_profile(profile).system_prompt}
{SkillLoader().load(profile)}
Select one provided tool, finish, or blocked. Do not emit a fixed multi-step plan.
Finish only when observations support completion of the requested work.
Call finish for a completed task. Never use blocked to report successful completion.
Blocked means missing required input, unavailable capability, or inability to continue.
Unsupported tasks are blocked. Use failures and verification feedback to recover.
Never repeat successful calculations for values already returned.
Your summary describes the action/status, not scientific results.
Use the provided tool schemas. input_xyz aliases are accepted by the executor.
Use simple relative output paths such as molecule.xyz, never $HOME or shell variables.
For calculation inputs copy the exact xyz_path/optimized_xyz from observations.
"""

    async def select_tool(context: Any, arguments: str) -> str:
        return json.dumps(
            {"action": "tool", "tool": context.tool_name, "args": json.loads(arguments)}
        )

    async def finish(context: Any, arguments: str) -> str:
        return json.dumps({"action": context.tool_name, **json.loads(arguments)})

    tools = [
        FunctionTool(
            name=item["name"],
            description=item["description"],
            params_json_schema=item["parameters"],
            on_invoke_tool=select_tool,
        )
        for item in get_tool_catalog(profile, user_request)
    ]
    for name in ("finish", "blocked"):
        # Completion without an observation cannot substantiate a scientific answer.
        if name == "finish" and not observations:
            continue
        tools.append(
            FunctionTool(
                name=name,
                description=(
                    "Finish after observed results satisfy the request."
                    if name == "finish"
                    else "Stop and explain missing molecule/input or unsupported capability."
                ),
                params_json_schema={
                    "type": "object",
                    "properties": {"summary": {"type": "string"}},
                    "required": ["summary"],
                    "additionalProperties": False,
                },
                on_invoke_tool=finish,
            )
        )
    agent = Agent(
        name="cspilot_decision",
        instructions=instructions + "\nCall exactly one provided tool. Do not print JSON as text.",
        model=create_llm_model(model=model, base_url=base_url),
        tools=tools,
        model_settings=ModelSettings(tool_choice="required", parallel_tool_calls=False),
        tool_use_behavior="stop_on_first_tool",
    )
    prompt = json.dumps(
        {
            "request": user_request,
            "workdir": workdir,
            "observations": observations,
        }
    )
    result = await Runner.run(agent, prompt, max_turns=2)
    if not result.final_output:
        result = await Runner.run(
            agent,
            prompt + "\nYour previous response selected no action. Call one tool. "
            "If the molecule or input geometry is missing, call blocked and ask for it.",
            max_turns=2,
        )
    output = result.final_output
    if not output:
        return AgentDecision(
            action="blocked",
            summary="No action was selected by the model. Please provide the molecule "
            "(name, SMILES, or XYZ file) and the calculation you want to run.",
        ).model_dump(mode="json")
    # Some compatible providers ignore required tool_choice and emit only a summary.
    # Ask for an explicit decision once; never infer completion from prose ourselves.
    candidate = json.loads(output) if isinstance(output, str) else output
    if (
        observations
        and isinstance(candidate, dict)
        and not any(key in candidate for key in ("action", "tool", "name"))
    ):

        async def explicit_decision(context: Any, arguments: str) -> str:
            return AgentDecision.model_validate_json(arguments).model_dump_json()

        recovery = Agent(
            name="cspilot_explicit_decision",
            model=create_llm_model(model=model, base_url=base_url),
            instructions=instructions + "\nReturn an explicit AgentDecision object. "
            "Your previous summary lacked an action. Review ALL requested operations against "
            "observations. Choose finish only if complete, tool if work remains, blocked if "
            "required input/capability is missing. A summary alone is not a decision.\n"
            + json.dumps(get_tool_catalog(profile, user_request)),
            tools=[
                FunctionTool(
                    name="submit_decision",
                    description="Return an explicit action, not just a summary.",
                    params_json_schema=AgentDecision.model_json_schema(),
                    on_invoke_tool=explicit_decision,
                    strict_json_schema=False,
                )
            ],
            model_settings=ModelSettings(
                tool_choice="required", parallel_tool_calls=False, max_tokens=2048
            ),
            tool_use_behavior="stop_on_first_tool",
        )
        recovered = await Runner.run(recovery, prompt, max_turns=1)
        output = recovered.final_output
    decision = (
        output
        if isinstance(output, AgentDecision)
        else (
            AgentDecision.model_validate_json(output)
            if isinstance(output, str)
            else AgentDecision.model_validate(output)
        )
    )
    if decision.action == "tool" and decision.tool not in get_allowed_tools(profile, user_request):
        raise ValueError(f"Decision returned disallowed tool: {decision.tool}")
    return decision.model_dump(mode="json")


class PlanStep(BaseModel):
    """Represent one allowlisted tool and its structured arguments."""

    tool: str
    args: dict[str, Any] = Field(default_factory=dict)


class ExecutionPlan(BaseModel):
    """Represent an ordered collection of allowlisted plan steps."""

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

{SkillLoader().load(profile)}

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
    result = await _run_planner_agent(
        user_request,
        instructions,
        create_llm_model(model=model, base_url=base_url),
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
