# Agent Usage

## Deterministic Tools

Deterministic commands call local Python functions and external binaries
directly:

```bash
cspilot inspect tests/examples/input.xyz
cspilot xtb-opt tests/examples/input.xyz
cspilot workflow xtb-orca-sp tests/examples/input.xyz
```

Use these when you already know the exact calculation.

## Direct AGAPI Agent

`cspilot agent` runs an AGAPI/OpenAI-compatible tool-using agent:

```bash
cspilot agent "inspect tests/examples/input.xyz" \
  --workdir runs/agent_test --agent-profile chem
```

It supports `--model`, `--base-url`, and `--agent-profile
chem|materials|general`. Tool calls are still restricted to provided tools.

## Planner and Executor

`plan`, `execute`, and `run` provide a stricter JSON workflow:

1. AGAPI creates a JSON plan.
2. The executor accepts only registered tools for the selected profile.
3. Step results are written as JSON.
4. Verification checks paths, success flags, and numeric values.
5. A Markdown or HTML report is generated.

```bash
cspilot run "inspect tests/examples/input.xyz" --workdir runs/run_test --profile chem
```

## LangGraph

`graph-run` wraps the same planner, executor, verifier, and reporter in a
LangGraph graph.

Single mode:

```text
planner -> executor -> verifier -> reporter
```

```bash
cspilot graph-run "inspect tests/examples/input.xyz" \
  --workdir runs/water --profile chem --agent-mode single
```

Multi mode:

```text
router -> planner -> executor -> verifier -> reporter
```

```bash
cspilot graph-run "Find all Al2O3 materials" \
  --profile auto --agent-mode multi --html --workdir runs/al2o3
```

Multi-agent mode means deterministic specialist routing. It does not spawn
parallel autonomous agents.

## Profiles

Planner/graph profiles include:

| Profile | Role |
| --- | --- |
| `chem` | ASE, molecule conversion, xTB, ORCA, MACE, stk, NWPESSe, GreenCatAI |
| `stk` | stk-focused planning with chemistry tools available for follow-up calculations |
| `materials` | AGAPI materials query and GreenCatAI catalyst tools |
| `analysis` | result JSON search and property extraction |
| `thermo` | result JSON thermochemistry extraction |
| `general` | no calculation tools unless explicit materials query rules apply |
| `auto` | graph multi-mode router selects a specialist |

## Repair Mode

`src/cspilot/agents/repair.py` implements a repair helper for missing-file
handoffs and AGAPI repair fallback. The current `graph-run` integration uses
the clean single or routed multi graph without a repair node. Treat repair as
available implementation groundwork, not a current CLI mode.

## Pretty, HTML, and Quiet Output

`run` and `graph-run` support:

```bash
--pretty / --no-pretty
--quiet
--html
```

- `--pretty` prints Rich panels and tables. It is the default.
- `--no-pretty` prints the older simple terminal output.
- `--quiet` prints only verification status and report path.
- `--html` writes `final_report.html`; otherwise `final_report.md` is written.

JSON files are always written regardless of terminal style.

## Interactive Mode

No interactive REPL mode is currently implemented. The CLI accepts explicit
commands and natural-language request strings.
