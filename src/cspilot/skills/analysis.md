# Stored results

## Planner
For stored-property requests find the requested result JSON, then query its property.
For Multiwfn requests use multiwfn_analysis_tool on a supplied GBW, Molden or FCH file.
Supported analyses are mulliken/hirshfeld charges and mayer bond orders.
Do not launch new DFT calculations from this profile; ask for a wavefunction if absent.
If the value is absent, report not found. Return the source filename with the value.

## Reporter
- field: property
- field: value
- field: unit
- field: source_file
- field: atomic_charges
- field: bond_order_matrix
