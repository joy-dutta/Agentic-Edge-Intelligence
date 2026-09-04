# Experiment Package

This package contains the traffic-control proof of concept. The LLM is confined to structured supervisory intents; deterministic code owns policy checking, signal timing, fallback, simulation, accounting, and measurement.

| Module | Responsibility |
|---|---|
| `__init__.py` | Package marker and version-facing imports. |
| `models.py` | Typed observations, peer summaries, agent intents, corridor responses, and policy decisions. |
| `config.py` | Loads and validates YAML experiment settings. |
| `controllers.py` | Local MaxWave, coordinated max-pressure, and shared deterministic control helpers. |
| `agent_runtime.py` | Converts traffic state into compact supervisor input and applies an accepted intent to the local target. |
| `agents.py` | OpenAI structured-response supervisor, retry/latency recording, and exact replay supervisor. |
| `policy.py` | Deterministic policy limits and accept/reject shield. |
| `signals.py` | Safe yellow transitions, minimum timing, and signal execution. |
| `network.py` | Reproducible delay, jitter, loss, bandwidth, and message accounting. |
| `topology.py` | Derives neighboring controlled intersections from the SUMO network. |
| `scenario.py` | Creates deterministic demand-scaled route files. |
| `runner.py` | Owns one SUMO run, injects events/faults, coordinates controllers and agents, and writes raw outputs. |
| `orchestration.py` | Builds run matrices, checks live gates, orders work, and manages parallel workers. |
| `metrics.py` | Parses SUMO trip, safety, and SSM outputs into run-level measures. |
| `analysis.py` | Loads raw summaries and calculates descriptive and paired confirmatory statistics. |
| `budget.py` | Reserves, records, and caps live API cost across processes. |
| `file_lock.py` | Provides cross-process locks and safe append-only JSONL writes. |
| `cli.py` | Implements the installed `agentic-edge-poc` command. |

The main execution path is `orchestration.py` to `runner.py`, then through a deterministic controller or `agents.py` to `policy.py` and `signals.py`. Tests in [`tests/`](../../tests/README.md) exercise these boundaries without making API calls.
