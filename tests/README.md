# Offline Tests

The test suite checks the experiment's deterministic behavior without an API key or billable request.

| Test file | What it checks |
|---|---|
| `test_agents.py` | Structured supervisor responses, retries, redaction, replay matching, and invalid-output handling. |
| `test_analysis.py` | Run loading, confirmatory filtering, summaries, paired statistics, and confidence intervals. |
| `test_budget.py` | Cost reservation, hard caps, append-only ledgers, and concurrent access. |
| `test_models_policy.py` | Typed intent validation and deterministic policy-shield rules. |
| `test_network_harness.py` | MQTT payload schemas, counters, and network-harness helpers. |
| `test_orchestration_trust.py` | Run-matrix construction, live gates, peer trust handling, and orchestration behavior. |
| `test_scenario_network.py` | Demand scaling, deterministic scenario generation, and communication emulation. |
| `test_signals_metrics.py` | Safe phase transitions and SUMO metric parsing. |
| [`fixtures/`](fixtures/README.md) | Small recorded inputs used for deterministic replay tests. |

Run all tests from the repository root:

```bash
python -m pytest -q
```

CI runs the same suite on Python 3.12. Add a focused test whenever a behavioral change affects controller logic, policy enforcement, cost handling, output schemas, or analysis.
