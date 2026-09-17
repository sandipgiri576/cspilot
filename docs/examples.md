# Examples

## Natural-language acceptance examples

```bash
cspilot "what is the SMILES string of caffeine?" --workdir runs/caffeine
cspilot "what is the Gibbs free energy of benzene at ORCA with r2scan-3c" --workdir runs/benzene
cspilot "Optimize benzene geometry and compute thermochemistry with ORCA r2scan-3c" --workdir runs/benzene-thermo
```

Use a molecule name, SMILES, or XYZ path for new calculations. Without one the
agent requests input. New thermochemistry runs optimization and frequencies;
it does not report a single-point electronic energy as Gibbs energy.

## Display a stored property

```bash
cspilot run "print Gibbs free energy from runs/water/result.json on screen" \
  --profile analysis --workdir runs/query --max-steps 4
```

Returned values print in full and remain saved as JSON. Add `--html` to save
an HTML report as well; use `--quiet` only when result details are unwanted.

Examples assume CSPilot is installed and `.env.cspilot` is configured for any
external programs being used.

## Inspect XYZ

```bash
cspilot inspect tests/examples/input.xyz
```

LangGraph equivalent:

```bash
cspilot graph-run "inspect examples/water.xyz" --workdir runs/water
```

If `examples/water.xyz` is not present, use `tests/examples/input.xyz`.

## Molecule Name to XYZ

Direct agent:

```bash
cspilot agent "Create an XYZ file for water at runs/water_agent/water.xyz" \
  --workdir runs/water_agent --agent-profile chem
```

Python deterministic call:

```bash
python -c "from cspilot.tools.mol_tools import molecule_name_to_xyz; print(molecule_name_to_xyz('water', 'runs/water.xyz'))"
```

## xTB Optimization

```bash
cspilot xtb-opt tests/examples/input.xyz --charge 0 --uhf 0
```

## ORCA Single Point

```bash
cspilot orca-sp tests/examples/input.xyz \
  --method r2scan-3c --basis def2-SVP --charge 0 --mult 1
```

## xTB to ORCA

```bash
cspilot workflow xtb-orca-sp tests/examples/input.xyz \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

Frequency workflow:

```bash
cspilot workflow xtb-orca-freq tests/examples/input.xyz \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

## stk Build and xTB

```bash
cspilot stk-build-smiles "c1ccccc1" --workdir runs/stk_benzene
```

```bash
cspilot stk-xtb "c1ccccc1" --workdir runs/stk_xtb
```

Graph request:

```bash
cspilot graph-run "use stk to build benzene from SMILES c1ccccc1 and optimize with xTB" \
  --workdir runs/stk_benzene
```

## stk to xTB to ORCA

```bash
cspilot graph-run "use stk to build benzene from SMILES c1ccccc1 then run xTB and ORCA single point" \
  --workdir runs/stk_orca
```

This is a planned/executed agent workflow path, not a fixed deterministic
`workflow` subcommand.

## Result JSON Property Extraction

```bash
cspilot run "extract Gibbs free energy from the latest result JSON in runs/water" \
  --workdir runs/query --profile analysis
```

## NWPESSe

```bash
cspilot nwpesse-search "(h2o)4Mg" \
  --workdir runs/h2o4mg --max-calculations 10 --box-size 3.0
```

## Quiet and HTML Reports

```bash
cspilot graph-run "inspect tests/examples/input.xyz" --workdir runs/water --quiet
cspilot graph-run "inspect tests/examples/input.xyz" --workdir runs/water-html --html
```
