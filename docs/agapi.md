# AGAPI Integration

`cspilot` contains two related AGAPI integration paths.

## OpenAI-Compatible Agent Backend

The Agents SDK path constructs an asynchronous OpenAI-compatible client using:

```dotenv
AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b
```

It is used by `cspilot agent`, `cspilot plan`, and `cspilot run`. The model
selects only the tools made available by the relevant agent or profile
registry.

The direct agent supports model/backend overrides:

```bash
cspilot agent "inspect input.xyz" --workdir runs/agent-check \
  --model openai/gpt-oss-20b --base-url https://atomgpt.org/api
```

## AGAPI Prebuilt Materials Query

The optional `agapi_materials_query` wrapper imports the AGAPI prebuilt
`AGAPIAgent` and delegates to:

```python
agent.query_sync(query, render_html=render_html)
```

It is exposed through the planner/executor registry for the `materials`
profile:

```bash
cspilot run "Find all Al2O3 materials" --workdir runs/al2o3 \
  --profile materials --html
```

The `--html` switch above controls cspilot's final execution report.
`AGAPIAgent` may display its own rendered output in notebook environments; the
cspilot result records the returned response content.

## Local Tools Versus AGAPI Prebuilt Tools

| Kind | Examples | Authority for returned data |
| --- | --- | --- |
| Local cspilot tool | ASE inspection, xTB, ORCA/OPI, MACE, JSON parsing | Local inputs and local executable output |
| AGAPI prebuilt tool | Materials/JARVIS-style natural-language query | AGAPI service response |

AGAPI is not used to fabricate local ORCA or xTB results. If a local
calculation did not run or a parsed property is absent, reports must state
that limitation.
