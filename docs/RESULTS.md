# Released Results

This page summarizes the released machine-readable tables. It contains no publication figures. The CSV and JSON files under [`artifacts/tables`](../artifacts/tables) remain the authoritative values.

## Confirmatory Matrix

The processed dataset contains all 520 registered runs. Paired comparisons use identical scenario seeds for both controllers.

### Governed Edge Control Relative to Cloud Control

Positive values mean lower time loss for governed edge control. All comparisons in this table remain significant after Holm correction.

| Scenario | Mean time-loss reduction, s (95% CI) | P95 time-loss reduction, s (95% CI) |
|---|---:|---:|
| S0 | 21.69 (19.99, 23.36) | 76.92 (64.94, 88.28) |
| S1 | 21.77 (17.27, 26.66) | 69.24 (51.43, 89.24) |
| S2 | 30.11 (26.36, 33.97) | 102.28 (82.09, 125.39) |
| S3 | 28.40 (24.68, 32.12) | 87.65 (67.24, 108.43) |
| S4 | 27.14 (22.60, 32.03) | 91.10 (63.79, 127.02) |

This is an architecture-level comparison: the governed system combines local deterministic control, bounded supervision, and a less frequent WAN exchange, while the cloud baseline depends on remote max-pressure observations and actions.

### Comparison with Strong Local Control

After Holm correction, governed agentic control and Local MaxWave were not statistically distinguishable on mean or P95 time loss in the five confirmatory scenarios. This is useful evidence for the intended role of the LLM: it adds bounded supervision and governance without requiring the dependable local controller to be removed.

The S2 incident comparison showed a 12.65-s P95 reduction for governed control with a paired-bootstrap interval of 1.70 to 23.25 s. Because the multiplicity-corrected test was not significant, this remains an incident-focused signal for further testing rather than a confirmatory performance claim.

### WAN Application Traffic

| Scenario | Cloud, MB/run | Governed edge, MB/run | Reduction |
|---|---:|---:|---:|
| S0 | 8.778 | 0.395 | 95.50% |
| S1 | 8.781 | 0.394 | 95.52% |
| S2 | 8.778 | 0.408 | 95.35% |
| S3 | 8.778 | 0.413 | 95.30% |
| S4 | 8.778 | 0.440 | 94.99% |

The packet-capture calibration measured 37-ms median and 40-ms P95 closed-loop latency for the edge path, compared with 112-ms median and 146-ms P95 for the cloud path.

## Policy Governance

Across the 80 governed confirmatory runs:

| Measure | Count |
|---|---:|
| Proposals violating at least one declared rule | 1,191 |
| Violating proposals blocked by the shield | 1,191 |
| Violating proposals executed | 0 |

The matched unguarded controller executed between 17.95 and 22.75 rule-violating proposals per run across the five scenarios. The deterministic shield's run-level P95 latency was approximately 0.0103 ms, and the largest run-level P99 was 0.0281 ms.

An independently selected 200-proposal audit reproduced the same behavior: all 29 rule-violating proposals were blocked with the shield enabled and all 29 were executable when the shield was disabled. These counts establish enforcement of the declared policy rules; they do not label every physically unsafe state.

## Fail-Closed Operation

The 200 live agentic runs recorded:

| Structured-response outcome | Count |
|---|---:|
| Valid response | 5,961 |
| Invalid response | 221 |
| Timeout | 2 |
| Server error | 1 |

Invalid, unavailable, or late responses did not stop the five-second deterministic control loop. In the 30 governed S3/S4 outage runs, the first accepted post-outage intent arrived after a mean of 55.17 simulated seconds; the maximum was 225 seconds. Local control remained active throughout these intervals.

## Coordination and Model Sensitivity

The no-peer ablation and 80-run two-network follow-up provide an interpretation boundary: peer summaries changed some LLM decisions, but the completed tests did not establish a repeatable traffic-performance improvement from peer context. This makes the released benchmark useful for testing richer directional context and event-specialized coordination without overstating the present result.

The larger validation model reduced malformed or fallback outputs but did not automatically improve closed-loop traffic performance. The package therefore evaluates the complete controlled system rather than treating model size as a substitute for system-level measurement.

## Where to Inspect the Values

- `data/processed/run_level_results.csv`: one row per confirmatory run.
- `artifacts/tables/main_results.csv`: controller/scenario summaries and confidence intervals.
- `artifacts/tables/paired_comparisons.csv`: paired effects, confidence intervals, effect sizes, and corrected tests.
- `artifacts/tables/shield_audit.csv`: independent shield audit.
- `artifacts/tables/followup_run_level.csv`: exploratory cross-network runs.
- `artifacts/tables/model_validation_*.csv`: model sensitivity checks.
- `artifacts/tables/repeatability_*.json`: repeated-call behavior.

Run `python scripts/verify_results.py` to regenerate the main summary and paired-comparison tables from the released run-level CSV and compare them numerically with the released tables.

