# Updating Documentation

Documentation is part of a user-facing change. Every time a function, tool,
workflow, command, or configurable integration is added or changed:

- Update `README.md` when the capability is user-facing.
- Update `docs/tools.md` for each new or changed tool.
- Update `docs/workflows.md` for each new or changed workflow.
- Update `docs/cli_usage.md` for each new or changed CLI command or option.
- Update `docs/configuration.md` for each new or changed environment variable.
- Update `docs/examples.md` when a new use case becomes possible.
- Add or update tests that establish the documented behavior.
- Add a changelog entry when `CHANGELOG.md` exists.

## Accuracy Rules

- Read implementation code before documenting an interface.
- Do not publish commands, environment variables, files, or outputs that are
  not implemented.
- Clearly label roadmap work as planned.
- Never place real API keys, licensed-software data, or private paths in
  documentation examples.
