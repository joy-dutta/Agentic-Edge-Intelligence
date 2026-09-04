# Released Result Tables

These are the compact, machine-readable outputs of the completed evaluation. They contain no publication figure and can be inspected with a spreadsheet program, Python, R, or a text editor.

## Main Confirmatory Evidence

| File | What it reports |
|---|---|
| `main_results.csv` | Scenario-by-controller summaries for the frozen 520-run matrix. |
| `paired_comparisons.csv` | Paired effects, confidence intervals, tests, and multiplicity-adjusted results. |

## Pilot and Exploratory Follow-up

| File | What it reports |
|---|---|
| `pilot_corrected_v4_summary.csv` | Final two-seed pilot summaries after the registered pre-pilot corrections. |
| `pilot_corrected_v4_paired_comparisons.csv` | Paired pilot comparisons used for the go/no-go review. |
| `followup_run_level.csv` | Run-level values from the separate Cologne-8 and Cologne-3 coordination follow-up. |
| `followup_paired_comparisons.csv` | Peer-aware versus no-peer follow-up comparisons. |
| `followup_summary.json` | Compact follow-up counts and interpretation fields. |

## Model and Controller Sensitivity

| File | What it reports |
|---|---|
| `model_validation_state_agreement.csv` and `model_validation_state_agreement_summary.json` | Agreement between the pinned small and larger model on frozen traffic states. |
| `model_validation_traffic_runs.csv` | Run-level traffic outcomes for the model-size validation. |
| `model_validation_traffic_comparison.csv` and `model_validation_traffic_summary.json` | Paired model-size traffic comparisons and summary. |
| `idqn_placement_summary.csv` | Frozen IDQN outcomes by local or delayed placement. |
| `idqn_placement_paired.csv` | Paired placement effects for the IDQN sensitivity check. |

## Governance, Repeatability, Latency, and Network Audits

| File | What it reports |
|---|---|
| `shield_audit.csv` and `shield_audit_summary.json` | Fixed-state causal tests of policy-shield acceptance and rejection. |
| `repeatability_audit.csv` and `repeatability_summary.json` | Repeated pinned-model outputs for identical structured inputs. |
| `independent_agent_latency.csv` and `independent_agent_latency_summary.json` | Host-observed latency for eight independent logical agents. |
| `pcap_reconciliation_edge.json` and `pcap_reconciliation_cloud.json` | Application-counter and packet-capture byte reconciliation. |

To verify the main tables from the included run-level data, run:

```bash
python scripts/verify_results.py
```

For definitions, denominators, and units, see [`docs/data_dictionary.md`](../../docs/data_dictionary.md). For a readable interpretation, see [`docs/RESULTS.md`](../../docs/RESULTS.md).
