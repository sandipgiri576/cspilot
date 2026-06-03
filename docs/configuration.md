# Configuration

CSPilot loads `.env.cspilot` from the current working directory.

```dotenv
CSPILOT_RUNS_DIR=runs
XTB_COMMAND=xtb
ORCA_COMMAND=/path/to/orca
NWPESSE_BIN=nwpesse
MACE_MODEL=/path/to/model.model

AGAPI_API_KEY=your_api_key
AGAPI_BASE_URL=https://atomgpt.org/api
cspilot_MODEL=openai/gpt-oss-20b
```

## Implemented Variables

| Variable | Used by | Default or requirement |
| --- | --- | --- |
| `CSPILOT_RUNS_DIR` | deterministic commands and fixed workflows | `runs` |
| `XTB_COMMAND` | xTB optimization | `xtb` |
| `ORCA_COMMAND` | ORCA CLI and workflows | `orca` |
| `NWPESSE_BIN` | NWPESSe workflow | `nwpesse` |
| `MACE_MODEL` | `workflow mace-orca` when `--model` is omitted | fallback placeholder |
| `AGAPI_API_KEY` | `agent`, `search`, `plan`, `run`, `graph-run` planning, AGAPI materials | required for AGAPI calls |
| `AGAPI_BASE_URL` | OpenAI-compatible AGAPI client | required unless command supports `--base-url` |
| `cspilot_MODEL` | AGAPI model | required unless command supports `--model` |

OPI may also recognize `OPI_ORCA` and `ORCA_PATH` internally. CSPilot CLI
settings use `ORCA_COMMAND`.

## Names Not Currently Read

| Name | Current status | Use now |
| --- | --- | --- |
| `XTB_BIN` | not read | `XTB_COMMAND` |
| `ORCA_BIN` | not read | `ORCA_COMMAND` |
| `MULTIWFN_BIN` | planned only | none |
| `MACE_MODEL_PATH` | not read | `MACE_MODEL` or `--model` |

## Work Directories

- `inspect`, `xtb-opt`, `orca-sp`, `mace-opt`, and `workflow ...` create
  timestamped directories under `CSPILOT_RUNS_DIR`.
- `plan`, `execute`, `run`, `graph-run`, `agent`, `search`, `stk-*`, and
  `nwpesse-search` accept explicit `--workdir` style paths.
- `run` and `graph-run` write report files in their selected workdir.

## Output Controls

`run` and `graph-run` support:

- `--pretty / --no-pretty`: Rich terminal tables and panels, on by default.
- `--quiet`: print only final status and report path.
- `--html`: write `final_report.html` instead of `final_report.md`.
