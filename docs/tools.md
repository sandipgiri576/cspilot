# Tools

This page describes implemented Python tools and agent wrappers in
`src/cspilot/tools/`.

## ASE

Module: `ase_tools.py`

| Function | Purpose |
| --- | --- |
| `load_structure` | Read a structure with ASE. |
| `save_structure` | Write a structure with ASE. |
| `summarize_structure` | Return formula, atom count, cell, PBC, and center of mass. |

Agent wrapper: `inspect_structure`.

## Molecule Conversion

Module: `mol_tools.py`

| Function | Purpose |
| --- | --- |
| `molecule_name_to_smiles` | PubChem name lookup. |
| `validate_smiles` | RDKit SMILES validation. |
| `canonicalize_smiles` | RDKit canonical SMILES. |
| `smiles_to_xyz` | RDKit ETKDG conformer generation and MMFF/UFF minimization. |
| `molecule_name_to_xyz` | PubChem name lookup followed by RDKit XYZ generation. |

Agent wrappers include `molecule_name_to_smiles_tool`, `smiles_to_xyz_tool`,
`molecule_name_to_xyz_tool`, `validate_smiles_tool`, and
`canonicalize_smiles_tool`.

## stk

Module: `stk_tools.py`

| Function | Purpose |
| --- | --- |
| `stk_build_from_smiles` | Build an stk/RDKit molecule from SMILES and write `.mol`, `.sdf`, or `.xyz`. |
| `stk_building_block_from_file` | Load an stk building block from a molecule file. |
| `stk_linear_polymer_from_smiles` | Construct a linear polymer with a whitelisted stable path. |
| `stk_construct_cage_from_smiles` | Returns a clear unsupported result for cage topologies until safe presets are implemented. |
| `rdkit_replace_substructure` | RDKit-based molecule editing. |
| `stk_export_to_xyz` | Export molecule files to XYZ with stk/RDKit/ASE fallback. |

CLI commands: `stk-build-smiles`, `stk-polymer`, `stk-xtb`, and the `stk`
subcommands.

## xTB

Module: `xtb_tools.py`

| Function | Purpose |
| --- | --- |
| `optimize_with_xtb` | Run xTB geometry optimization through the configured command. |

CLI: `xtb-opt`. Agent wrapper: `run_xtb_optimize`.

## ORCA / OPI

Module: `opi_orca_tools.py`

| Function | Purpose |
| --- | --- |
| `orca_single_point` | OPI ORCA single point. |
| `orca_optimize` | OPI ORCA optimization. |
| `orca_frequency` | OPI ORCA frequency. |
| `parse_orca_result` | OPI parsing plus fallback text parsing. |
| `single_point_with_orca` | CLI adapter for `orca-sp`. |

Parsed values may include energies, orbital data, dipole, thermochemistry, and
frequencies when those values exist in ORCA output. Missing values are not
invented.

## MACE

Module: `mace_tools.py`

| Function | Purpose |
| --- | --- |
| `optimize_with_mace` | ASE optimization with `MACECalculator`. |

CLI: `mace-opt`. Agent wrapper: `run_mace_optimize`.

## AGAPI Materials

Module: `agapi_materials_tools.py`

| Function | Purpose |
| --- | --- |
| `agapi_materials_query` | Optional wrapper around AGAPI prebuilt materials query. |

Agent wrapper: `agapi_materials_query_tool`.

## Result Tools

Module: `result_tools.py`

| Function | Purpose |
| --- | --- |
| `find_result_json` | Recursively find result JSON files. |
| `load_result_json` | Load a JSON result file. |
| `get_property_from_result` | Find a property through recursive lookup and aliases. |

Agent wrappers: `find_result_json_tool`, `get_property_from_result_tool`, and
name-overridden direct-agent variants.

## NWPESSe

Module: `nwpesse_tools.py`

Implemented helpers parse fragment formulas, generate validated box configs,
write `mol.cluster` and `mol.inp`, run the external NWPESSe binary, parse
candidate XYZ second-line energies, and copy the lowest-energy structure.

CLI: `nwpesse-search`. Agent wrapper: `nwpesse_global_minimum_search_tool`.

## GreenCatAI

Module: `greencatai_tools.py`

`greencatai_design_mbh_catalysts` calls the installed GreenCatAI MBH design API
when available.

CLI: `greencatai design-mbh`. Agent wrapper: `design_mbh_catalysts_tool`.
