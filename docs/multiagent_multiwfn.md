# Independent agents and Multiwfn

## Agent modes

Single-agent execution remains the default. `--agent-mode multi` retains the old
specialist router for compatibility. **`--multiagent`** selects the new graph:

```text
request -> decomposer -> independent child loops -> structured summaries
        -> deterministic aggregator -> verification -> report
```

Each child runs the existing plan/tool/observe/decide loop with its own history,
directory, verifier and report. It shares only the registered deterministic tools.
Generated output paths are confined to that child's workdir.
Children run serially by default to avoid oversubscribing external programs;
`--workers 2` permits two independent loops concurrently (maximum four).
There are at most eight children; `--max-steps` and `--max-retries` apply to each.
This can multiply both model usage and computation compared with one agent.

The decomposer chooses one of:

- `collection`: independently inspect/analyze/screen supplied molecules; return a
  labeled table of results. No cross-molecule total-energy ranking is implied.
- `reaction`: calculate each species, then sum stoichiometric contributions.
- `conformers`: compare user-supplied XYZ conformers of the same molecule using
  compatible ORCA energies; return relative energies in kJ/mol. It does not
  generate a conformer ensemble or prove that a global minimum was found.

Unsupported dependencies, phases, conditions, ambiguous inputs or excess jobs
block decomposition rather than creating speculative calculations. A failed child
prevents a successful aggregate. Child diagnostics remain available.

Artifacts at the parent directory: `decomposition.json`, `summaries.json`,
`aggregate.json`, `execution_result.json`, `verification_result.json`,
`final_state.json`, and `final_report.md`/`.html`. Child artifacts and
`summary.json` are under `subtasks/<safe-id>/`.
`decomposition_notes.json` records discarded model-invented missing reaction
inputs: with known species SMILES, the child generates a structure instead.
An explicitly user-named missing file still blocks; it is never silently replaced.
Provider/schema failures are reported concisely, with details in `decomposition_error.txt`.

## Water-first examples

Use the provided water geometry for quick checks without molecule-name lookup:

```bash
cspilot "Inspect tests/examples/input.xyz and print its formula" --workdir runs/water-inspect
cspilot "Optimize tests/examples/input.xyz and compute enthalpy and Gibbs energy with ORCA r2scan-3c" --workdir runs/water-thermo
cspilot "Independently inspect tests/examples/input.xyz twice, label jobs water_a and water_b. Do not calculate energies." --multiagent --workers 2 --workdir runs/water-independent
```

For different molecules, explicitly name each requested property. For conformer
comparison provide the actual existing paths, SMILES identity, charge and spin;
do not use water as an example of a meaningful conformer ensemble.

## General reaction thermochemistry

```bash
cspilot "Calculate gas-phase reaction enthalpy for CH4 + 2 O2 -> CO2 + 2 H2O with ORCA r2scan-3c at 298.15 K and 1 atm. Optimize and calculate frequencies for every species. O2 is triplet; all others are neutral singlets." --multiagent --workdir runs/combustion --max-steps 4
```

Every thermal child must return ORCA optimization **and frequencies**, not just
a single-point energy. O2 uses multiplicity 3 and xTB `uhf=2`.

The calculation is general, not hardcoded to methane:

```text
delta H = sum(product coefficient * H) - sum(reactant coefficient * H)
```

The same signed sum can be applied to Gibbs or electronic energy when explicitly
requested; these are labeled separately. The aggregator checks atom and charge
balance, electron-count/spin parity, declared species composition against the
calculated XYZ, charge/multiplicity, common method/basis, Eh units, and finite
values. Thermal results additionally require converged optimization, frequencies,
no significant imaginary modes, and common temperature/pressure.

Supported conditions in this first stage are gas phase, 298.15 K, 1 atm.
H2O is **water vapor**. This is not a liquid-water higher heating value; no phase
correction or experimental heat-of-combustion claim is made. Composition checks
do not prove isomer identity or that a conformer is the global minimum.

## Local Multiwfn

Configure executable paths in `.env.cspilot`:

```dotenv
ORCA_COMMAND=/path/to/orca
MULTIWFN_COMMAND=/path/to/Multiwfn_noGUI
ORCA_2MKL_COMMAND=/path/to/orca_2mkl
```

If `orca_2mkl` is not on PATH, CSPilot also looks beside the configured ORCA
executable. ORCA/OPI results now expose `files.gbw` and `files.output` when present.
For `.gbw`, the adapter copies the file into a fresh analysis directory and calls
`orca_2mkl wavefunction -molden`; it never modifies the original ORCA results.
Multiwfn reads the resulting Molden file. `.out` is not accepted as a wavefunction.

Natural-language example (single agent, no need for multiagent):

```bash
cspilot "Run ORCA r2scan-3c DFT on tests/examples/input.xyz, then use its GBW for Multiwfn Mulliken charges and print them" --workdir runs/water-charges
```

Model-free command, using an actual returned GBW path:

```bash
cspilot multiwfn /path/to/job.gbw --analysis hirshfeld --workdir runs/water-hirshfeld
```

### Validated numeric menu map

These sequences were tested with Multiwfn 3.8, build 2026-Jan-7. Input is an
allowlisted operation, never model-supplied menu text. One thread is requested,
subprocess calls have timeouts, and every run saves `menu.txt`, output/error logs,
exported values and `result.json`.

| Operation | Sequence after loading wavefunction | Export |
| --- | --- | --- |
| Mulliken charges | `7, 5, 1, y, 0, 0, q` | atomic `.chg` |
| Hirshfeld charges | `7, 1, 1, y, 0, q` | atomic `.chg`, built-in free-atom densities |
| Mayer bond orders | `9, 1, y, 0, q` | `bndmat.txt` |

Charge output is checked for finite values, atom count and total charge. Bond
matrices are checked for complete square finite data; Multiwfn's diagonal entries
are row sums, not self-bond orders. Charges are in elementary charge units;
bond orders are dimensionless. Nonzero exit status, missing exports, unexpected
version, timeout or parse failure returns `success=False`, never fabricated values.

The [reference agent description](https://lunyang.github.io/agents/multiwfn-agent/)
and local reference package informed the workflow only. No MCP integration or
reference implementation was copied. Its numeric maps were not trusted blindly:
the installed build uses `7,1` for Hirshfeld, not Mulliken.
RESP, cubes, orbital visualization, topology and other analyses remain unsupported.
When publishing Multiwfn results, follow the citation requirements in the installed
distribution and its output banner.
