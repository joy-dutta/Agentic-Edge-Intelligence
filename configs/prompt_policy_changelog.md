# Prompt And Policy Changelog

## Protocol 1.0.0

- Supervisor prompt: `configs/prompts/supervisor_v1.txt`.
- Structured response model: `CorridorResponse` in `src/ojcoms_poc/models.py`.
- Policy limits: `configs/experiment.yaml`.

No prompt or safety-limit change is permitted after confirmatory runs begin. The
pre-pilot controller and measurement corrections are recorded separately in
`configs/protocol_amendment_001_pre_pilot.yaml`. Any post-result redesign must be
precommitted in `configs/followup_protocol.yaml` and reported as exploratory.
