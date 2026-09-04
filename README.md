# Governed Agentic Edge Traffic Control

[![CI](https://github.com/joy-dutta/Agentic-Edge-Intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/joy-dutta/Agentic-Edge-Intelligence/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](pyproject.toml)

This repository contains a reproducible proof of concept for **bounded LLM-assisted control at the network edge**. The test case is urban traffic-signal control, where decisions are time-sensitive, neighboring intersections exchange compact context, and unsuitable actions can immediately affect a physical process.

The central design principle is simple: the LLM assists a dependable local controller; it does not replace it. The local loop continues to operate every five simulated seconds. The LLM periodically proposes a small, structured supervisory intent. A deterministic policy shield checks that intent before execution, and invalid, unsafe, stale, late, or unavailable responses automatically fall back to local control.

## What This Experiment Tests

The evaluation separates four practical questions:

1. **Placement:** What changes when control depends on a delayed WAN path instead of remaining at the edge?
2. **Bounded autonomy:** Can an LLM contribute contextual supervision without entering the hard real-time loop?
3. **Governance:** Can explicit policy checks prevent rule-breaking proposals from reaching the controller?
4. **Resilience:** Does deterministic fallback keep the physical process running when sensing, communication, peer information, or the remote model is impaired?

The frozen evaluation contains **520 confirmatory simulation runs** across five scenarios and seven controller configurations. A separately registered **80-run exploratory follow-up** checks peer-context behavior on the Cologne-8 and Cologne-3 networks.

## System at a Glance

```text
SUMO traffic state
        |
        +--> deterministic local controller --> traffic signals
        |
        +--> bounded observation --> LLM supervisor --> structured intent
                                                    |
                                             policy shield
                                                    |
                         accepted intent -----------+
                         rejected/late/invalid -----> local fallback
```

The simulator advances individual vehicles at one-second resolution. Signal control runs every five seconds. LLM supervision is requested every 120 simulated seconds, with additional rate-limited requests for declared incident, emergency, sensing, or trust events. The experiment uses the public RESCO Cologne scenarios and SUMO 1.27.1.

## Main Evidence

The repository includes the frozen configurations, source code, tests, controller checkpoints, processed run-level data, and result tables. No manuscript or publication figure is included.

The completed evaluation demonstrates that:

- Governed edge supervision reduced mean and P95 vehicle time loss relative to the WAN-dependent cloud controller in all five confirmatory scenarios.
- Governed control retained performance comparable to the strong deterministic Local MaxWave baseline after correction for multiple comparisons.
- Edge supervision reduced application-level WAN traffic by approximately 95% relative to cloud control.
- The policy shield blocked all 1,191 proposals that violated the declared rules, with zero such proposals executed by the governed controller.
- The deterministic loop continued during invalid responses, timeouts, a remote-service error, and injected API outages.

Exact estimates, confidence intervals, statistical tests, and interpretation boundaries are reported in [docs/RESULTS.md](docs/RESULTS.md). Machine-readable values are under [`artifacts/tables`](artifacts/tables).

## Find What You Need

You do not need to understand the whole repository before using it. Start with the row that matches your goal; every linked folder has its own README explaining the files inside and the next command to run.

| I want to... | Start here |
|---|---|
| Understand the experiment and its seven controllers | [Experiment design](docs/EXPERIMENT_DESIGN.md) |
| Verify the released results without SUMO or an API key | [Processed data](data/processed/README.md) and [result tables](artifacts/tables/README.md) |
| Reproduce the simulation | [Reproducibility guide](docs/REPRODUCIBILITY.md) |
| Understand where raw outputs come from | [Raw-output guide](artifacts/raw/README.md) |
| Inspect or change a frozen setting | [Configuration guide](configs/README.md) |
| Understand the implementation | [Source-code guide](src/ojcoms_poc/README.md) |
| Find the right command | [Script guide](scripts/README.md) |
| Use the containers or network harness | [Docker guide](docker/README.md) |
| Run or extend the tests | [Test guide](tests/README.md) |

## Reproducibility Paths

Choose the level that matches what you want to verify:

| Level | What it verifies | API calls | Typical starting point |
|---|---|---:|---|
| A | Included tables, run counts, paired statistics, and frozen hashes | None | `python scripts/verify_release.py` |
| B | Deterministic controllers and SUMO scenario execution | None | `python scripts/pilot.py --mode offline` |
| C | Full LLM-assisted behavior with the pinned API model | Yes | Contract probe, live pilot, then frozen sweep |

Level A is suitable for a quick repository audit. Level B verifies the traffic simulator, deterministic controllers, incidents, sensors, network models, and metrics. Level C requires the user's own OpenAI API key and is protected by the local budget gates described in [docs/API_AND_BUDGET.md](docs/API_AND_BUDGET.md).

## Quick Start with Docker

Docker on Linux or WSL2 is the recommended path because it isolates SUMO and Python dependencies from the host.

```bash
git clone https://github.com/joy-dutta/Agentic-Edge-Intelligence.git
cd Agentic-Edge-Intelligence

docker compose -f docker/compose.yaml build experiment
docker compose -f docker/compose.yaml run --rm experiment python scripts/verify_release.py
docker compose -f docker/compose.yaml run --rm experiment python -m pytest -q
docker compose -f docker/compose.yaml run --rm experiment python scripts/verify_results.py
docker compose -f docker/compose.yaml run --rm experiment python scripts/fetch_resco.py
docker compose -f docker/compose.yaml run --rm experiment python scripts/pilot.py --mode offline --phase pilot
```

The RESCO source is downloaded at its pinned commit and patched locally. It is not redistributed because its upstream CC-BY-NC-SA-3.0 terms remain authoritative.

## Native Python Setup

Python 3.12 is required.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements/base.lock
python -m pip install --no-deps -e .

python scripts/verify_release.py
python -m pytest -q
python scripts/verify_results.py
python scripts/fetch_resco.py
python scripts/pilot.py --mode offline --phase pilot
```

On PowerShell, activate the environment with `.venv\Scripts\Activate.ps1`. Use a short checkout path or enable Windows long-path support because the SUMO data wheel contains deeply nested paths. Full platform-specific instructions are in [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md).

## Documentation Map

- [Experiment design](docs/EXPERIMENT_DESIGN.md): controllers, scenarios, run matrix, metrics, and statistics.
- [Reproduction guide](docs/REPRODUCIBILITY.md): complete Level A, B, and C procedures.
- [API privacy and budget](docs/API_AND_BUDGET.md): safe key handling and cost gates.
- [Results](docs/RESULTS.md): concise table-based evidence with no publication figures.
- [Data dictionary](docs/data_dictionary.md): meaning and units of exported fields.
- [Scenario provenance](scenarios/README.md): RESCO source, commit, patch, and scenario construction.
- [Network harness](docs/network_harness.md): TLS/MQTT, `tc netem`, and packet-capture validation.
- [Repository layout](docs/REPOSITORY_LAYOUT.md): where to find code, configurations, outputs, and tests.
- [Documentation index](docs/README.md): a plain-language guide to every document.

## Reproducibility Commitments

- Exact SUMO, Python-package, model-snapshot, RESCO-commit, seed, prompt, policy, and container inputs are pinned.
- Confirmatory and exploratory protocols remain separate.
- A simulation run, not an individual vehicle, is the statistical unit.
- Paired seeds compare controllers on the same traffic realization.
- Live requests use strict structured output, `store: false`, bounded tokens, capped retries, and an append-only cost ledger.
- CI performs unit tests, a secret scan, release-integrity checks, and result-table verification without making API calls.

## Scope

This is a controlled SUMO microsimulation, not a field deployment. It is intended to make the architecture, governance controls, failure handling, and evaluation procedure inspectable and repeatable. It does not connect to a physical traffic signal or claim that an LLM alone provides real-time or universal physical safety.

## Associated Publication

This repository supports a manuscript that is currently under peer review. To preserve the confidentiality of the review process, the manuscript title and publication details are not included at this stage. After acceptance, this section will be updated with the complete citation, DOI, and official publication link.

Researchers who use this repository, its experimental methodology, released results, or the associated agentic edge intelligence framework are kindly requested to cite the published article once the final citation becomes available. Until then, the software and released result tables can be cited using the repository's [CITATION.cff](CITATION.cff) file.

## License and Citation

Repository code is released under the [MIT License](LICENSE). RESCO scenarios retain their upstream license. To cite the software, use [`CITATION.cff`](CITATION.cff). Contributions are described in [.github/CONTRIBUTING.md](.github/CONTRIBUTING.md), and private vulnerability reports are covered by [.github/SECURITY.md](.github/SECURITY.md).
