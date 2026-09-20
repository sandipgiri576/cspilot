# Workflows

`run` and `graph-run` now choose tools iteratively from observed outputs.
The fixed workflows below remain independently callable and may be selected as
one action by the agent. Decisions and observations are saved alongside results.

`--multiagent` adds independent child loops and deterministic reaction/conformer
aggregation without changing these tools. See [multi-agent and Multiwfn](multiagent_multiwfn.md)
for supported conditions, per-child artifacts, GBW handoffs and menu maps.

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

The ORCA stage runs `Opt Freq` after xTB preoptimization, so frequencies are
computed at the geometry optimized with the requested ORCA method. For r2SCAN-3c
the method-defined basis is used; an extra def2-SVP keyword is not added.
Gibbs free energy, enthalpy, frequencies, temperature, and pressure are reported
only when parsed. Verification checks optimization convergence, required
thermochemistry, and significant imaginary modes (below -20 cm^-1).
See the [ORCA optimization/frequency example](https://www.faccts.de/docs/orca/6.1/tutorials/spec/IR.html).

## MACE to ORCA

```bash
cspilot workflow mace-orca tests/examples/input.xyz \
  --model /path/to/model.model --charge 0 --mult 1
```

Requires `mace-torch` and a valid MACE model. If `--model` is omitted, the
workflow uses `MACE_MODEL`.

## stk to xTB

```bash
cspilot stk-xtb "O" --workdir runs/stk_xtb --charge 0 --uhf 0
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
cspilot graph-run "use stk to build water from SMILES O then run xTB and ORCA single point" \
  --workdir runs/stk_orca --profile chem --agent-mode single
```

The planner should create an stk build step producing an XYZ, then pass that
same XYZ into the xTB to ORCA workflow tool.

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
