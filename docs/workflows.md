# Workflows

## xTB Optimization

```bash
cspilot xtb-opt tests/examples/input.xyz --charge 0 --uhf 0
```

Inputs: XYZ file, charge, UHF count.

Outputs: timestamped run directory, copied input, `result.json`, and xTB output
files such as `xtbopt.xyz` when xTB succeeds.

## ORCA Single Point 

```bash
cspilot orca-sp tests/examples/input.xyz \
  --method r2scan-3c --basis def2-SVP --charge 0 --mult 1
```

Inputs: XYZ file, method, basis, charge, multiplicity.

Outputs: timestamped run directory, `result.json`, ORCA input/output files, and
parsed properties when present in ORCA output.

## xTB to ORCA Single Point

```bash
cspilot workflow xtb-orca-sp tests/examples/input.xyz \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

Steps:

1. Copy input XYZ.
2. Run xTB optimization in `01_xtb_opt/`.
3. Use optimized XYZ for ORCA SP in `02_orca_sp/`.
4. Write `workflow_result.json`.

## xTB to ORCA Frequency

```bash
cspilot workflow xtb-orca-freq tests/examples/input.xyz \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

The second ORCA step is a frequency job. Gibbs free energy, enthalpy,
frequencies, and related values are reported only when parsed from output.

## MACE to ORCA

```bash
cspilot workflow mace-orca tests/examples/input.xyz \
  --model /path/to/model.model --charge 0 --mult 1
```

Requires `mace-torch` and a valid MACE model. If `--model` is omitted, the
workflow uses `MACE_MODEL`.

## stk to xTB

```bash
cspilot stk-xtb "c1ccccc1" --workdir runs/stk_xtb --charge 0 --uhf 0
```

Steps:

1. Build a molecule from SMILES.
2. Export XYZ.
3. Run xTB optimization.
4. Save `workflow_result.json`.

## stk to xTB to ORCA

There is no fixed deterministic `stk-to-xtb-orca` CLI command yet. Use the
planner/graph path:

```bash
cspilot graph-run "use stk to build benzene from SMILES c1ccccc1 then run xTB and ORCA single point" \
  --workdir runs/stk_orca --profile chem --agent-mode single
```

The planner should create an stk build step producing an XYZ, then pass that
same XYZ into the xTB to ORCA workflow tool.

## AGAPI Materials Query

```bash
cspilot graph-run "Find all Al2O3 materials" \
  --profile auto --agent-mode multi --html --workdir runs/al2o3
```

This uses the materials profile when routed successfully and records AGAPI
response content in JSON. It does not run local DFT.

## Result JSON Extraction

```bash
cspilot run "extract Gibbs free energy from the latest result JSON in runs/water" \
  --workdir runs/query --profile analysis
```

The result tools search stored JSON and return matching properties by alias.
If a property is absent, reports say it was not found in parsed results.

## NWPESSe Global-Minimum Search

```bash
cspilot nwpesse-search "(h2o)4Mg" \
  --workdir runs/h2o4mg --max-calculations 10 --box-size 3.0
```

Outputs include `mol.cluster`, `mol.inp`, external run logs,
`workflow_result.json`, candidate XYZ files, and `lowest_energy.xyz` when a
valid lowest-energy structure is parsed.
