# Docker Environments

Docker is the recommended reproduction path on Linux or WSL2. These files keep host Python and SUMO installations separate from the experiment.

| File | Purpose |
|---|---|
| `release.Dockerfile` | Main public reproduction image with the pinned Python and SUMO dependencies, source, tests, and verification tools. |
| `experiment.Dockerfile` | Minimal experiment image whose hash was frozen with the original protocol. It is retained as protocol evidence. |
| `network-harness.Dockerfile` | Small SUMO/Python image with Linux traffic-control tools for the MQTT communication harness. |
| `compose.yaml` | Defines the main `experiment` service and the optional broker, packet capture, edge, cloud, and simulator services. |

Run Compose commands from the repository root and name this file explicitly:

```bash
docker compose -f docker/compose.yaml build experiment
docker compose -f docker/compose.yaml run --rm experiment python scripts/verify_release.py
docker compose -f docker/compose.yaml run --rm experiment python -m pytest -q
docker compose -f docker/compose.yaml run --rm experiment python scripts/verify_results.py
```

The experiment service bind-mounts the repository at `/workspace`, so fetched RESCO files and generated outputs remain on the host. Compose receives `OPENAI_API_KEY` only from the current process environment; no key is built into an image.

For the complete workflow, read [`docs/REPRODUCIBILITY.md`](../docs/REPRODUCIBILITY.md). For the multi-container communication test, read [`docs/network_harness.md`](../docs/network_harness.md).
