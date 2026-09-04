# Experiment Artifacts

This folder separates evidence that is small enough to publish from detailed outputs that are generated during a rerun.

| Folder | Status | What it contains |
|---|---|---|
| [`tables/`](tables/README.md) | Included | Machine-readable result summaries, paired comparisons, and audit outputs. |
| [`raw/`](raw/README.md) | Generated locally | One folder per simulation run, including the run summary and decision logs. |
| [`logs/`](logs/README.md) | Generated locally | Live API usage and budget-reservation ledgers. |
| [`pcap/`](pcap/README.md) | Generated locally | Packet captures from the optional TLS/MQTT network harness. |

Additional ignored folders may appear after a rerun: `figures/` for local diagnostic plots, `network/` for harness counters, `network_tls/` for disposable certificates, and `reports/` for generated reports. These are working outputs, not hidden inputs.

For a quick evidence check, start with:

```bash
python scripts/verify_results.py
```

That command uses the included processed data and does not require SUMO, Docker, an API key, or a network connection.
