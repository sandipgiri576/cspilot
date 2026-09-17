# Thermochemistry

## Planner
For a NEW Gibbs free energy, enthalpy, or thermochemistry request, create a geometry
if absent and call run_xtb_orca_frequency_workflow with the requested method.
That tool performs xTB preoptimization then ORCA optimization AND frequencies.
Never substitute a single-point calculation for thermochemistry.
Only query stored results if the user names a result file or asks for previous results.
Default method is r2scan-3c, charge 0, multiplicity 1; clearly report actual settings.
If neither molecule nor structure is specified, mark blocked and ask for the molecule
or XYZ filename. Do not invent a molecule or scan unrelated work directories.
Do not infer missing Gibbs energy or enthalpy from electronic energy.

## Reporter
- field: enthalpy
- field: gibbs_free_energy
- field: value
- field: unit
