# cspilot

`cspilot` is a Python command-line package for reproducible molecular structure
workflows. It combines deterministic calculation tools with an optional
AGAPI/OpenAI-compatible agent layer that may choose only registered operations
and records results as JSON.

## Current Features

- ASE-based XYZ structure inspection and I/O.
- xTB geometry optimization.
- ORCA single point, optimization, and frequency support through OPI
  (`orca-pi`), including parsed energy and thermochemistry properties when ORCA
  reports them.
- Optional MACE geometry optimization with `mace-torch` and a supplied model.
- Fixed workflows: xTB to ORCA single point, xTB to ORCA frequency, and MACE
  to ORCA single point.
- NWPESSe global-minimum search setup for fragment clusters, including
  `mol.cluster`, `mol.inp`, fragment XYZ generation, external execution, and
  lowest-energy XYZ discovery.
- Molecule name to SMILES lookup with PubChem and SMILES to XYZ generation with
  RDKit, exposed through agent tools and Python functions.
- AGAPI/OpenAI-compatible tool-using agent plus JSON planner/executor commands.
- Optional AGAPI prebuilt materials-query wrapper for `run --profile materials`.
- Optional stk molecule construction/editing tools and GreenCatAI MBH catalyst-design wrapper.
- General AGAPI search via `cspilot search "..."` or quoted root questions.
- Result JSON discovery and property lookup, including Gibbs free energy
  aliases, when those values exist in prior output.

## Installation

With [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run cspilot --help
```

With pip:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

Install MACE support only when needed:

```bash
python -m pip install -e ".[mace]"
```

xTB and ORCA are external executables. Installing `cspilot` does not install
ORCA. See [Installation](docs/installation.md).

## Environment Setup

Create `.env.cspilot` in the project working directory:

```dotenv
CSPILOT_RUNS_DIR=runs
XTB_COMMAND=xtb
ORCA_COMMAND=/path/to/orca
NWPESSE_BIN=/home/anoop/apps/nwpesse/nwpesse

AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b

# Used by the MACE-to-ORCA workflow when --model is omitted:
MACE_MODEL=/path/to/model.model
```

The implemented variable names are `XTB_COMMAND`, `ORCA_COMMAND`, and
`MACE_MODEL`; names such as `XTB_BIN`, `ORCA_BIN`, `MULTIWFN_BIN`, and
`MACE_MODEL_PATH` are not currently read by the package.

## Minimal CLI Examples

```bash
cspilot inspect input.xyz
cspilot xtb-opt input.xyz --charge 0 --uhf 0
cspilot orca-sp input.xyz --method r2scan-3c --basis def2-SVP --charge 0 --mult 1
cspilot workflow xtb-orca-sp input.xyz --charge 0 --mult 1
cspilot workflow xtb-orca-freq input.xyz --charge 0 --mult 1
cspilot search "what is the chemical space?"
cspilot stk-build-smiles "C1=CC=CC=C1" --workdir runs/stk_benzene
cspilot stk-polymer "BrCCBr" --repeating-unit A --num-repeating-units 4 --workdir runs/stk_polymer
cspilot stk-xtb "C1=CC=CC=C1" --workdir runs/stk_xtb
cspilot nwpesse-search "(h2o)4Mg" --workdir runs/h2o4mg --max-calculations 10 --box-size 3.0
cspilot stk replace-smiles CCO O N runs/stk/ethylamine.xyz
cspilot greencatai design-mbh --search-space /path/to/search_space.json --scoring /path/to/scoring.json --output-dir runs/mbh_api
```

Deterministic commands create a timestamped subdirectory of `runs/` (or
`CSPILOT_RUNS_DIR`) and write `result.json` or `workflow_result.json`.

## Agent Examples

Direct tool-using agent:

```bash
cspilot agent "gibbs free energy of water in ORCA r2scan-3c" \
  --workdir runs/water-agent --agent-profile chem
```

Plan, execute, verify, and produce an HTML report:

```bash
cspilot run "Find all Al2O3 materials" \
  --workdir runs/al2o3 --profile materials --html
```

The agent is not a source of scientific data: it must obtain energies,
structures, and properties from tool output or state that they were not found.

## Supported Tools

| Area | Implemented capability |
| --- | --- |
| Structures | ASE loading, saving, and summary inspection |
| Molecular input | PubChem name lookup; RDKit validation, canonicalization, and XYZ generation |
| xTB | Geometry optimization |
| ORCA | OPI-driven single point, optimization, frequency, and output parsing |
| MACE | Optional geometry optimization from a local model |
| NWPESSe | Fragment-cluster global-minimum search input generation, execution, and lowest-energy candidate discovery |
| Results | Recursive JSON property retrieval with scientific aliases |
| AGAPI | OpenAI-compatible agent backend, general search, and optional materials-query wrapper |
| stk | Optional SMILES/file building, linear polymer construction, RDKit editing, XYZ export, and stk-to-xTB workflow |
| GreenCatAI | MBH catalyst-design wrapper around the public GreenCatAI API |

## Current Limitations

- xTB single-point execution is not implemented; current xTB support is
  geometry optimization.
- MACE requires the optional Python dependency and a model file.
- Thermochemical values such as Gibbs free energy are reported only when an
  ORCA frequency result contains them.
- The AGAPI agent requires network access and configured credentials.
- NWPESSe is an external binary configured with `NWPESSE_BIN`; cspilot does
  not install NWPESSe.
- stk cage construction is planned but not enabled yet; it requires safe
  topology-specific functional-group presets.
- Multiwfn, LangGraph, torch-sim, MongoDB, MCP, and Streamlit are not
  implemented. stk support is optional and limited to whitelisted construction/editing tools.

## Roadmap

Planned stages include Multiwfn post-processing, LangGraph retry/repair
orchestration, expanded stk structure generation, torch-sim MLIP molecular dynamics, a
MongoDB job database, an MCP server, and a Streamlit interface. See
[Roadmap](docs/roadmap.md).

## Documentation

- [Installation](docs/installation.md)
- [Configuration](docs/configuration.md)
- [CLI usage](docs/cli_usage.md)
- [Agent usage](docs/agent_usage.md)
- [Workflows](docs/workflows.md)
- [Examples](docs/examples.md)
- [Safety](docs/safety.md)

## Citation And Acknowledgements

A project citation will be added when a release archive or associated
publication is available.

Acknowledgement placeholders: ASE, xTB, ORCA/OPI, MACE, RDKit, PubChem,
stk, NWPESSe, GreenCatAI, OpenAI Agents SDK, and AGAPI. Users should cite the scientific software used in
their calculations according to the corresponding project guidance.
