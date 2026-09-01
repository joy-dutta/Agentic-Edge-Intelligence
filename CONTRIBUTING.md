# Contributing

Contributions that improve reproducibility, controller correctness, measurement quality, platform portability, or documentation are welcome.

## Development Workflow

1. Create a focused branch.
2. Keep confirmatory behavior unchanged unless the change is explicitly versioned as a new protocol.
3. Add or update tests for every behavioral change.
4. Run the offline verification suite:

```bash
python scripts/secret_scan.py
python scripts/verify_release.py
python scripts/verify_docs.py
python -m pytest -q
python scripts/verify_results.py
```

5. Explain any effect on frozen configurations, output schemas, seeds, statistical tests, or expected costs.

Do not include credentials, manuscripts, publication figures, machine-specific paths, or unredacted API payloads in a pull request. New experimental claims should be accompanied by a registered configuration, disjoint seeds, a machine-readable result table, and a clear statement of whether the analysis is confirmatory or exploratory.
