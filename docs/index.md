# CSPilot Documentation

Computational chemistry agentic workflow package.

Created by Sandip Giri.

CSPilot is a command-line package for reproducible molecular structure
workflows. It combines deterministic local tools, OpenRouter-backed
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
cspilot graph-run "build water from SMILES O with stk" \
  --profile auto --agent-mode multi --workdir runs/water
```

## Documentation Map

- [Installation](installation.md): install with `uv` or `pip`.
- [Configuration](configuration.md): `.env.cspilot`, OpenRouter, ORCA, xTB, and MACE.
- [CLI Usage](cli_usage.md): every implemented command and output file.
- [Agent Usage](agent_usage.md): direct agent, planner/executor, LangGraph.
- [Workflows](workflows.md): xTB, ORCA, stk, NWPESSe, and result extraction.
- [Tools](tools.md): Python and agent tools grouped by domain.
- [Agentic Audit](agentic_audit.md): current autonomy and orchestration assessment.
- [Examples](examples.md): copy-paste workflows.
- [Safety](safety.md): execution boundaries and scientific integrity.
- [Code Documentation](api.md): public orchestration entry points.

## Current Status

Implemented:

- ASE inspection.
- xTB optimization.
- ORCA calcultions.
- xTB to ORCA workflows.
- MACE to ORCA workflow.
- stk build/edit/export and stk to xTB.
- NWPESSe fragment-cluster search.
- OpenRouter direct agent and JSON planner/executor.
- LangGraph single mode and routed multi mode.
- Opt-in independent child loops with `--multiagent`; see [usage and limits](multiagent_multiwfn.md).
- Local Multiwfn Mulliken/Hirshfeld charges and Mayer bond orders.
- Rich terminal reports and Markdown/HTML final reports.

Planned:

- Checkpoint/resume and request-level completion validation.
- Additional validated Multiwfn post-processing operations.
- Expanded stk topology presets.
- torch-sim MLIP molecular dynamics.
- MongoDB job database.
- MCP server.
- Streamlit UI.

## Build Notes

The documentation site uses MkDocs and mkdocstrings. Reference pages document
the real import package, `cspilot`, not `chemagent`.
