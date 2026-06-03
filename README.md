# CSPilot

Computational chemistry agentic workflow package.

Created by Sandip Giri.

CSPilot combines deterministic molecular-structure tools with an optional
AGAPI/OpenAI-compatible planning layer. It is designed to keep local scientific
workflows reproducible: commands write JSON records, reports only summarize
returned values, and agent plans may call only registered tools.

## What CSPilot Can Do

- Inspect XYZ structures with ASE.
- Run xTB geometry optimization.
- Run ORCA single-point calculations through OPI / `orca-pi`.
- Run fixed xTB to ORCA single-point and frequency workflows.
- Run fixed MACE to ORCA single-point workflows when MACE is installed.
- Build and edit molecules with lightweight stk/RDKit tools.
- Run stk to xTB optimization through a fixed workflow.
- Use AGAPI/OpenAI-compatible planning for natural-language workflows.
- Run LangGraph in single-agent or routed multi-agent mode.
- Query optional AGAPI/JARVIS-style materials tools when available.
- Find and query result JSON files without inventing missing properties.
- Produce Rich terminal summaries plus Markdown or HTML reports.

## Quick Installation

```bash
uv sync
uv run cspilot --help
```

Editable pip install:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Optional extras:

```bash
python -m pip install -e ".[stk]"
python -m pip install -e ".[mace]"
python -m pip install -e ".[dev,docs]"
```

ORCA, xTB, NWPESSe, and MACE model files are external requirements. Installing
CSPilot does not install ORCA or xTB.

## Environment

Create `.env.cspilot` in the working directory:

```dotenv
CSPILOT_RUNS_DIR=runs
XTB_COMMAND=xtb
ORCA_COMMAND=/path/to/orca
NWPESSE_BIN=nwpesse
MACE_MODEL=/path/to/model.model

AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b
```

## Minimal Examples

```bash
cspilot inspect tests/examples/input.xyz
cspilot xtb-opt tests/examples/input.xyz --charge 0 --uhf 0
cspilot orca-sp tests/examples/input.xyz --method r2scan-3c --basis def2-SVP
```

Fixed workflow:

```bash
cspilot workflow xtb-orca-sp tests/examples/input.xyz \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

stk build and xTB:

```bash
cspilot stk-build-smiles "c1ccccc1" --workdir runs/stk_benzene
cspilot stk-xtb "c1ccccc1" --workdir runs/stk_xtb
```

## LangGraph Examples

Single mode uses the selected profile directly:

```bash
cspilot graph-run "inspect tests/examples/input.xyz" \
  --workdir runs/water --profile chem --agent-mode single
```

Multi mode first routes to a specialist profile, then uses the same planner,
executor, verifier, and reporter:

```bash
cspilot graph-run "Find all Al2O3 materials" \
  --profile auto --agent-mode multi --html --workdir runs/al2o3
```

Useful output flags:

```bash
cspilot graph-run "inspect tests/examples/input.xyz" --workdir runs/water --no-pretty
cspilot graph-run "inspect tests/examples/input.xyz" --workdir runs/water --quiet
```

## Single vs Multi-Agent Mode

- `single`: `planner -> executor -> verifier -> reporter`
- `multi`: `router -> planner -> executor -> verifier -> reporter`

Multi-agent mode is specialist routing only. It does not spawn independent
autonomous agents and does not duplicate tool execution.

## AGAPI

AGAPI is used for:

- direct tool-using agent requests via `cspilot agent`;
- JSON planning via `cspilot plan` and `cspilot run`;
- LangGraph planning via `cspilot graph-run`;
- optional materials query wrappers when the AGAPI prebuilt agent is installed.

Local xTB, ORCA, MACE, stk, and ASE results still come from local tools and
local output files. AGAPI is not used to fabricate energies or structures.

## Current Limitations

- ORCA and xTB must be installed and configured separately.
- `stk -> xTB -> ORCA` is available through planner/graph requests, not as a
  fixed deterministic CLI workflow command.
- Multiwfn, MongoDB, MCP server, torch-sim MD, and Streamlit UI are planned.
- Reports only include properties present in parsed JSON/tool output.
- The repair module exists, but the current `graph-run` path is the clean
  planner/executor/verifier/reporter flow without a repair node.

## Roadmap

- Deterministic CLI and fixed workflows: implemented.
- AGAPI planner/executor and LangGraph single/multi routing: implemented.
- Documentation and tests: in progress.
- Planned: Multiwfn, LangGraph repair/retry integration, expanded stk
  generation, torch-sim MLIP MD, MongoDB job database, MCP server, Streamlit UI.

See `docs/` for detailed installation, configuration, CLI, tools, workflows,
agent usage, safety, and examples.
