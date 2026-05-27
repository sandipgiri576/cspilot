# Configuration

`cspilot` loads `.env.cspilot` from the current working directory. Do not
commit API keys or licensed-software configuration containing secrets.

## Implemented Variables

```dotenv
CSPILOT_RUNS_DIR=runs
XTB_COMMAND=xtb
ORCA_COMMAND=/path/to/orca
MACE_MODEL=/path/to/mace_model.model

AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b
```

| Variable | Used by | Default or requirement |
| --- | --- | --- |
| `CSPILOT_RUNS_DIR` | Deterministic commands and workflows | `runs` |
| `XTB_COMMAND` | xTB optimization | `xtb` |
| `ORCA_COMMAND` | ORCA CLI and workflows | `orca` |
| `MACE_MODEL` | `workflow mace-orca` when `--model` is omitted | `model_path` placeholder |
| `AGAPI_API_KEY` | `agent`, `plan`, `run`, AGAPI materials wrapper | Required for AGAPI calls |
| `AGAPI_BASE_URL` | OpenAI-compatible agent/planner client | Required unless `--base-url` is supplied where supported |
| `cspilot_MODEL` | OpenAI-compatible agent/planner model | Required unless `--model` is supplied for `agent` |

The OPI integration also recognizes `OPI_ORCA` and `ORCA_PATH` when its Python
API is invoked without an explicitly supplied ORCA command. The CLI uses
`ORCA_COMMAND` through application settings.

## Names Not Currently Implemented

The following proposed variable names are not read by current source code:

| Requested name | Current status | Use now |
| --- | --- | --- |
| `XTB_BIN` | Not implemented | `XTB_COMMAND` |
| `ORCA_BIN` | Not implemented | `ORCA_COMMAND` |
| `MULTIWFN_BIN` | Planned with Multiwfn support | None |
| `MACE_MODEL_PATH` | Not implemented | `MACE_MODEL` or `--model` |

## Work Directories

- `inspect`, `xtb-opt`, `orca-sp`, `mace-opt`, and `workflow ...` use
  `CSPILOT_RUNS_DIR` and create timestamped directories such as
  `runs/20260527-170000-000000-orca-sp/`.
- `agent`, `plan`, `execute`, and `run` accept an explicit `--workdir`.
- Default agent workdir: `runs/agent_test`.
- Default planner/executor/run workdir: `runs/test`.
