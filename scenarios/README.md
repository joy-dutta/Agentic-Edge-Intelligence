# Scenario Provenance

The experiment uses the public [RESCO traffic-signal benchmark](https://github.com/Pi-Star-Lab/RESCO) at commit `f1ed9a174f8de41fc9d8689373b836bc882570dc`. Cologne-8 supplies the eight-signal urban network for the confirmatory evaluation; Cologne-3 supplies the smaller three-signal corridor for the separate cross-network follow-up. The experiment keeps the benchmark road geometry, routes, demand, and signal programs rather than redrawing them.

RESCO remains under its upstream CC-BY-NC-SA-3.0 license and is therefore fetched rather than copied into this MIT-licensed repository. From the repository root, run:

```bash
python scripts/fetch_resco.py
```

The script clones RESCO into `external/RESCO`, checks the exact remote and commit, and applies `patches/resco_v2_deterministic_seed.patch`. It refuses an unexpected checkout so a silent scenario change cannot enter the evaluation.

## Five Confirmatory Conditions

| Case | Plain-language meaning |
|---|---|
| S0 | Normal morning traffic with no injected incident or system fault. |
| S1 | A busier morning with traffic demand increased by 20%. |
| S2 | A 600-second lane closure with an emergency vehicle introduced during the disruption. |
| S3 | The same incident while sensing, WAN communication, the remote service, and peer freshness are impaired. |
| S4 | The incident plus misleading stale, replayed, and unauthenticated messages from a faulty or compromised neighbor. |

The exploratory follow-up combines 1.3-times demand with a longer 900-second lane closure on Cologne-8 and Cologne-3. Exact lane identifiers, event times, fault rates, seeds, and network profiles are frozen in `configs/experiment.yaml` and `configs/followup_cologne*.yaml`.
