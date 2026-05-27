# CLI Usage

Commands below are defined in `src/cspilot/cli.py`. The installed script name
is `cspilot`; a legacy `cspiolt` alias also currently exists.

## Deterministic Commands

### `inspect`

Purpose: read an XYZ structure with ASE and print formula, atom count,
periodicity, and center of mass.

```bash
cspilot inspect input.xyz
```

Output: `runs/<timestamp>-inspect/input.xyz` and `result.json`.

### `xtb-opt`

Purpose: optimize an XYZ geometry with xTB.

```bash
cspilot xtb-opt input.xyz --charge 0 --uhf 0
```

Output: `runs/<timestamp>-xtb-opt/result.json` and, after successful xTB
execution, `xtbopt.xyz` and `xtbopt.log`.

### `orca-sp`

Purpose: run an ORCA single-point calculation through OPI.

```bash
cspilot orca-sp input.xyz --method r2scan-3c --basis def2-SVP --charge 0 --mult 1
```

Output: `runs/<timestamp>-orca-sp/result.json`, OPI input `job.inp`, and
successful ORCA output `job.out`.

### `mace-opt`

Purpose: optimize geometry with an optional MACE calculator and model file.

```bash
cspilot mace-opt input.xyz --model /path/to/model.model
```

Output: `runs/<timestamp>-mace-opt/result.json`; on success,
`mace_opt.xyz`, `mace_opt.traj`, and `mace_opt.log`.

## Fixed Workflows

### `workflow xtb-orca-sp`

```bash
cspilot workflow xtb-orca-sp input.xyz --charge 0 --mult 1 \
  --method r2scan-3c --basis def2-SVP
```

Output: `runs/<timestamp>-xtb-orca-sp/workflow_result.json`, plus
`01_xtb_opt/` and `02_orca_sp/` job files when the steps run.

### `workflow xtb-orca-freq`

```bash
cspilot workflow xtb-orca-freq input.xyz --charge 0 --mult 1 \
  --method r2scan-3c --basis def2-SVP
```

Output: `runs/<timestamp>-xtb-orca-freq/workflow_result.json`, plus
`01_xtb_opt/` and `02_orca_freq/` job files. Gibbs free energy is recorded
only when parsed from the ORCA result.

### `workflow mace-orca`

```bash
cspilot workflow mace-orca input.xyz --model /path/to/model.model \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

Output: `runs/<timestamp>-mace-orca/workflow_result.json`, plus MACE and ORCA
subdirectories when executed successfully.

## AGAPI And Agent Commands

### `agent`

Purpose: let an AGAPI-backed Agents SDK agent select exposed tools directly.
Supported direct-agent profiles are `chem`, `materials`, and `general`.

```bash
cspilot agent "gibbs free energy of water in ORCA r2scan-3c" \
  --workdir runs/water-agent --agent-profile chem
```

Options include `--model` and `--base-url`.

Output: `<workdir>/agent_result.json` plus calculation subruns selected by the
agent.

### `plan`

Purpose: produce a JSON plan without executing it. Planner profiles are
`chem`, `materials`, `analysis`, `thermo`, and `general`.

```bash
cspilot plan "Find all Al2O3 materials" --workdir runs/al2o3 --profile materials
```

Output: `<workdir>/plan.json`.

### `execute`

Purpose: execute an existing JSON plan through the profile allowlist only.

```bash
cspilot execute runs/al2o3/plan.json --workdir runs/al2o3 --profile materials
```

Output: `<workdir>/plan.json`, `step_001_result.json` for each executed step,
and `execution_result.json`.

### `run`

Purpose: plan, execute, verify, and create a final deterministic report.

```bash
cspilot run "Find all Al2O3 materials" --workdir runs/al2o3 \
  --profile materials --html
```

Output: `<workdir>/plan.json`, step result JSON files,
`execution_result.json`, `verification_result.json`, and either
`final_report.md` or `final_report.html`.
