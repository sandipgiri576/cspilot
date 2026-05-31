# Agent Usage

## Deterministic Commands Versus Agent Mode

Use deterministic CLI commands when you know the operation and input file:

```bash
cspilot workflow xtb-orca-freq input.xyz --method r2scan-3c --basis def2-SVP
```

Use an agent command when the request needs interpretation, molecule input
conversion, materials querying, or property retrieval:

```bash
cspilot agent "gibbs free energy of water in ORCA r2scan-3c" \
  --workdir runs/water-agent --agent-profile chem
```

The direct agent can select tools and write `agent_result.json`. It does not
replace calculation programs or validate a scientific method choice.

## Planner And Executor

`plan`, `execute`, and `run` use a stricter JSON workflow:

1. The planner requests a JSON list of registered tools and arguments from the
   AGAPI model.
2. The executor rejects names outside the selected profile allowlist.
3. Each tool result is written as JSON.
4. `run` verifies returned paths and numeric property fields and writes a
   report.

```bash
cspilot run "Find all Al2O3 materials" --workdir runs/al2o3 \
  --profile materials --html
```

`--html` belongs to `run`; it writes `final_report.html`.

## AGAPI Backend Selection

Agent and planning calls need:

```dotenv
AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b
```

The direct `agent` command can override model and base URL:

```bash
cspilot agent "inspect input.xyz" --workdir runs/check \
  --model openai/gpt-oss-20b --base-url https://atomgpt.org/api
```

## Profiles

`agent --agent-profile` currently accepts:

| Profile | Purpose |
| --- | --- |
| `chem` | Chemistry calculation, molecular input, stk, and GreenCatAI catalyst tools |
| `materials` | Materials-oriented direct-agent instructions with local chemistry, stk, and GreenCatAI tools |
| `general` | No registered direct-agent calculation tools |

`plan`, `execute`, and `run --profile` accept:

| Profile | Executor allowlist |
| --- | --- |
| `chem` | ASE/xTB/ORCA/MACE chemistry tools plus stk and GreenCatAI wrappers |
| `materials` | AGAPI materials-query wrapper and GreenCatAI catalyst wrapper |
| `analysis` | Result JSON search/property tools |
| `thermo` | Result JSON search/property tools |
| `general` | No calculation tools; materials query is permitted only when explicitly requested during `run` planning |

## Agent Rules

The implemented prompts and executor are designed to enforce these rules:

- Use only provided or allowlisted tools.
- Never invent structures, energies, files, or property values.
- Prefer the fixed xTB to ORCA single-point workflow where applicable.
- Use the xTB to ORCA frequency workflow for a new Gibbs free-energy request
  in direct chem agent mode.
- Search previous JSON output for requested existing properties.
- Report unsupported behavior or absent properties clearly.

Agent results remain dependent on external executables, external API responses,
and the quality of the chosen computational method.

## General Search Shortcut

A quoted root-level question is routed to the same general agent used by `search`:

```bash
cspilot "what is the chemical space?"
```

This requires the AGAPI environment variables and does not register calculation tools.
