# Repository Layout

The repository is arranged so a first-time visitor can move from the research question to the evidence without guessing what a folder contains. Every main folder has a local README with its contents and common commands.

```text
.
|-- .github/               Contribution, security, automation, and CI files
|-- artifacts/             Released result tables and generated-output locations
|-- checkpoints/           Frozen IDQN sensitivity checkpoints
|-- configs/               Frozen protocols, prompts, seeds, policies, and budgets
|-- data/                  Included processed run-level evidence
|-- docker/                Containers and the Compose network harness
|-- docs/                  Experiment, result, and reproduction documentation
|-- network/               MQTT broker configuration
|-- patches/               Reproducibility patch applied to upstream RESCO
|-- requirements/          Pinned Python dependency sets
|-- scenarios/             Scenario origin and construction
|-- scripts/               Commands for runs, analyses, audits, and verification
|-- src/ojcoms_poc/        Experiment implementation
|-- tests/                 Offline unit and integration tests
|-- CITATION.cff           Software citation metadata
|-- LICENSE                Repository-code license
|-- pyproject.toml         Installable Python package metadata
`-- README.md              Project overview and first steps
```

## Why Some Files Stay at the Root

The root is deliberately small, but a few files remain there because standard tools look for them in that location. GitHub displays `README.md`, `LICENSE`, and `CITATION.cff`; Python packaging reads `pyproject.toml`; Git and Docker use the root ignore files; and `.env.example` documents the environment variable name without containing a credential.

## Generated Rather Than Published

The following paths are created locally and ignored:

| Path | What creates it |
|---|---|
| `external/RESCO` | `python scripts/fetch_resco.py` |
| `artifacts/raw` | Pilot and sweep commands |
| `artifacts/logs` | Live API budget and usage accounting |
| `artifacts/pcap` | Docker network-harness packet capture |
| `artifacts/network_tls` | Disposable local test certificates |
| `artifacts/figures` | Optional local analysis plots |
| `configs/platform_budget_gate.json` | The reproducer after checking their own account limit |
| `configs/api_contract_gate.json` | The one-call API schema probe |

The full completed raw archive is approximately 3.3 GiB and contains more than 10,000 generated files, so it is not placed in normal Git history. The exact processed run-level evidence and released statistical tables are included. See [the raw-output guide](../artifacts/raw/README.md) for regeneration instructions.

No manuscript, publication figure, API credential, or private authorization record belongs in this repository.
