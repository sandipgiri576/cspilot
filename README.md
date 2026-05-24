# cspilot

`cspilot` is a small command line package for structure inspection and local
computational chemistry runs.

## Install

```bash
pip install -e .
```

For MACE optimization support, install the optional extra:

```bash
pip install -e ".[mace]"
```

## Configuration

`cspilot` loads environment variables from `.env.cspilot` when present.

```bash
export ORCA_COMMAND=orca
export XTB_COMMAND=xtb
CSPILOT_RUNS_DIR=runs
```

## CLI

```bash
cspilot inspect input.xyz
cspilot xtb-opt input.xyz --charge 0 --uhf 0
cspilot orca-sp input.xyz --method r2scan-3c --basis def2-SVP --charge 0 --mult 1
cspilot mace-opt input.xyz --model model_path
```

Each command creates a timestamped directory under `runs/` and writes
`result.json` there.
