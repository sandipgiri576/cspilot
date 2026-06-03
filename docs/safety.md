# Safety and Scientific Integrity

## Implemented Controls

- LLM output is not executed as shell code.
- The executor calls only registered tools in `src/cspilot/tools/registry.py`.
- Profile allowlists restrict which tools can be used.
- External binaries come from fixed settings such as `XTB_COMMAND`,
  `ORCA_COMMAND`, and `NWPESSE_BIN`.
- Reports never invent numerical values.
- If a parsed property is absent, reports say it was not found in parsed
  results.
- JSON files are written for plans, step results, execution results,
  verification results, graph state, and reports.
- Verification checks success flags, expected files, and numeric fields before
  marking workflows verified.

## Agent Boundaries

- Direct agent and planner prompts prohibit invented energies, structures,
  files, and completed calculations.
- LangGraph multi-agent mode is deterministic routing only.
- No independent uncontrolled agents are spawned.
- Tool calls are routed through the same executor and registry.

## External Software Responsibility

Users remain responsible for:

- installing and licensing ORCA;
- installing xTB, NWPESSe, MACE, and stk where needed;
- choosing scientifically meaningful methods, charges, spin states, basis
  sets, and model files;
- reviewing raw ORCA/xTB/NWPESSe output before relying on values.

## Planned Features

Multiwfn, MongoDB, MCP, torch-sim, and Streamlit are planned. When Multiwfn is
added, only reviewed whitelisted operations should be exposed. Arbitrary
LLM-generated shell, Python, or Multiwfn scripts must not be executed.

## Secrets

Keep `AGAPI_API_KEY` in `.env.cspilot` and out of version control. Do not paste
private API keys, licensed paths, or sensitive output into public reports.
