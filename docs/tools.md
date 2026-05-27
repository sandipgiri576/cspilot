# Tools

This page describes implemented Python and agent tools. Not every Python
function is a standalone CLI command.

## Structure Tools

Module: `cspilot.tools.ase_tools`

| Function | Behavior |
| --- | --- |
| `load_structure` | Read a structure with ASE. |
| `save_structure` | Write a structure with ASE. |
| `summarize_structure` | Return formula, atom count, cell, PBC, and center of mass. |

Agent wrapper: `inspect_structure`.

## Molecule Conversion Tools

Module: `cspilot.tools.mol_tools`

| Function | Behavior |
| --- | --- |
| `molecule_name_to_smiles` | Resolve a name using PubChem. |
| `validate_smiles` | Validate and canonicalize a SMILES string with RDKit. |
| `canonicalize_smiles` | Return canonical RDKit SMILES. |
| `smiles_to_xyz` | Embed conformers with ETKDGv3, minimize with MMFF or UFF, and write the lowest-energy XYZ conformer. |
| `molecule_name_to_xyz` | Combine PubChem lookup and RDKit XYZ generation. |

These are exposed to the direct agent as tools; there are currently no
standalone molecule-conversion CLI subcommands.

## xTB Tools

Module: `cspilot.tools.xtb_tools`

| Function | Behavior |
| --- | --- |
| `optimize_with_xtb` | Execute `XTB_COMMAND <input> --opt --chrg ... --uhf ...` and return expected optimization paths. |

CLI: `xtb-opt`. Agent wrapper: `run_xtb_optimize`.

xTB single-point calculation is not currently implemented.

## ORCA And OPI Tools

Module: `cspilot.tools.opi_orca_tools`

| Function | Behavior |
| --- | --- |
| `orca_single_point` | Create and execute an OPI ORCA SP job. |
| `orca_optimize` | Create and execute an OPI ORCA optimization job. |
| `orca_frequency` | Create and execute an OPI ORCA frequency job. |
| `parse_orca_result` | Parse with OPI where possible and fill missing supported values from ORCA text. |
| `single_point_with_orca` | Adapter used by `orca-sp`. |

The parser can report returned final energy, orbital-gap data, dipole,
zero-point energy, Gibbs free energy, enthalpy, entropy, and IR data when
available in successful output. It does not synthesize missing properties.

## MACE Tools

Module: `cspilot.tools.mace_tools`

`optimize_with_mace` runs ASE BFGS with `MACECalculator`, writes an optimized
XYZ, trajectory, and log, and returns the MACE energy when successful. It
requires `mace-torch` and a model file.

CLI: `mace-opt`. Agent wrapper: `run_mace_optimize`.

## AGAPI Materials Tools

Module: `cspilot.tools.agapi_materials_tools`

`agapi_materials_query` optionally imports `AGAPIAgent` and delegates a
natural-language materials query through its prebuilt `query_sync` function.
It is available to planner/executor workflows in the `materials` profile and
for explicit materials requests in the `general` run profile.

## Result JSON Tools

Module: `cspilot.tools.result_tools`

| Function | Behavior |
| --- | --- |
| `find_result_json` | Recursively find supported run JSON records. |
| `load_result_json` | Load JSON from a supplied path. |
| `get_property_from_result` | Search nested results using supported aliases. |

Supported query aliases include Gibbs free energy, enthalpy, electronic/final
energy, HOMO-LUMO gap, and frequencies. Failure to find a property returns an
explicit error rather than a guessed value.
