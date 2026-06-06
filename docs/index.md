# CSPilot Documentation

Computational chemistry agentic workflow package.

Created by Sandip Giri.

CSPilot is a command-line package for reproducible molecular structure
workflows. It combines deterministic local tools, AGAPI/OpenAI-compatible
planning, LangGraph orchestration, JSON verification, and polished terminal
reports.

## Quick Install

```bash
python -m pip install -e .
```

For documentation builds:

```bash
python -m pip install -e ".[docs]"
mkdocs build --strict
```

For stk support:

```bash
python -m pip install -e ".[stk]"
```

## First Command

```bash
cspilot inspect tests/examples/input.xyz
```

This reads an XYZ file with ASE and writes a timestamped `result.json`.

## Agentic Start

Single-agent graph:

```bash
cspilot graph-run "inspect tests/examples/input.xyz" \
  --workdir runs/water --profile chem --agent-mode single
```

Routed multi-agent graph:

```bash
cspilot graph-run "Find all Al2O3 materials" \
  --profile auto --agent-mode multi --html --workdir runs/al2o3
```

## Documentation Map

- [Installation](installation.md): install with `uv` or `pip`.
- [Configuration](configuration.md): `.env.cspilot`, ORCA, xTB, AGAPI, MACE.
- [CLI Usage](cli_usage.md): every implemented command and output file.
- [Agent Usage](agent_usage.md): direct agent, planner/executor, LangGraph.
- [Workflows](workflows.md): xTB, ORCA, stk, NWPESSe, and result extraction.
- [Tools](tools.md): Python and agent tools grouped by domain.
- [AGAPI Integration](agapi.md): model backend and materials wrapper.
- [Examples](examples.md): copy-paste workflows.
- [Safety](safety.md): execution boundaries and scientific integrity.
- [Code Documentation](reference/SUMMARY.md): mkdocstrings reference pages.

## Current Status

Implemented:

- ASE inspection.
- xTB optimization.
- ORCA calcultions.
- xTB to ORCA workflows.
- MACE to ORCA workflow.
- stk build/edit/export and stk to xTB.
- NWPESSe fragment-cluster search.
- AGAPI direct agent and JSON planner/executor.
- LangGraph single mode and routed multi mode.
- Rich terminal reports and Markdown/HTML final reports.

Planned:

- LangGraph repair/retry node integration.
- Multiwfn post-processing.
- Expanded stk topology presets.
- torch-sim MLIP molecular dynamics.
- MongoDB job database.
- MCP server.
- Streamlit UI.

## Build Notes

The documentation site uses MkDocs and mkdocstrings. Reference pages document
the real import package, `cspilot`, not `chemagent`.
