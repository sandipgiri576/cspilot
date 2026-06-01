from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar, Token
from pathlib import Path
from typing import Any

from agents.tool_context import ToolContext

from cspilot.prompts.system_prompts import allowed_group_names
from cspilot.tools.agent_tools import (
    agapi_materials_query_tool,
    design_mbh_catalysts_tool,
    find_result_json_tool,
    get_property_from_result_tool,
    inspect_structure,
    rdkit_replace_substructure_tool,
    reset_agent_workdir,
    run_mace_optimize,
    run_orca_single_point,
    run_xtb_optimize,
    run_xtb_orca_workflow,
    set_agent_workdir,
    stk_build_from_smiles_tool,
    stk_building_block_from_file_tool,
    stk_construct_cage_from_smiles_tool,
    stk_export_to_xyz_tool,
    stk_linear_polymer_from_smiles_tool,
)

_TOOL_GROUPS = {
    "chemistry": [
        inspect_structure,
        run_xtb_optimize,
        run_orca_single_point,
        run_mace_optimize,
        run_xtb_orca_workflow,
        stk_build_from_smiles_tool,
        stk_building_block_from_file_tool,
        stk_linear_polymer_from_smiles_tool,
        stk_construct_cage_from_smiles_tool,
        rdkit_replace_substructure_tool,
        stk_export_to_xyz_tool,
        design_mbh_catalysts_tool,
    ],
    "materials": [agapi_materials_query_tool, design_mbh_catalysts_tool],
    "stk": [
        stk_build_from_smiles_tool,
        stk_building_block_from_file_tool,
        stk_linear_polymer_from_smiles_tool,
        stk_construct_cage_from_smiles_tool,
        rdkit_replace_substructure_tool,
        stk_export_to_xyz_tool,
    ],
    "catalysis": [design_mbh_catalysts_tool],
    "analysis": [find_result_json_tool, get_property_from_result_tool],
    "thermo": [find_result_json_tool, get_property_from_result_tool],
}
_TOOLS = {tool.name: tool for tools in _TOOL_GROUPS.values() for tool in tools}
_active_allowed_tools: ContextVar[set[str] | None] = ContextVar("active_allowed_tools", default=None)


def get_allowed_tools(profile: str | None = None, user_request: str = "") -> list[str]:
    """Return tool names permitted for the current or requested profile."""
    if profile is None:
        active = _active_allowed_tools.get()
        if active is not None:
            return [name for name in _TOOLS if name in active]
        profile = "chem"
    groups = allowed_group_names(profile, user_request)
    allowed = {tool.name for group in groups for tool in _TOOL_GROUPS.get(group, [])}
    return [name for name in _TOOLS if name in allowed]


def set_allowed_profile(profile: str, user_request: str = "") -> Token[set[str] | None]:
    return _active_allowed_tools.set(set(get_allowed_tools(profile, user_request)))


def reset_allowed_profile(token: Token[set[str] | None]) -> None:
    _active_allowed_tools.reset(token)


def call_tool(tool_name: str, args: dict[str, Any], workdir: str) -> dict[str, Any]:
    """Call one allowlisted function tool; reject arbitrary tool or shell execution."""
    if tool_name not in get_allowed_tools():
        raise ValueError(f"Unknown or disallowed tool: {tool_name}")
    if not isinstance(args, dict):
        raise ValueError("Tool args must be a JSON object.")

    root = Path(workdir)
    root.mkdir(parents=True, exist_ok=True)
    token = set_agent_workdir(root)
    try:
        arguments = json.dumps(args)
        context = ToolContext(
            context=None,
            tool_name=tool_name,
            tool_call_id=f"executor_{tool_name}",
            tool_arguments=arguments,
        )
        output = asyncio.run(_TOOLS[tool_name].on_invoke_tool(context, arguments))
    finally:
        reset_agent_workdir(token)

    if not isinstance(output, dict):
        raise ValueError(f"Tool '{tool_name}' returned an unsupported result type.")
    return {"tool_name": tool_name, **output}
