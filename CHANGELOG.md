# Changelog

## Unreleased

- Added opt-in `--multiagent` decomposition, isolated child loops, bounded concurrency,
  structured summaries and deterministic reaction/conformer aggregation.
- Guarded reaction sums with atom/charge balance, spin, method, units and frequency checks.
- Added local Multiwfn 3.8 Mulliken/Hirshfeld charges and Mayer bond orders, validated
  menu maps, isolated GBW conversion, JSON outputs and a model-free CLI command.
- Exposed ORCA/OPI GBW artifacts for wavefunction handoff and used water in routine examples.
- Closed model clients before short-lived event loops exit; bounded schema/decision
  recovery and unambiguous observed-path repairs address live provider failures.

- Routed bare prompts to the tool agent and registered PubChem SMILES lookup.
- Used native action tool schemas and handled empty/plain clarification responses.
- Distinguished new thermochemistry from stored-result queries.
- Ran ORCA Opt Freq for thermochemistry with the composite method's own basis.
- Verified requested thermochemistry and removed XYZ requirements from SMILES lookup.
- Displayed concise answers without unrelated absent-property warnings.

- Added bundled domain Markdown skills and automatic planner/reporter loading.
- Replaced the run/graph-run fixed chain with bounded observation-driven tool decisions.
- Persisted per-action decisions and verification feedback.
- Displayed full reports and queried values in terminals, including HTML-save mode.
- Removed the catalyst-design integration and its CLI/tool registration.

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [v0.1]

### Added common tools

- Direct CLI tools
- ASE + xTB + OPI/ORCA + MACE

## [v0.2]

### Added Fixed workflows

- xTB opt → ORCA SP
- MACE opt → ORCA SP
- xTB opt → ORCA freq
