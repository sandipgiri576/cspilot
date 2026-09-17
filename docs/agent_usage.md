# Agent Usage

## Iterative agent

Both `run` and `graph-run` use a bounded LangGraph action loop. OpenRouter
chooses one structured action at a time using the original request, tool
descriptions and schemas, domain skills, and all prior observations.

```text
planner -> decide -> tool -> observe -> planner
              |
              +-> verifier -> reporter
```

The planner can choose another tool, finish, or mark the request blocked.
Observations contain real tool outputs and deterministic verification feedback.
A later action can reuse a returned path or change its arguments after failure.
No separate model-generated shell or Python is executed.

```bash
cspilot run "inspect tests/examples/input.xyz and print its formula" --workdir runs/inspect
cspilot graph-run "build benzene from SMILES c1ccccc1 with stk" \
  --profile auto --agent-mode multi --max-steps 8 --workdir runs/benzene
```

`--max-steps` defaults to 8 tool calls; one final decision may follow the last
call. `--max-retries` defaults to 1: after the first failed/unverified call the
model may recover; after the second, no more tools execute. Successful steps
are not replayed. A limit, blocked request, missing results, or model error
produces an incomplete/failed report. Historical failures remain visible and
keep overall verification conservative even if a later action succeeds.
Finish is the model's completion decision; deterministic verification checks
returned artifacts, not full semantic fulfillment of the user's request.

`multi` adds a deterministic profile router before the same agent loop.
It does not create parallel autonomous agents.

## Domain skills

`src/cspilot/skills/` contains bundled Markdown files and is included in package
distributions. `SkillLoader` automatically loads `common.md` plus
`<profile>.md` on each request. Each file has `## Planner` and `## Reporter`
sections. The planner section is appended to its instructions; reporter entries
such as `- field: value` select additional returned fields for deterministic
rendering. Markdown is guidance, never executable code or permission to add tools.

Edit a profile file to refine guidance without changing orchestration. To test
another directory in Python, use `SkillLoader(directory)`. Missing domain files
fall back to common guidance. Adding a new profile also requires an explicit
profile/tool allowlist; a Markdown file cannot expand execution permissions.

The reporter remains deterministic and does not ask a model to invent or rewrite
scientific results. More elaborate report templates can be added later.

## Profiles

| Profile | Available scope |
| --- | --- |
| chem | ASE, conversion, xTB, ORCA, MACE, stk, NWPESSe, stored results |
| stk | Construction/editing, chemistry calculations, stored results |
| analysis | Result JSON search and property extraction |
| thermo | New ORCA optimization/frequency calculations and stored thermochemistry extraction |
| materials | No database tool currently available; queries are unsupported |
| general | No calculation tools; use search for general explanations |
| auto | Select a specialist with graph-run --agent-mode multi |

## Saved plans and direct tools

`plan` still generates a complete saved JSON plan; `execute` runs such a plan
deterministically. Fixed `workflow` commands remain independently usable.
The iterative agent may select a combined workflow as one tool when suitable.

`agent` retains the direct Agents SDK tool-calling interface and
`--agent-profile chem|materials|general`. For the persisted LangGraph observation
loop and limits use `run` or `graph-run`. General explanations use `search`.

## Reports and artifacts

Each loop run saves `plan.json` (actions actually attempted),
`decision_NNN.json`, `step_NNN_result.json`, `observations.json` after tool calls,
`execution_result.json`, `verification_result.json`, `final_state.json`, and
`final_report.md` or `final_report.html`.
Decisions store short action summaries, not hidden reasoning.

An answer-focused summary of returned values and verification prints by default.
The full plan, file inventory, and diagnostic report remain saved.
`--no-pretty` prints plain text; `--html` saves the full HTML report and still
prints the answer. `--quiet` suppresses result details. JSON is always saved.
Python callers receive state and saved artifacts; only CLI presentation prints.

The standalone `repair.py` helper remains available, but graph recovery is now
driven by the next decision receiving failure observations.

## Identifiers and new thermochemistry

Bare quoted prompts now use the same tool agent as `run`.
SMILES questions use the PubChem name lookup without generating XYZ or energies.
For a new Gibbs/enthalpy request the agent generates a structure if needed and
selects the frequency workflow. Explicit previous-result/JSON requests use analysis.
An optimization request without a molecule or geometry asks for that input.

The decision model receives native function schemas. Selection callbacks only
record the next action; the shared executor performs the actual calculation.
This avoids confusing JSON-plan text with real function calls. A successful
geometry-generation step alone cannot satisfy a thermochemistry request.
