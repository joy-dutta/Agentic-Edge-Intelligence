# Pinned Python Dependencies

The experiment uses separate lock files so readers install only what their task needs.

| File | Use it for |
|---|---|
| `base.lock` | Main source package, SUMO evaluation, analysis, live API client, and tests. |
| `network.lock` | Lightweight Docker network harness with MQTT and schema validation. |
| `idqn.lock` | Optional frozen-IDQN sensitivity study; it includes `base.lock` and adds Torch, PFRL, Gym, and RESCO configuration support. |

For the normal native setup:

```bash
python -m pip install -r requirements/base.lock
python -m pip install --no-deps -e .
```

Use Python 3.12. Dependency versions are intentionally exact for reproducibility; an automated update proposal should be evaluated as a new environment rather than merged blindly into the frozen release.
