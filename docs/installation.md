# Installation

## Requirements

- Python 3.11 or newer.
- `uv` or `pip`.
- External binaries for calculation commands:
  - xTB for `xtb-opt`, `stk-xtb`, and xTB workflows.
  - ORCA for `orca-sp` and ORCA workflows.
  - NWPESSe for `nwpesse-search`.
- Optional MACE model file for MACE workflows.

ORCA is not installed by pip. Install ORCA separately under the ORCA license and
set `ORCA_COMMAND` in `.env.cspilot`.

## Install With uv

```bash
uv sync
uv run cspilot --help
```

Optional extras:

```bash
uv sync --extra stk
uv sync --extra mace
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

Optional extras:

```bash
python -m pip install -e ".[stk]"
python -m pip install -e ".[mace]"
python -m pip install -e ".[dev,docs]"
```

## Optional Dependency Groups

| Extra | Purpose |
| --- | --- |
| `stk` | stk molecule construction tools plus compatibility dependencies |
| `mace` | `mace-torch` support |
| `dev` | pytest, coverage, and Ruff |
| `docs` | documentation tooling |

## External Programs

| Program | Used by | Notes |
| --- | --- | --- |
| xTB | `xtb-opt`, `stk-xtb`, xTB to ORCA workflows | Configure `XTB_COMMAND`. |
| ORCA | `orca-sp`, ORCA workflows, OPI tools | Configure `ORCA_COMMAND`; not installed by pip. |
| NWPESSe | `nwpesse-search` | Configure `NWPESSE_BIN`. |
| Multiwfn | Planned | No current CLI support. |

## Sanity Checks

Python-only structure inspection:

```bash
cspilot inspect tests/examples/input.xyz
```

CLI help:

```bash
cspilot --help
cspilot graph-run --help
```

stk import check after installing the extra:

```bash
cspilot stk-build-smiles "c1ccccc1" --workdir runs/stk_check
```
