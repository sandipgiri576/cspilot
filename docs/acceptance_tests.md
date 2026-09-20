# Live acceptance checks

## Water and Multiwfn (2026-09-19)

Routine tests now use `tests/examples/input.xyz` (water). The installed local
Multiwfn 3.8 build was checked directly; no MCP service was involved.

| Check | Observed result |
| --- | --- |
| Water xTB -> ORCA r2SCAN-3c Opt Freq | Completed, converged, enthalpy/Gibbs/frequencies returned |
| Water FCH -> Mulliken/Hirshfeld/Mayer | All three numeric menu sequences completed and parsed |
| New water ORCA GBW -> orca_2mkl -> Multiwfn | All three analyses completed; original GBW preserved |
| Live single-agent DFT -> Multiwfn Mulliken | Verified; returned charges printed on screen |
| Live multiagent water inspection, two workers | Two isolated child histories/summaries; parent verified |

Local artifacts are under `runs/acceptance/water-thermo`, `water-gbw-multiwfn`,
`water-agent-multiwfn`, and `multi-water-final`. They are ignored runtime outputs,
not mandatory test fixtures. Unit tests mock model/subprocess boundaries.

Live testing also exposed provider summary-only responses and malformed task
schemas. Bounded structured-decision/schema retries were added; invalid plans
fail closed before calculations. Client connections are now closed before their
short-lived event loops to avoid shutdown tracebacks in terminal output.

## Earlier benzene checks (2026-09-17)

Checked on 2026-09-17 using the configured OpenRouter model, PubChem, and local
xTB/ORCA binaries. Default unit tests still mock remote services.

| Request | Observed behavior | Result |
| --- | --- | --- |
| what is the SMILES string of caffine? | Resolved caffeine via PubChem; no geometry calculation | Verified |
| what is the gibbs free enegy of benzene at orca with r2scan-3c | Generated XYZ, xTB preoptimization, ORCA Opt Freq | Verified |
| Optimize geometry and compute thermochemistry like Gibbs free energy, enthalpy, etc. | Asked for a molecule name, SMILES, or XYZ file | No calculation launched |
| Same optimization/thermochemistry request with benzene XYZ supplied | Native tool selection followed by xTB and ORCA Opt Freq | Verified |

Caffeine SMILES returned by PubChem:

```text
CN1C=NC2=C1C(=O)N(C(=O)N2C)C
```

Benzene at r2SCAN-3c with its method-defined basis, 298.15 K and 1 atm:

| Property | Parsed value |
| --- | --- |
| Electronic energy | -232.18315511772303 Eh |
| Gibbs free energy | -232.1098010846468 Eh |
| Enthalpy | -232.0776305917647 Eh |
| Significant imaginary frequencies below -20 cm^-1 | 0 |

Both completed benzene runs returned the same values in this environment.
These are observed outputs, not version-independent regression constants.

Local artifacts are under `runs/acceptance/caffeine-final/`,
`runs/acceptance/benzene-gibbs/`, `runs/acceptance/clarification-verified/`,
and `runs/acceptance/benzene-thermochemistry/`. Run directories are gitignored.
They include decisions, execution JSON, verification, reports, and external-program files.

The tests exposed missing tool registration, incorrect identifier verification,
stored-result routing for new thermochemistry, and model action-format issues.
Regression coverage is in `tests/test_request_acceptance.py`.
