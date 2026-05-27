# Examples

The examples assume installation is complete and `.env.cspilot` contains paths
for any external programs being used.

## Inspect An XYZ File

```bash
cspilot inspect tests/examples/input.xyz
```

Result: a structure table in the terminal and
`runs/<timestamp>-inspect/result.json`.

## Generate XYZ From A Molecule Name

Molecule conversion is currently an agent tool rather than a standalone CLI
subcommand:

```bash
cspilot agent "Create an XYZ file for water at runs/water-agent/water.xyz" \
  --workdir runs/water-agent --agent-profile chem
```

This requires AGAPI and PubChem access. For a deterministic Python call:

```bash
python -c "from cspilot.tools.mol_tools import molecule_name_to_xyz; print(molecule_name_to_xyz('water', 'runs/water.xyz'))"
```

## Optimize With xTB

```bash
cspilot xtb-opt tests/examples/input.xyz --charge 0 --uhf 0
```

Result: `result.json` and, when xTB succeeds, `xtbopt.xyz`.

## Run An ORCA Single Point

```bash
cspilot orca-sp tests/examples/input.xyz --method r2scan-3c \
  --basis def2-SVP --charge 0 --mult 1
```

Result: `result.json`, `job.inp`, and `job.out` after successful ORCA
execution.

## xTB To ORCA Workflow

```bash
cspilot workflow xtb-orca-sp tests/examples/input.xyz --charge 0 --mult 1 \
  --method r2scan-3c --basis def2-SVP
```

For a thermochemistry-capable frequency calculation:

```bash
cspilot workflow xtb-orca-freq tests/examples/input.xyz --charge 0 --mult 1 \
  --method r2scan-3c --basis def2-SVP
```

Result: `workflow_result.json`, with parsed properties only when present in
successful ORCA output.

## Query AGAPI Materials

```bash
cspilot run "Find all Al2O3 materials" --workdir runs/al2o3 \
  --profile materials --html
```

Result: plan, step and execution JSON files, verification JSON, and
`runs/al2o3/final_report.html`.

## Extract A Property From Existing JSON Results

Using the analysis planner/executor profile:

```bash
cspilot run "Find the Gibbs free energy in runs/water-freq/workflow_result.json" \
  --workdir runs/water-analysis --profile analysis
```

Or call the deterministic Python function directly:

```bash
python -c "from cspilot.tools.result_tools import get_property_from_result; print(get_property_from_result('runs/water-freq/workflow_result.json', 'gibbs free energy'))"
```

If Gibbs free energy was not present in the selected JSON, the result reports
that it was not found.
