from __future__ import annotations

import asyncio
import json
from contextvars import ContextVar, Token
from numbers import Real
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
    molecule_name_to_xyz_tool,
    nwpesse_global_minimum_search_tool,
    parse_cluster_formula_tool,
    rdkit_replace_substructure_tool,
    reset_agent_workdir,
    run_mace_optimize,
    run_orca_single_point,
    run_xtb_optimize,
    run_xtb_orca_workflow,
    set_agent_workdir,
    smiles_to_xyz_tool,
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
        molecule_name_to_xyz_tool,
        smiles_to_xyz_tool,
        parse_cluster_formula_tool,
        nwpesse_global_minimum_search_tool,
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
    "nwpesse": [parse_cluster_formula_tool, nwpesse_global_minimum_search_tool],
    "analysis": [find_result_json_tool, get_property_from_result_tool],
    "thermo": [find_result_json_tool, get_property_from_result_tool],
}
_TOOLS = {tool.name: tool for tools in _TOOL_GROUPS.values() for tool in tools}
_active_allowed_tools: ContextVar[set[str] | None] = ContextVar("active_allowed_tools", default=None)
_TOOL_ARG_ALLOWLIST: dict[str, set[str]] = {
    "inspect_structure": {"xyz_path"},
    "run_xtb_optimize": {"xyz_path", "charge", "uhf"},
    "run_orca_single_point": {"xyz_path", "method", "basis", "charge", "mult", "nprocs"},
    "run_mace_optimize": {"xyz_path", "model_path", "fmax", "steps"},
    "run_xtb_orca_workflow": {"xyz_path", "method", "basis", "charge", "mult", "uhf", "nprocs"},
    "molecule_name_to_xyz_tool": {"name", "output_path", "num_confs"},
    "smiles_to_xyz_tool": {"smiles", "output_path", "num_confs", "forcefield"},
    "stk_build_from_smiles_tool": {"smiles", "output_path"},
    "stk_building_block_from_file_tool": {"input_path", "output_path"},
    "stk_linear_polymer_from_smiles_tool": {
        "monomer_smiles",
        "repeating_unit",
        "num_repeating_units",
        "output_path",
    },
    "stk_construct_cage_from_smiles_tool": {"building_block_smiles", "topology", "output_path"},
    "rdkit_replace_substructure_tool": {"parent_smiles", "old_smarts", "new_smiles", "output_path"},
    "stk_export_to_xyz_tool": {"input_path", "output_path"},
}


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
        normalized_args = normalize_tool_args(tool_name, args)
        normalized_args = _resolve_workdir_paths(normalized_args, root)
        arguments = json.dumps(normalized_args)
        context = ToolContext(
            context=None,
            tool_name=tool_name,
            tool_call_id=f"executor_{tool_name}",
            tool_arguments=arguments,
        )
        output = asyncio.run(_TOOLS[tool_name].on_invoke_tool(context, arguments))
    except Exception as exc:
        output = {
            "success": False,
            "tool": tool_name,
            "error": f"{type(exc).__name__}: {exc}",
        }
    finally:
        reset_agent_workdir(token)

    normalized = normalize_tool_result(tool_name, output)
    return {"tool_name": tool_name, **normalized}


def normalize_tool_result(tool_name: str, result: Any) -> dict[str, Any]:
    """Normalize arbitrary tool output into a JSON-serializable dictionary."""
    if isinstance(result, dict):
        return _json_safe(result)
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
        except json.JSONDecodeError:
            if result.lower().startswith("an error occurred while running the tool"):
                return {"success": False, "tool": tool_name, "error": result}
            return {"success": True, "tool": tool_name, "message": result}
        if isinstance(parsed, dict):
            return _json_safe(parsed)
        return {"success": True, "tool": tool_name, "value": _json_safe(parsed)}
    if isinstance(result, Path):
        return {"success": True, "tool": tool_name, "path": str(result)}
    if isinstance(result, bool):
        return {"success": True, "tool": tool_name, "value": result}
    if isinstance(result, Real):
        return {"success": True, "tool": tool_name, "value": result}
    if result is None:
        return {"success": False, "tool": tool_name, "error": "Tool returned None"}
    return {
        "success": False,
        "tool": tool_name,
        "error": f"Unsupported result type: {type(result).__name__}",
        "repr": repr(result),
    }


def normalize_tool_args(tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Normalize common planner aliases to registered function-tool argument names."""
    normalized = dict(args)
    if "output_file" in normalized and "output_path" not in normalized:
        normalized["output_path"] = normalized.pop("output_file")
    if "input_smiles" in normalized and "smiles" not in normalized:
        normalized["smiles"] = normalized.pop("input_smiles")
    if "smiles_string" in normalized and "smiles" not in normalized:
        normalized["smiles"] = normalized.pop("smiles_string")

    input_alias = next(
        (key for key in ("input_xyz", "input_file", "xyz_file", "file") if key in normalized),
        None,
    )
    if input_alias is not None:
        target = "input_path" if _prefers_input_path(tool_name) else "xyz_path"
        if target not in normalized:
            normalized[target] = normalized.pop(input_alias)

    allowed = _TOOL_ARG_ALLOWLIST.get(tool_name)
    if allowed is not None:
        normalized = {key: value for key, value in normalized.items() if key in allowed}
    return _json_safe(normalized)


def _resolve_workdir_paths(args: dict[str, Any], root: Path) -> dict[str, Any]:
    resolved = dict(args)
    for key in ("output_path", "output_file"):
        if key in resolved:
            resolved[key] = _path_in_workdir(resolved[key], root, must_exist=False)
    for key in ("xyz_path", "input_path"):
        if key in resolved:
            resolved[key] = _path_in_workdir(resolved[key], root, must_exist=True)
    return resolved


def _path_in_workdir(value: Any, root: Path, must_exist: bool) -> Any:
    if not isinstance(value, str):
        return value
    path = Path(value).expanduser()
    if path.is_absolute():
        return str(path)
    workdir_path = root / path
    if not must_exist or workdir_path.exists():
        return str(workdir_path)
    return value


def _prefers_input_path(tool_name: str) -> bool:
    lowered = tool_name.lower()
    return "building_block_from_file" in lowered or "export_to_xyz" in lowered


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value
