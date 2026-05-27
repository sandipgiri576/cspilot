# Workflows

All fixed workflows accept an XYZ input, copy it into a new timestamped run
directory under `CSPILOT_RUNS_DIR`, execute sequential steps, and write
`workflow_result.json`.

## xTB Optimization To ORCA Single Point

```bash
cspilot workflow xtb-orca-sp input.xyz --charge 0 --mult 1 \
  --method r2scan-3c --basis def2-SVP --uhf 0 --nprocs 1
```

Steps:

1. Copy `input.xyz`.
2. Optimize geometry using xTB in `01_xtb_opt/`.
3. If `xtbopt.xyz` exists after a successful optimization, run ORCA SP with
   OPI in `02_orca_sp/`.
4. Store parsed final energy when available.

## xTB Optimization To ORCA Frequency

```bash
cspilot workflow xtb-orca-freq input.xyz --charge 0 --mult 1 \
  --method r2scan-3c --basis def2-SVP --uhf 0 --nprocs 1
```

Steps are the same as above, except step 3 invokes an ORCA frequency job in
`02_orca_freq/`. OPI or the fallback text parser may store
`gibbs_free_energy`, `enthalpy`, or zero-point energy if those values occur in
the completed ORCA output.

## MACE Optimization To ORCA Single Point

```bash
cspilot workflow mace-orca input.xyz --model /path/to/model.model \
  --charge 0 --mult 1 --method r2scan-3c --basis def2-SVP
```

Steps:

1. Copy `input.xyz`.
2. Optimize geometry with MACE in `01_mace_opt/`.
3. If MACE succeeds and creates `mace_opt.xyz`, run ORCA SP in `02_orca_sp/`.

MACE requires the `mace` optional dependency and a valid local model. If
`--model` is absent, this workflow reads `MACE_MODEL`.

## Result JSON Shape

The workflow result is a JSON object of the following form; property keys are
present only when returned by tools:

```json
{
  "workflow": "xtb-orca-freq",
  "status": "ok",
  "input_xyz": "/absolute/path/input.xyz",
  "workdir": "runs/<timestamp>-xtb-orca-freq",
  "steps": {
    "xtb_opt": {
      "status": "ok",
      "outputs": {
        "optimized_xyz": "runs/.../01_xtb_opt/xtbopt.xyz"
      }
    },
    "orca_freq": {
      "status": "ok",
      "task": "freq",
      "result": {
        "properties": {
          "final_energy_hartree": -1.0,
          "gibbs_free_energy": -1.0
        }
      }
    }
  },
  "final_energy_hartree": -1.0,
  "workflow_result_path": "runs/.../workflow_result.json"
}
```

The numbers above show structure only and are not expected calculation values.
