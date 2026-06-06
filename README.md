# 🧪 CSPilot

Computational chemistry agentic workflow package.

Created by Sandip Giri.

CSPilot helps run and document molecular structure workflows from the command
line. It combines deterministic chemistry tools with optional
AGAPI/OpenAI-compatible planning, LangGraph orchestration, JSON verification,
and clean terminal/report output. Documentation is under developement and can be read [here](https://sandipgiri576.github.io/cspilot/).

## ✨ Features

- ASE structure inspection for XYZ files.
- xTB geometry optimization.
- ORCA single-point jobs through OPI / `orca-pi`.
- Fixed xTB to ORCA single-point and frequency workflows.
- Optional MACE to ORCA workflows.
- stk/RDKit molecule generation, editing, export, and stk to xTB optimization.
- AGAPI-backed direct agent, JSON planner/executor, and LangGraph runner.
- Single-agent and routed multi-agent graph modes.
- Optional AGAPI/JARVIS-style materials query wrapper.
- Rich terminal summaries plus Markdown or HTML reports.
- Machine-readable JSON outputs for plans, steps, execution, verification, and final state.

## 🚀 Quick Start

Install with `uv`:

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
python -m pip install -e ".[docs]"
```

First command:

```bash
cspilot inspect tests/examples/input.xyz
```

## 🤖 Agentic Workflows

Single graph mode uses the selected profile directly:

```bash
cspilot graph-run "inspect tests/examples/input.xyz" \
  --workdir runs/water --profile chem --agent-mode single
```

Multi graph mode routes to a specialist profile first:

```bash
cspilot graph-run "Find all Al2O3 materials" \
  --profile auto --agent-mode multi --html --workdir runs/al2o3
```

Graph paths:

- `single`: `planner -> executor -> verifier -> reporter`
- `multi`: `router -> planner -> executor -> verifier -> reporter`

Multi-agent mode is routing only. CSPilot does not spawn uncontrolled parallel
agents and does not execute LLM-generated shell commands.

## ⚙️ Configuration

Create `.env.cspilot`:

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

ORCA, xTB, NWPESSe, and MACE model files are external requirements. Installing
CSPilot does not install ORCA or xTB.

## 🧬 stk Molecule Generation

```bash
cspilot stk-build-smiles "c1ccccc1" --workdir runs/stk_benzene
cspilot stk-xtb "c1ccccc1" --workdir runs/stk_xtb
```

Agent/planner route for stk followed by xTB and ORCA:

```bash
cspilot graph-run "use stk to build benzene from SMILES c1ccccc1 then run xTB and ORCA single point" \
  --workdir runs/stk_orca
```

There is not yet a fixed deterministic `stk-to-xtb-orca` CLI subcommand.

## 🔬 ORCA/xTB Workflows

```bash
cspilot xtb-opt tests/examples/input.xyz --charge 0 --uhf 0
cspilot orca-sp tests/examples/input.xyz --method r2scan-3c --basis def2-SVP
cspilot workflow xtb-orca-sp tests/examples/input.xyz --charge 0 --mult 1
cspilot workflow xtb-orca-freq tests/examples/input.xyz --charge 0 --mult 1
```

Reports include parsed energies and thermochemistry only when those values are
present in completed outputs.

## 📊 Reports

`run` and `graph-run` support:

```bash
--pretty / --no-pretty
--quiet
--html
```

JSON files are always preserved. Terminal output can be Rich-formatted,
minimal, or quiet.

## 📚 Documentation

See:

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [CLI Usage](docs/cli_usage.md)
- [Agent Usage](docs/agent_usage.md)
- [Workflows](docs/workflows.md)
- [Tools](docs/tools.md)
- [Examples](docs/examples.md)

Build docs locally:

```bash
python -m pip install -e ".[docs]"
mkdocs build --strict
```

<!-- ## 🛣️ Roadmap

Implemented:

- deterministic CLI;
- fixed xTB/MACE to ORCA workflows;
- AGAPI planner/executor;
- LangGraph single and routed multi mode;
- stk baseline tools;
- Rich terminal reports.

Planned:

- LangGraph repair/retry node integration;
- Multiwfn post-processing;
- expanded stk topology support;
- torch-sim MLIP molecular dynamics;
- MongoDB job database;
- MCP server;
- Streamlit UI. -->

## 🙏 Acknowledgements

CSPilot uses and integrates with ASE, xTB, ORCA/OPI, RDKit, stk, MACE,
LangGraph, Rich, Typer, Pydantic, and many others open source package. It uses AGAPI-compatible model backends.


