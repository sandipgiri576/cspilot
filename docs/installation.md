# Installation

## Requirements

- Python 3.11 or newer.
- An XYZ input file for deterministic structure and calculation commands.
- xTB and/or ORCA executables installed separately for the corresponding jobs.

## Install With uv

From the repository root:

```bash
uv sync
uv run cspilot --help
```

Install the optional MACE dependency set:

```bash
uv sync --extra mace
```

Development and documentation extras are also defined:

```bash
uv sync --extra dev
uv sync --extra docs
```

## Editable pip Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

For MACE:

```bash
python -m pip install -e ".[mace]"
```

Optional groups in `pyproject.toml`:

| Extra | Purpose |
| --- | --- |
| `dev` | pytest, coverage, and Ruff |
| `docs` | documentation tooling |
| `mace` | `mace-torch` calculator support |
| `stk` | Optional stk molecule construction support plus `polars[rtcompat]` for broader CPU compatibility |

## External Programs

| Program | Status | Installation note |
| --- | --- | --- |
| xTB | Used by `xtb-opt` and xTB workflows | Install externally and configure `XTB_COMMAND`. |
| ORCA | Used by `orca-sp` and ORCA workflows | Install separately under the ORCA license and configure `ORCA_COMMAND`. ORCA is not installed by pip. |
| Multiwfn | Planned, not currently called | No cspilot configuration or CLI support yet. |

`orca-pi` supplies the Python interface and parsers; it is not the ORCA
quantum chemistry executable.

## Sanity Check

```bash
uv run cspilot inspect tests/examples/input.xyz
```

This command only needs Python dependencies and should produce a timestamped
`runs/*-inspect/result.json` record.

## GreenCatAI Development Install

GreenCatAI is not declared as a PyPI dependency in this package. For local development, install GreenCatAI in editable mode in the same environment, then confirm:

```bash
greencatai --help
cspilot greencatai --help
```

The cspilot wrapper calls `greencatai.api.design_mbh_catalysts`; the native GreenCatAI CLI remains available for direct use.
