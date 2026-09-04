# Command Guide

Run these scripts from the repository root. Most support `--help`; commands that make a live API call are clearly identified below.

## Prepare and Run Experiments

| Script | What it does | API use |
|---|---|---:|
| `fetch_resco.py` | Downloads the exact upstream RESCO commit and applies the deterministic-seed patch. | No |
| `pilot.py` | Runs the frozen two-seed S2 pilot in offline or live mode. | Optional |
| `pilot_report.py` | Builds the pilot gate report from completed pilot outputs. | No |
| `full_sweep.py` | Runs the deterministic, LLM-assisted, or complete portion of the frozen 520-run confirmatory matrix. | Optional |
| `followup_sweep.py` | Runs the separately registered Cologne-8 and Cologne-3 coordination follow-up. | Yes for agentic cells |
| `replay.py` | Exactly replays one recorded live run against payload hashes and recorded responses. | No |
| `resco_idqn.py` | Packages, trains, or evaluates the separate RESCO IDQN sensitivity controller. | No |

## Analyze Results

| Script | What it does |
|---|---|
| `analyze.py` | Builds the main processed frame, paired statistics, and local diagnostics from primary raw runs. |
| `analyze_followup.py` | Summarizes the exploratory peer-context follow-up. |
| `analyze_model_traffic_validation.py` | Compares traffic outcomes from the pinned small and larger model validation. |
| `analyze_idqn.py` | Summarizes local-versus-delayed IDQN placement runs. |

## Run Focused Audits and Validations

| Script | What it does | API use |
|---|---|---:|
| `shield_audit.py` | Tests governed and unguarded behavior on recorded fixed states containing acceptable and policy-breaking intents. | No |
| `repeatability_audit.py` | Repeats identical structured requests to measure pinned-model output stability. | Yes |
| `independent_latency_audit.py` | Measures parallel latency for eight independent logical edge agents. | Yes |
| `model_validation.py` | Runs the registered small-versus-larger-model state and traffic validation stages. | Yes |
| `measure_host_network.py` | Measures the unshaped host path to the API endpoint. | Network metadata only |
| `check_api_access.py` | Checks access to the pinned model without requesting an inference. | No billable inference |
| `probe_responses_contract.py` | Makes one bounded request to verify model access, structured output, and the eight-agent schema. | One bounded call |

## Network Harness

| Script | What it does |
|---|---|
| `generate_mqtt_tls.py` | Creates short-lived certificates for the local MQTT test. |
| `network_harness.py` | Runs the simulator, edge, or cloud role and records versioned MQTT counters. |
| `reconcile_pcap.py` | Checks application counters against captured transport bytes. |

## Budget, Integrity, and Release Tools

| Script | What it does |
|---|---|
| `prepare_budget_manifest.py` | Uses observed pilot usage to create a bounded post-pilot phase manifest. |
| `build_release_manifest.py` | Records every public file's byte size and SHA-256 hash in `configs/release_manifest.json`. |
| `build_sha256_manifest.py` | Creates an evidence/source manifest under generated artifacts for a local archive. |
| `secret_scan.py` | Scans paths and text patterns for likely credentials without printing a matched secret. |
| `verify_release.py` | Checks the release manifest, private-file exclusions, forbidden publication assets, and secret patterns. |
| `verify_docs.py` | Checks local Markdown links. |
| `verify_results.py` | Recomputes and compares the released main result tables from included processed data. |

Start with [`docs/REPRODUCIBILITY.md`](../docs/REPRODUCIBILITY.md) instead of calling live scripts directly. The reproduction guide puts model access, contract probing, pilot review, and cost gates in the required order.
