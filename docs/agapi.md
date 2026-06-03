# AGAPI Integration

CSPilot uses AGAPI through OpenAI-compatible clients and optional prebuilt
AGAPI tools.

## Configuration

```dotenv
AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b
```

## Direct Agent

```bash
cspilot agent "inspect tests/examples/input.xyz" \
  --workdir runs/agent_test --agent-profile chem
```

`agent` supports:

```bash
--model openai/gpt-oss-20b
--base-url https://atomgpt.org/api
--agent-profile chem|materials|general
```

## Planner, Run, and LangGraph

AGAPI planning is used by:

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
| Local CSPilot tools | ASE, xTB, ORCA/OPI, MACE, stk, NWPESSe | local files and local executables |
| AGAPI planner | `plan`, `run`, `graph-run` | JSON tool selection only |
| AGAPI prebuilt tools | materials/JARVIS-style query | AGAPI response |

AGAPI is not used to invent xTB or ORCA outputs. If a property is missing from
parsed output, reports say it was not found in parsed results.
