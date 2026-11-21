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

## Coding Style

`AGENTS.md` is the authoritative engineering guide. In particular:

- annotate every function signature;
- document public functions, methods, and classes with clear docstrings;
- keep imports at module scope and organize them as standard-library,
  third-party, then internal imports;
- use local imports only for optional heavy dependencies or to avoid a
  documented circular dependency;
- keep deterministic chemistry functions independent of model orchestration;
- return JSON-serializable tool results with stable `success`, `tool`, `error`,
  and `metadata` fields at the registry boundary.

Before submitting a change, run:

```bash
uv run --extra dev ruff format --check src tests
uv run --extra dev ruff check src tests
uv run --extra dev pytest -q
```

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
