## Purpose

Describe the problem and the smallest change that addresses it.

## Reproducibility Impact

- [ ] No frozen protocol, seed, prompt, policy, controller, metric, or output schema changes.
- [ ] Any intended protocol change is versioned and clearly separated from existing confirmatory results.
- [ ] Tests cover the behavioral change.
- [ ] Result tables are machine-readable and identify confirmatory versus exploratory analysis.

## Release Checks

- [ ] `python scripts/secret_scan.py`
- [ ] `python scripts/verify_release.py`
- [ ] `pytest -q`
- [ ] `python scripts/verify_results.py`
- [ ] No credentials, local gates, private paths, manuscripts, or publication figures are included.

