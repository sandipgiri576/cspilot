# AGAPI Integration

CSPilot can use AGAPI through OpenAI-compatible clients and optional prebuilt
AGAPI tools. For normal planner/agent model calls, OpenRouter is currently the
recommended default; AGAPI model serving is opt-in.

## Configuration

```dotenv
AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-oss-20b:free
CSPILOT_LLM_PROVIDER=openrouter
```


## OpenRouter-First Backend

For normal `search`, `agent`, `plan`, `run`, and `graph-run` usage, configure
OpenRouter:

```dotenv
OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_MODEL=openai/gpt-oss-20b:free
CSPILOT_LLM_PROVIDER=openrouter
```

`--llm-provider auto` uses OpenRouter by default.
Use `--llm-provider agapi` only when AGAPI model serving is intentionally being
tested. If AGAPI is selected and fails with common backend/model errors, CSPilot
can still retry through OpenRouter.

Deterministic xTB, ORCA, stk, NWPESSe, MACE, and ASE tools are unchanged.

## Direct Agent

```bash
cspilot agent "inspect tests/examples/input.xyz" \
  --workdir runs/agent_test --agent-profile chem
```

`agent` supports:

```bash
--llm-provider auto|openrouter|agapi
--model openai/gpt-oss-20b:free
--base-url https://openrouter.ai/api/v1
--agent-profile chem|materials|general
```

## Planner, Run, and LangGraph

The configured model backend is used by:

```bash
cspilot plan "inspect tests/examples/input.xyz" --workdir runs/plan
cspilot run "inspect tests/examples/input.xyz" --workdir runs/run
cspilot graph-run "inspect tests/examples/input.xyz" --workdir runs/graph
```

The model returns JSON plans. The executor calls only registered tools from the
selected profile allowlist.

## AGAPI Materials Query Wrapper

When the AGAPI prebuilt `AGAPIAgent` is available, CSPilot can delegate
materials queries:

```bash
cspilot graph-run "Find all Al2O3 materials" \
  --profile auto --agent-mode multi --html --workdir runs/al2o3
```

The wrapper calls the equivalent of:

```python
agent.query_sync(query, render_html=render_html)
```

## Local Tools vs AGAPI Tools

| Path | Examples | Data source |
| --- | --- | --- |
| Local CSPilot tools | ASE, xTB, ORCA, MACE, stk, NWPESSe | local files and local executables |
| Model planner | `plan`, `run`, `graph-run` | JSON tool selection only through OpenRouter or AGAPI |
| AGAPI prebuilt tools | materials/JARVIS-style query | AGAPI response |

AGAPI is not used to invent xTB or ORCA outputs. If a property is missing from
parsed output, reports say it was not found in parsed results.
