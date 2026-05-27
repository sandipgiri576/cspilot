# Development

## Local Setup

```bash
uv sync --extra dev
uv run --extra dev pytest -q
uv run --extra dev ruff check src tests
```

The package uses a `src/` layout; the Typer entry point is
`cspilot.cli:app`.

## Design Boundaries

- Deterministic tools perform file and executable work.
- Workflows compose existing deterministic tools.
- Agent tools wrap implemented functions and return JSON-serializable data.
- The planner emits JSON tool plans; the executor runs only registered tools.
- The verifier and reporter inspect returned data without using an LLM to
  create scientific values.

## Adding Capabilities

When adding a tool or workflow:

1. Keep external execution in deterministic Python code.
2. Return explicit status, paths, and parsed values.
3. Add agent exposure only when the deterministic implementation is stable.
4. Add tests for failure states and result serialization.
5. Update documentation according to [Updating Documentation](updating_docs.md).

## Documentation

Documentation dependencies are available through:

```bash
uv sync --extra docs
```

The user-facing pages in `docs/` should describe only implemented commands and
mark roadmap work as planned.
