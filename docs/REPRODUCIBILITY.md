# Reproducibility Guide

This guide separates inexpensive verification from full live reproduction. Run every command from the repository root.

## Requirements

Recommended:

- 64-bit Linux or WSL2.
- Docker Engine with Compose v2.
- Git.
- At least 8 CPU threads, 16 GB RAM, and 20 GB free disk space for a full rerun.

Native alternative:

- Python 3.12.
- A C/C++ compatible host for the pinned Python wheels.
- SUMO 1.27.1, installed by `requirements.lock`.

The completed evaluation used CPU execution. No GPU is required for SUMO or the API-hosted supervisor.

## Obtain the Repository

```bash
git clone https://github.com/joy-dutta/Agentic-Edge-Intelligence.git
cd Agentic-Edge-Intelligence
git status --short
```

A fresh clone should have an empty status.

## Docker Environment

```bash
docker compose build experiment
docker compose run --rm experiment python --version
docker compose run --rm experiment python scripts/verify_release.py
docker compose run --rm experiment pytest -q
docker compose run --rm experiment python scripts/verify_results.py
```

Expected high-level checks:

- Python reports version 3.12.x.
- Release verification reports no forbidden assets or secret-like values.
- The offline test suite passes.
- Result verification reports 520 confirmatory runs and matching tables.

The `experiment` service bind-mounts the repository at `/workspace`, so fetched scenarios and generated outputs remain available on the host.

## Native Environment

Linux/WSL2:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
export PYTHONPATH="$PWD/src"
```

PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
$env:PYTHONPATH = (Resolve-Path 'src')
```

The SUMO data wheel contains deeply nested paths. For native Windows installation, enable long-path support and use a short checkout path such as `C:\src\Agentic-Edge-Intelligence`. Docker/WSL2 avoids this host limitation and remains the recommended route.

Then run:

```bash
python scripts/verify_release.py
pytest -q
python scripts/verify_results.py
```

## Level A: Verify the Released Evidence

Level A makes no network request and no API call.

```bash
python scripts/verify_release.py
python scripts/verify_results.py
```

`verify_release.py` checks the release manifest, credential patterns, forbidden private files, and forbidden figure/manuscript formats. `verify_results.py` recomputes the main summary and paired-comparison tables from `data/processed/run_level_results.csv` and compares the values with the released tables.

The authoritative table inputs and outputs are:

```text
data/processed/run_level_results.csv
artifacts/tables/main_results.csv
artifacts/tables/paired_comparisons.csv
```

## Level B: Reproduce the Offline Simulation

### Fetch the Exact RESCO Source

```bash
python scripts/fetch_resco.py
```

The command checks the upstream URL, checks out commit `f1ed9a174f8de41fc9d8689373b836bc882570dc`, and applies `patches/resco_v2_deterministic_seed.patch`. It refuses an unexpected remote, commit, or unrecognized local modification.

### Two-Seed Offline Pilot

```bash
python scripts/pilot.py --mode offline --phase pilot --workers 1
```

This runs fixed timing, Local MaxWave, coordinated max-pressure, and cloud max-pressure for the two frozen pilot seeds in S2. It produces no billable request.

### Full Deterministic Matrix

```bash
python scripts/full_sweep.py --mode offline --workers 4
```

Start with one worker if the host has limited memory. Each worker owns its SUMO process, route file, controller state, and output directory.

### Rebuild Tables from New Raw Runs

```bash
python scripts/analyze.py --phase primary
```

This command reads `artifacts/raw/primary/*/summary.json`, filters the frozen confirmatory cells, and writes new processed data and result tables. It may also create local diagnostic figures under the ignored `artifacts/figures` directory.

## Level C: Reproduce Live LLM Supervision

Read [API_AND_BUDGET.md](API_AND_BUDGET.md) before making any live request. Use your own API project and verify its billing controls independently.

### Prepare Local Gates

```bash
cp configs/platform_budget_gate.example.json configs/platform_budget_gate.json
```

Edit the ignored local copy after verifying the account limit. Set `OPENAI_API_KEY` only in the process environment.

### Check Access and Schema

```bash
python scripts/check_api_access.py
python scripts/probe_responses_contract.py
```

The first command retrieves model metadata without inference. The second makes one bounded inference and writes the ignored `configs/api_contract_gate.json` only when the exact model and eight-agent schema pass.

### Live Pilot

```bash
python scripts/pilot.py --mode live --phase pilot --workers 1
python scripts/pilot_report.py --phase pilot
```

Inspect:

```text
artifacts/pilot_report.md
artifacts/logs/api_usage.jsonl
artifacts/logs/api_usage_reservations.jsonl
```

Do not continue unless every pilot gate passes and recorded usage is within the phase ceiling.

### Confirmatory Live Matrix

```bash
python scripts/full_sweep.py --mode live --workers 1
```

The frozen live matrix runs the governed, unguarded, and no-peer configurations. Increase workers only after confirming that the host, API rate limits, and budget reservation ledger behave correctly.

### Registered Audits

```bash
python scripts/shield_audit.py
python scripts/repeatability_audit.py
python scripts/independent_latency_audit.py
python scripts/model_validation.py --stage nano-sweep
python scripts/model_validation.py --stage mini-sweep
python scripts/model_validation.py --stage mini-states
```

### Exploratory Coordination Follow-up

```bash
python scripts/followup_sweep.py --workers 1
python scripts/analyze_followup.py
python scripts/analyze_model_traffic_validation.py
```

The follow-up uses disjoint seeds and remains separate from the confirmatory matrix.

## Network and Packet-Capture Harness

The TLS/MQTT harness requires Linux networking capabilities and Docker Compose:

```bash
ARCHITECTURE=edge docker compose up --build -d
docker wait "$(docker compose ps -q simulator-controller)"
docker compose stop pcap
python scripts/reconcile_pcap.py --architecture edge
docker compose down
```

Repeat with `ARCHITECTURE=cloud`. See [network_harness.md](network_harness.md) for shaping assumptions and reconciliation rules.

## Frozen IDQN Sensitivity

The supplied checkpoints can be evaluated with the additional pinned dependency set:

```bash
python -m pip install -r requirements-idqn.lock
python scripts/resco_idqn.py --help
python scripts/analyze_idqn.py
```

The IDQN study is separate from the seven-controller confirmatory matrix.

## Expected Outputs

| Path | Content |
|---|---|
| `artifacts/raw/<phase>/<run_id>/summary.json` | One run-level summary |
| `artifacts/raw/<phase>/<run_id>/*.jsonl` | Decision, policy, and redacted API audit streams |
| `artifacts/logs/api_usage*.jsonl` | Append-only usage and reservation ledger |
| `data/processed/run_level_results.csv` | Confirmatory analysis frame |
| `artifacts/tables/*.csv` | Statistical tables and audit outputs |

## Final Reproduction Checks

```bash
python scripts/secret_scan.py
python scripts/verify_release.py
pytest -q
python scripts/verify_results.py
git status --short
```

Generated raw runs and local gates should remain untracked. A difference in live model output is possible even with a pinned snapshot; the experiment therefore records payload hashes, schema validity, token usage, model identifiers, fallback behavior, and system-level outcomes rather than assuming identical natural-language reasoning.
