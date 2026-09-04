# Upstream Reproducibility Patch

`resco_v2_deterministic_seed.patch` is applied to the pinned upstream RESCO checkout. It ensures the declared seed reaches SUMO and the relevant Python, NumPy, and Torch random-number generators, making paired traffic and IDQN runs repeatable.

Do not apply the patch by hand. From the repository root, run:

```bash
python scripts/fetch_resco.py
```

The fetch script verifies the upstream URL and commit before applying the patch, and refuses an unexpected checkout. The RESCO source itself is not redistributed; its origin, exact commit, and license are documented in [`scenarios/README.md`](../scenarios/README.md).
