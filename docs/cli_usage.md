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

## stk Commands

### `stk building-block-smiles`

Purpose: create an stk building block from SMILES and export `.mol`, `.sdf`, or `.xyz`.

```bash
cspilot stk building-block-smiles BrCCBr runs/stk/bb.mol -f bromo
```

Output: JSON on stdout and the requested molecule file when successful.

### `stk building-block-file`

Purpose: load an stk building block from an existing molecule file and optionally export it.

```bash
cspilot stk building-block-file molecule.mol --output-path runs/stk/copy.mol
```

Output: JSON on stdout and optional copied/exported file.

### `stk linear-polymer`

Purpose: construct a linear polymer with `stk.polymer.Linear`.

```bash
cspilot stk linear-polymer BrCCBr A 3 runs/stk/polymer.mol
```

Output: JSON on stdout and the requested molecule file when stk construction succeeds.

### `stk simple-cage`

Purpose: construct a cage from a small topology whitelist. Currently the documented topology is `four_plus_six`.

```bash
cspilot stk simple-cage runs/stk/cage.mol \
  --building-block 'NCCN' --topology four_plus_six
```

Output: JSON on stdout and the requested molecule file when stk construction succeeds. Unsupported topologies return a JSON error.

### `stk replace-smiles`

Purpose: replace a substructure using RDKit and export the edited molecule.

```bash
cspilot stk replace-smiles CCO O N runs/stk/ethylamine.xyz
```

Output: JSON on stdout and the requested molecule file.

### `stk export-xyz`

Purpose: export a molecule file to XYZ with stk/RDKit fallback.

```bash
cspilot stk export-xyz molecule.mol runs/stk/molecule.xyz
```

Output: JSON on stdout and the requested XYZ file.

## GreenCatAI Commands

### `greencatai design-mbh`

Purpose: call the stable GreenCatAI MBH catalyst-design API from cspilot. GreenCatAI must be installed in the active environment.

```bash
cspilot greencatai design-mbh \
  --search-space /path/to/search_space.json \
  --scoring /path/to/scoring.json \
  --output-dir runs/mbh_api \
  --generations 3 \
  --population-size 30 \
  --top-n-xtb 0 \
  --top-n-orca 0
```

Output: JSON on stdout and GreenCatAI artifacts such as `mbh_seeds.json`, `mbh_scored.json`, `mbh_ga.json`, and `summary.json` in the output directory. The native GreenCatAI equivalent is `greencatai design-mbh ...`.

## AGAPI And Agent Commands

### `search`

Purpose: answer a general natural-language chemistry/materials question through the AGAPI-backed general agent. A quoted unknown root command such as `cspilot "what is the chemical space?"` is routed here.

```bash
cspilot search "what is the chemical space?" --workdir runs/search-space
```

Output: `<workdir>/agent_result.json`.

### `docs-check`

Purpose: run lightweight documentation consistency checks.

```bash
cspilot docs-check
```

Output: terminal pass/fail report.

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
