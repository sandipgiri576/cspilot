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

## stk SMILES To xTB Optimization

```bash
cspilot stk-xtb "C1=CC=CC=C1" --workdir runs/stk_xtb
```

Steps:

1. Build a molecule from SMILES with `stk_build_from_smiles`.
2. Export `stk_build.xyz` with `stk_export_to_xyz`.
3. Run the existing xTB optimizer in `xtb_opt/`.
4. Save `workflow_result.json`.

This workflow does not use `stko`. If xTB is not available, the build/export
steps can still be recorded and the xTB step is reported as skipped or failed.

## NWPESSe Fragment-Cluster Global-Minimum Search

```bash
cspilot nwpesse-search "(h2o)4Mg" --workdir runs/h2o4mg \
  --max-calculations 10 --box-size 3.0
```

Steps:

1. Parse the fragment formula or use explicit `--fragment name:count` options.
2. Copy fragment XYZ files from `--fragment-dir`, or generate known simple
   fragments from the internal library.
3. Write `mol.cluster`.
4. Generate validated placement boxes. The default `per_fragment_type` mode
   creates one `inbox` line per unique fragment type; `single` creates one box
   for the whole system.
5. Write `mol.inp` using the whitelisted `xtb_gxtb` optimizer block.
6. Run the external NWPESSe binary configured by `NWPESSE_BIN`.
7. Scan generated XYZ candidates in `<result-name>-LM/`, any `*-LM/` folder,
   and recursively under the workdir. Energies are parsed from line 2 formats
   such as `Energy = -505.86549251 au`, `E = -505.86549251 au`, or a bare
   number.
8. Copy the best candidate to `lowest_energy.xyz` and save
   `workflow_result.json`.

`mol.cluster` format:

```text
2
h2o.xyz 4
mg.xyz 1
```

`mol.inp` format:

```text
nwpesse_result
mol.cluster
10
>>>>
inbox 0. 0. 0. 3.0 3.0 3.0
inbox 0. 0. 0. 3.0 3.0 3.0
>>>>
cp $inp$ $xxx$.xyz
xtb $xxx$.xyz --gxtb --opt  > $xxx$.out
energy=`awk 'NR==2{print $2}' xtbopt.xyz` ; sed -i "2c ${energy}" xtbopt.xyz
mv xtbopt.xyz $out$
rm $xxx$.xyz $xxx$.out  charges wbo xtbopt.log xtbrestart *.mol
>>>>
```

Supported formula forms include `(h2o)4Mg`, `(h2o)4(Mg)`,
`[h2o]4[mg]1`, `h2o:4,mg:1`, and `h2o 4 mg 1`.

For `(h2o)4`, default `per_fragment_type` writes one box line. For
`(h2o)4Mg`, it writes two box lines. Use `--box-mode single --box-size 5.0`
to place the whole system in one larger box.

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
