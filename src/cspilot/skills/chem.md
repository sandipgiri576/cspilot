# Chemistry

## Planner
For a SMILES-only question call molecule_name_to_smiles_tool, then finish.
Do not generate geometry or launch calculations for identifier questions.
Resolve obvious spelling mistakes such as "caffine" to caffeine and identify the
resolved molecule in the returned result.
Use an existing structure first. For SMILES generate XYZ; for names resolve then generate XYZ.
Use stk only when construction or editing is requested.
Choose individual tools or a combined workflow according to the requested calculation.
For frequency/thermochemistry use the frequency workflow, not a single-point job.
Use run_xtb_orca_frequency_workflow for new Gibbs energy or enthalpy calculations;
it optimizes at ORCA level before frequencies. Query existing JSON only if requested.
If a calculation request gives neither molecule nor geometry, mark blocked and ask
for that input. Do not infer a molecule from arbitrary files in the work directory.
After each calculation inspect the actual geometry path and parsed properties.

## Reporter
- field: final_energy_hartree
- field: energy_unit
- field: frequencies
- field: gibbs_free_energy
