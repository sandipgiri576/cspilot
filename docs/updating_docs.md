# Updating Documentation

Documentation must be updated with each user-facing change.

Every new tool, workflow, CLI command, or CLI flag must update:

- `README.md` if the feature is user-facing.
- `docs/tools.md` if a tool or agent wrapper changes.
- `docs/workflows.md` if a workflow changes.
- `docs/cli_usage.md` if a command, option, or output file changes.
- `docs/configuration.md` if an environment variable or external binary path
  changes.
- `docs/examples.md` if a new use case becomes possible.
- Tests that establish the documented behavior.

Also update:

- `docs/agent_usage.md` for planning, agent, profile, LangGraph, or reporting
  behavior.
- `docs/agapi.md` for AGAPI backend, model, or materials-query changes.
- `docs/safety.md` when execution boundaries or verification behavior changes.
- `docs/roadmap.md` when planned work becomes implemented or changes stage.
- `CHANGELOG.md` when it exists and the change is release-relevant.

## Accuracy Rules

- Inspect the source before documenting a command.
- Do not invent commands or output files.
- Mark planned features as planned.
- Keep examples copy-pasteable.
- Never include real API keys or private licensed-software paths.
