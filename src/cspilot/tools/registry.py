from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from agents.tool_context import ToolContext

from cspilot.tools.agent_tools import (
    inspect_structure,
    reset_agent_workdir,
    run_mace_optimize,
    run_orca_single_point,
    run_xtb_optimize,
    run_xtb_orca_workflow,
    set_agent_workdir,
)

_TOOLS = {
    tool.name: tool
    for tool in [
        inspect_structure,
        run_xtb_optimize,
        run_orca_single_point,
        run_mace_optimize,
        run_xtb_orca_workflow,
    ]
}


def get_allowed_tools() -> list[str]:
    """Return the exact tool names accepted by the explicit executor."""
    return list(_TOOLS)


def call_tool(tool_name: str, args: dict[str, Any], workdir: str) -> dict[str, Any]:
    """Call one allowlisted function tool; reject arbitrary tool or shell execution."""
    if tool_name not in _TOOLS:
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
