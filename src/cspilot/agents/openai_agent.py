from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agents import Agent, Runner, ToolCallOutputItem

from cspilot.agents.reporter import make_report
from cspilot.agents.verifier import verify_tool_result
from cspilot.llm import (
    LLMProvider,
    create_llm_model,
    resolve_llm_provider,
    should_fallback_to_openrouter,
)
from cspilot.tools.agent_tools import (
    canonicalize_smiles_tool,
    design_mbh_catalysts_tool,
    find_result_json_agent_tool,
    get_property_from_result_agent_tool,
    inspect_structure,
    molecule_name_to_smiles_tool,
    molecule_name_to_xyz_tool,
    nwpesse_global_minimum_search_tool,
    parse_cluster_formula_tool,
    rdkit_replace_substructure_tool,
    reset_agent_workdir,
    run_mace_optimize,
    run_orca_single_point,
    run_xtb_optimize,
    run_xtb_orca_frequency_workflow,
    run_xtb_orca_workflow,
    set_agent_workdir,
    smiles_to_xyz_tool,
    stk_build_from_smiles_tool,
    stk_building_block_from_file_tool,
    stk_construct_cage_from_smiles_tool,
    stk_export_to_xyz_tool,
    stk_linear_polymer_from_smiles_tool,
    validate_smiles_tool,
)

CHEM_INSTRUCTIONS = """You are a computational chemistry workflow agent.
Use only provided tools.
Do not invent energies, structures, files, catalyst candidates, or calculation results.
Prefer run_xtb_orca_workflow for xTB optimization followed by ORCA SP.
For a new Gibbs free energy or thermochemistry calculation, use run_xtb_orca_frequency_workflow.
If the user provides a molecule name and no XYZ file, use molecule_name_to_xyz_tool.
If the user provides SMILES and no XYZ file, use smiles_to_xyz_tool.
Use stk tools only for molecule construction or editing requests. Use design_mbh_catalysts_tool only for MBH catalyst design requests.
Use nwpesse_global_minimum_search_tool for NWPESSe global-minimum or cluster-search requests, and treat formulas like (h2o)4Mg as fragment clusters, not PubChem molecule names. Use structured box_mode and box_size arguments only; do not write raw mol.inp or optimizer shell.
If the user asks for a property from previous results, use find_result_json and get_property_from_result.
Do not guess property values. If a property name is ambiguous, use aliases first.
If no matching property is found, say it was not found and mention the searched file.
If unsupported, clearly say unsupported."""

MATERIALS_INSTRUCTIONS = """You are a materials science workflow agent.
Use only provided tools for structure inspection and calculations.
You may use AGAPI/JARVIS/materials style reasoning only if supported by available tools or returned information.
Do not invent energies, structures, files, database results, or calculation results.
Prefer run_xtb_orca_workflow for xTB optimization followed by ORCA SP.
For a new Gibbs free energy or thermochemistry calculation, use run_xtb_orca_frequency_workflow.
If the user provides a molecule name and no XYZ file, use molecule_name_to_xyz_tool.
If the user provides SMILES and no XYZ file, use smiles_to_xyz_tool.
Use stk tools only for molecule construction or editing requests. Use design_mbh_catalysts_tool only for MBH catalyst design requests.
Use nwpesse_global_minimum_search_tool for NWPESSe global-minimum or cluster-search requests, and do not use PubChem for fragment generation. Use structured box_mode and box_size arguments only; do not write raw mol.inp or optimizer shell.
If the user asks for a property from previous results, use find_result_json and get_property_from_result.
Do not guess property values. If a property name is ambiguous, use aliases first.
If no matching property is found, say it was not found and mention the searched file.
If a requested materials capability is not available as a tool, clearly say unsupported."""

GENERAL_INSTRUCTIONS = """You are a general scientific search and explanation agent.
Answer general chemistry and materials questions directly using the model's background knowledge.
Do not claim to run calculations, query databases, or create files unless a provided tool actually did so.
If a computational, catalyst-design, or materials database action is requested and no tool is available, clearly say unsupported."""

PROFILE_INSTRUCTIONS = {
    "chem": CHEM_INSTRUCTIONS,
    "materials": MATERIALS_INSTRUCTIONS,
    "general": GENERAL_INSTRUCTIONS,
}


def create_computational_chemistry_agent(
    profile: str = "chem",
    model: str | None = None,
    base_url: str | None = None,
    provider: LLMProvider = "auto",
) -> Agent:
    instructions = _profile_instructions(profile)
    model_obj = create_llm_model(
        provider=provider,
        profile=profile,
        model=model,
        base_url=base_url,
    )
    return Agent(
        name="cspilot",
        instructions=instructions,
        model=model_obj,
        tools=_profile_tools(profile),
    )


async def run_agent_request(
    request: str,
    workdir: Path | str,
    model: str | None = None,
    base_url: str | None = None,
    profile: str = "chem",
    llm_provider: LLMProvider = "auto",
) -> dict[str, Any]:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    token = set_agent_workdir(workdir)
    model_provider = resolve_llm_provider(profile=profile, requested=llm_provider)
    try:
        try:
            result = await Runner.run(
                create_computational_chemistry_agent(
                    profile=profile,
                    model=model,
                    base_url=base_url,
                    provider=model_provider,
                ),
                request,
            )
        except Exception as exc:
            if model_provider != "agapi" or not should_fallback_to_openrouter(exc):
                raise
            model_provider = "openrouter"
            result = await Runner.run(
                create_computational_chemistry_agent(
                    profile=profile,
                    provider="openrouter",
                ),
                request,
            )
        tool_results = _collect_tool_results(result.new_items)
        verification = _verify_results(tool_results, str(workdir))
        report = make_report(request, tool_results, verification)
        payload = {
            "request": request,
            "workdir": str(workdir),
            "agent_profile": profile,
            "model": model,
            "base_url": base_url,
            "model_provider": model_provider,
            "model_output": str(result.final_output),
            "tool_results": tool_results,
            "verification": verification,
            "final_output": report,
        }
        result_path = workdir / "agent_result.json"
        payload["result_path"] = str(result_path)
        result_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload
    finally:
        reset_agent_workdir(token)


def _collect_tool_results(items: list[Any]) -> list[dict[str, Any]]:
    tool_results: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, ToolCallOutputItem):
            continue
        output = item.output
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except json.JSONDecodeError:
                output = {"output": output}
        if not isinstance(output, dict):
            output = {"output": str(output)}
        tool_results.append({"tool_name": _tool_name(item), **output})
    return tool_results


def _tool_name(item: ToolCallOutputItem) -> str:
    origin = item.tool_origin
    if origin is not None:
        name = getattr(origin, "tool_name", None) or getattr(origin, "name", None)
        if name:
            return str(name)
    raw_item = item.raw_item
    if isinstance(raw_item, dict) and raw_item.get("name"):
        return str(raw_item["name"])
    return "tool"


def _verify_results(tool_results: list[dict[str, Any]], workdir: str) -> dict[str, Any]:
    issues: list[str] = []
    for index, tool_result in enumerate(tool_results, start=1):
        verification = verify_tool_result(tool_result, workdir)
        issues.extend(f"Step {index}: {issue}" for issue in verification["issues"])
    return {"verified": not issues, "issues": issues, "workdir": workdir}


def _profile_instructions(profile: str) -> str:
    try:
        return PROFILE_INSTRUCTIONS[profile]
    except KeyError as exc:
        allowed = ", ".join(PROFILE_INSTRUCTIONS)
        raise ValueError(f"Unknown agent profile '{profile}'. Expected one of: {allowed}") from exc


def _profile_tools(profile: str) -> list[Any]:
    if profile == "general":
        return []
    return [
        inspect_structure,
        run_xtb_optimize,
        run_orca_single_point,
        run_mace_optimize,
        run_xtb_orca_workflow,
        run_xtb_orca_frequency_workflow,
        design_mbh_catalysts_tool,
        molecule_name_to_smiles_tool,
        smiles_to_xyz_tool,
        molecule_name_to_xyz_tool,
        validate_smiles_tool,
        canonicalize_smiles_tool,
        parse_cluster_formula_tool,
        nwpesse_global_minimum_search_tool,
        stk_build_from_smiles_tool,
        stk_building_block_from_file_tool,
        stk_linear_polymer_from_smiles_tool,
        stk_construct_cage_from_smiles_tool,
        rdkit_replace_substructure_tool,
        stk_export_to_xyz_tool,
        find_result_json_agent_tool,
        get_property_from_result_agent_tool,
    ]
