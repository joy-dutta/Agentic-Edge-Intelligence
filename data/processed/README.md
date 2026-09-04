# Processed Run-Level Data

These files make the released evidence checkable without downloading SUMO scenarios or making an API call.

| File | What it contains |
|---|---|
| `run_level_results.csv` | Main confirmatory analysis frame, one independent row per completed simulation run. |
| `run_level_results.parquet` | The same main frame in a typed, efficient columnar format. |
| `pilot_corrected_v4_run_level_results.csv` | Final corrected pilot analysis frame in portable CSV form. |
| `pilot_corrected_v4_run_level_results.parquet` | The same pilot frame in Parquet form. |
| `idqn_placement_results.csv` | Run-level local-versus-delayed placement sensitivity results for the frozen IDQN. |

Verify the main counts and statistical tables with:

```bash
python scripts/verify_results.py
```

When raw primary runs are available, `python scripts/analyze.py --phase primary` rebuilds the main frame and result tables. Field definitions and units are in [`docs/data_dictionary.md`](../../docs/data_dictionary.md).
