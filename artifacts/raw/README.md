# Raw Run Outputs

This is the authoritative destination for newly generated raw experiment outputs. The folder is intentionally empty in a fresh clone apart from this guide; `data/raw` is not used.

## Why the Completed Raw Archive Is Not in Git

The completed development archive contains more than 10,000 generated files and is approximately 3.3 GiB. Placing that archive in ordinary Git history would make every clone much larger without being necessary for checking the released statistics. Instead, the repository includes:

- the exact processed run-level data under [`data/processed`](../../data/processed/README.md);
- the released statistical outputs under [`artifacts/tables`](../tables/README.md);
- all frozen configurations, seeds, source code, and analysis scripts needed to regenerate raw runs.

No external raw-data download is required for Level A verification. Run `python scripts/verify_results.py` to recompute the main tables directly from the included run-level data.

## Where Raw Data Comes From

Raw files are produced by this repository, not manually downloaded. SUMO simulates individual vehicles on the pinned RESCO Cologne networks, and the experiment runtime records traffic outcomes, controller decisions, policy checks, and redacted API metadata. Obtain the upstream scenario first:

```bash
python scripts/fetch_resco.py
```

This checks out the exact RESCO commit and applies the tracked reproducibility patch. See [`scenarios/README.md`](../../scenarios/README.md) for provenance and licensing.

## Generate Raw Runs

An inexpensive offline pilot creates deterministic-controller outputs without an API call:

```bash
python scripts/pilot.py --mode offline --phase pilot --workers 1
```

The full deterministic matrix is generated with:

```bash
python scripts/full_sweep.py --mode offline --workers 4
```

The LLM-assisted cells require the reproducer's own API key and completed cost gates. Follow [`docs/API_AND_BUDGET.md`](../../docs/API_AND_BUDGET.md), then use the live commands in [`docs/REPRODUCIBILITY.md`](../../docs/REPRODUCIBILITY.md). Never place an API key or `.env` file in this folder.

## Layout After a Run

```text
artifacts/raw/<phase>/<run_id>/
|-- summary.json             One run-level traffic and system summary
|-- decisions.jsonl          Observations, delivered intents, and executed phases
|-- policy_decisions.jsonl   Shield decisions, reasons, and fallback actions
`-- api_calls.jsonl          Redacted request metadata, hashes, latency, and usage
```

Some controllers do not create every JSONL file because they make no LLM request or policy decision. Field definitions and units are in [`docs/data_dictionary.md`](../../docs/data_dictionary.md).

After generating a primary matrix, rebuild the processed files and tables with:

```bash
python scripts/analyze.py --phase primary
```
