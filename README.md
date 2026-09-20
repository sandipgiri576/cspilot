[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.20568039.svg)](https://doi.org/10.5281/zenodo.20568039)
# 🧪 CSPilot

Computational chemistry agentic workflow package.

Created by Sandip Giri.

CSPilot helps run and document molecular structure workflows from the command
line. It combines deterministic chemistry tools with optional
OpenRouter/OpenAI-compatible planning, LangGraph orchestration, JSON verification,
and clean terminal/report output. Documentation is under developement and can be read [here](https://sandipgiri576.github.io/cspilot/).

## ✨ Features

- ASE structure inspection for XYZ files.
- xTB geometry optimization.
- ORCA calcutions 
- Fixed xTB to ORCA single-point and frequency workflows.
- Optional MACE to ORCA workflows.
- stk/RDKit molecule generation, editing, export, and stk to xTB optimization.
- OpenRouter agent with iterative tool decisions and verified observations.
- Domain Markdown skills loaded automatically by the planner and reporter.
- Single-agent default, specialist routing, and opt-in independent multi-agent loops.
- Local Multiwfn Mulliken/Hirshfeld charges and Mayer bond orders from ORCA GBW.
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
cspilot graph-run "use stk to build water from SMILES O then run xTB and ORCA single point" \
  --workdir runs/stk_orca
```
```bash
cspilot graph-run "Find the global minima of (h2o)4Mg cluster." \
  --workdir runs/global_minima
```

```bash
cspilot graph-run "inspect tests/examples/input.xyz" \
  --profile auto --agent-mode multi --workdir runs/inspection
```

Graph paths:

- `single`: `planner -> decide -> tool -> observe -> planner; finish -> verifier -> reporter`
- `multi`: `router -> planner -> decide -> tool -> observe -> planner; finish -> verifier -> reporter`

The legacy `--agent-mode multi` is routing only. The additional `--multiagent`
flag enables `decomposer -> independent child loops -> aggregator -> verify -> report`.
Children run serially by default; `--workers 2` enables bounded concurrency.
Each child has its own work directory and tool-call budget (up to eight children).
No model-generated shell commands execute. See [multi-agent and Multiwfn usage](docs/multiagent_multiwfn.md).

Use water for inexpensive routine tests:

```bash
cspilot "Optimize water from SMILES O and compute Gibbs energy and enthalpy with ORCA r2scan-3c" --workdir runs/water-thermo
cspilot "Calculate gas-phase reaction enthalpy: CH4 + 2 O2 -> CO2 + 2 H2O, ORCA r2scan-3c. O2 is triplet. Optimize and calculate frequencies for every species." --multiagent --workdir runs/combustion
```

Reaction results use stoichiometric sums of verified enthalpies, not model arithmetic.
This first version supports gas phase, 298.15 K, 1 atm; water is vapor, not liquid.

`run` and `graph-run` choose one tool at a time, observe its real output, and
decide what to do next. Use `--max-steps 8` and `--max-retries 1` to bound
execution. Fixed workflows remain available as tools and deterministic commands.
Full results print on screen, including when saving HTML; `--quiet` suppresses
details. Domain guidance lives in `src/cspilot/skills/`.

Bare prompts use the tool agent: `cspilot "what is the SMILES string of caffeine?"`.
New Gibbs/enthalpy requests use ORCA optimization plus frequencies. The terminal
shows returned answers and verification; full diagnostic reports remain saved.
Use `cspilot search "..."` for general explanations without tool execution.

## ⚙️ Configuration

Create `.env.cspilot`:

```dotenv
CSPILOT_RUNS_DIR=runs
XTB_COMMAND=xtb
ORCA_COMMAND=/path/to/orca
MULTIWFN_COMMAND=/path/to/Multiwfn_noGUI
ORCA_2MKL_COMMAND=/path/to/orca_2mkl
NWPESSE_BIN=nwpesse
MACE_MODEL=/path/to/model.model

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-oss-20b
```

OpenRouter is the sole model backend for `search`, `agent`, `plan`, `run`, and
`graph-run`.

ORCA, xTB, NWPESSe, and MACE model files are external requirements. Installing
CSPilot does not install ORCA or xTB.

## 🧬 stk Molecule Generation

```bash
cspilot stk-build-smiles "O" --workdir runs/stk_water
cspilot stk-xtb "O" --workdir runs/stk_xtb
```

Agent/planner route for stk followed by xTB and ORCA:

```bash
cspilot graph-run "use stk to build water from SMILES O then run xTB and ORCA single point" \
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
- [Project Structure](PROJECT_STRUCTURE.md)
- [Agentic Architecture Audit](docs/agentic_audit.md)
- [Next-stage TODO](TODO.md)

Build docs locally:

```bash
python -m pip install -e ".[docs]"
mkdocs build --strict
```

<!-- ## 🛣️ Roadmap

Implemented:

- deterministic CLI;
- fixed xTB/MACE to ORCA workflows;
- OpenRouter-backed planner/executor;
- LangGraph single and routed multi mode;
- stk baseline tools;
- Rich terminal reports.

Planned:

- checkpoint/resume and request-level completion validation;
- Expanded Multiwfn analyses beyond charges and Mayer bond orders;
- expanded stk topology support;
- torch-sim MLIP molecular dynamics;
- MongoDB job database;
- MCP server;
- Streamlit UI. -->

## 🙏 Acknowledgements

CSPilot uses and integrates with ASE, xTB, ORCA, RDKit, stk, MACE,
LangGraph, Rich, Typer, Pydantic, and other open-source packages. OpenRouter is
its model provider.
