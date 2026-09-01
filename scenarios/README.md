# Scenario Provenance

The experiment downloads RESCO at commit
`f1ed9a174f8de41fc9d8689373b836bc882570dc` and uses its Cologne-8 environment
without redrawing the network, routes, or phase programs. The upstream scenario
is licensed CC-BY-NC-SA-3.0 and is therefore excluded from this repository.

Run `python scripts/fetch_resco.py` to clone the exact commit and apply the tracked
determinism/evaluation patch. The script refuses a different remote or commit.

Scenario S0 preserves nominal demand. S1 scales demand by 1.2. S2 adds a declared
lane incident and emergency route. S3 adds impaired WAN, sensor error/loss, a
detector outage, API outage, and authenticated stale peer state. S4 adds replayed,
unauthenticated malicious peer content. Exact values and event times are frozen in
`configs/experiment.yaml`.
