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

## stk Molecule Construction Tools

Module: `cspilot.tools.stk_tools`

| Function | Behavior |
| --- | --- |
| `stk_building_block_from_smiles` | Create an `stk.BuildingBlock` from SMILES and export `.mol`, `.sdf`, or `.xyz`. |
| `stk_building_block_from_file` | Load a building block with `stk.BuildingBlock.init_from_file`. |
| `stk_construct_linear_polymer` | Build a linear polymer with `stk.polymer.Linear` when `stk` is installed. |
| `stk_construct_simple_cage` | Build only whitelisted cage topologies; currently `four_plus_six`. |
| `stk_edit_replace_smiles` | Replace a substructure with RDKit and export the edited molecule. |
| `stk_export_to_xyz` | Export a molecule file to XYZ with stk/RDKit fallback. |

The stk dependency is optional. Missing `stk` or unsupported topology names return JSON errors; arbitrary Python and arbitrary topology lookup are not exposed. These functions are available through `cspilot stk ...` CLI commands and agent tools.

## GreenCatAI Catalyst Tools

Module: `cspilot.tools.greencatai_tools`

`greencatai_design_mbh_catalysts` calls the public GreenCatAI API:

```python
from greencatai.api import design_mbh_catalysts
```

It supports MBH catalyst-design parameters from the GreenCatAI cspilot interface, including `search_space`, `scoring`, `library`, `max_candidates`, `generations`, `population_size`, `top_n_xtb`, and `top_n_orca`. It is available as `cspilot greencatai design-mbh ...` and as an agent tool. GreenCatAI remains responsible for catalyst libraries, scaffold rules, filters, scoring, and future design logic.

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
