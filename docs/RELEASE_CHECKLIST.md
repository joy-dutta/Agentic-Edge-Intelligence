# Public Release Checklist

## Scientific Content

- [x] Frozen confirmatory configuration is present.
- [x] Protocol amendments are versioned and dated.
- [x] Confirmatory and exploratory datasets remain separate.
- [x] Seeds, RESCO commit, SUMO version, model snapshots, prompt, and policy rules are pinned.
- [x] Processed run-level data and machine-readable result tables are included.
- [x] Table regeneration reproduces 520 runs, 383 summary rows, and 293 paired-comparison rows.
- [x] IDQN checkpoints include their configuration and SHA-256 manifest.

## Reproduction

- [x] Docker/WSL2 is the primary documented path.
- [x] Native Python setup is documented.
- [x] Analysis-only, offline SUMO, and live API paths are separated.
- [x] Fresh-clone unit tests do not require a pre-existing RESCO checkout.
- [x] CI makes no API calls and receives no API key.
- [x] A pinned public-release container is provided.

## Privacy and Scope

- [x] No API key or credential-like value is present.
- [x] No machine-specific key loader or private source path is present.
- [x] Local budget and API contract gates are ignored and absent.
- [x] No manuscript, publication figure, PDF, PNG, JPEG, or TeX source is included.
- [x] Result evidence is shared as CSV, JSON, and Parquet tables.
- [x] Internal handoffs and private authorization records are excluded.

## Before Push

- [ ] Rebuild `configs/release_manifest.json`.
- [ ] Run `python scripts/secret_scan.py`.
- [ ] Run `python scripts/verify_release.py`.
- [ ] Run `python scripts/verify_docs.py`.
- [ ] Run `pytest -q`.
- [ ] Run `python scripts/verify_results.py`.
- [ ] Review `git status --short` and the complete staged diff.
- [ ] Create a clean root commit so excluded material is absent from Git history.
- [ ] Confirm the destination remote is `https://github.com/joy-dutta/Agentic-Edge-Intelligence.git`.
- [ ] Push only after explicit owner approval.
