# Frozen Experiment Configuration

This folder is the experiment's control panel. It records what was planned, what changed before execution, which seeds and systems were used, and how API spending was bounded. Do not casually edit these files when reproducing the released evaluation; a changed configuration defines a new experiment.

| File | Purpose |
|---|---|
| `experiment.yaml` | Main Cologne-8 protocol: paths, scenarios, seven controllers, timing, network profiles, policy limits, seeds, metrics, and model settings. |
| `followup_cologne8.yaml` | Cologne-8 configuration for the separate high-interaction peer-context follow-up. |
| `followup_cologne3.yaml` | Equivalent follow-up configuration on the smaller Cologne-3 corridor. |
| `followup_protocol.yaml` | Pre-specified exploratory question, analysis rule, seeds, and interpretation boundary. |
| `followup_protocol_amendment_001.yaml` | Pre-run correction to keep the Cologne-3 lane closure connected. |
| `protocol_amendment_001_pre_pilot.yaml` | Corrections made before final execution, including deterministic seeding and measurement fixes. |
| `protocol_amendment_002_primary_recovery.yaml` | Documents the full matrix restart after SUMO's SSM failure and withdrawal of unavailable SSM endpoints. |
| `frozen_protocol_manifest.json` | Frozen software versions, seed sets, and hashes of protocol-critical files. |
| `prompt_policy_changelog.md` | Human-readable record of the prompt and policy version. |
| `prompts/supervisor_v1.txt` | Exact system instruction used for the structured LLM supervisor. |
| `ssm_controlled_junctions.txt` | Eight Cologne-8 junction identifiers selected for SSM instrumentation. |
| `ssm_controlled_junctions_cologne3.txt` | Three Cologne-3 junction identifiers used in the follow-up configuration. |
| `budget_manifest_pilot.json` | Pre-run request and cost ceilings for the pilot. |
| `budget_manifest_primary.json` | Cost estimate and hard local phase cap for the confirmatory live matrix. |
| `budget_manifest_validation.json` | Cost controls for the model-size validation. |
| `budget_manifest_followup.json` | Cost controls for the exploratory coordination follow-up. |
| `platform_budget_gate.example.json` | Safe template that a reproducer copies locally after checking their own API-project limit. |
| `release_manifest.json` | SHA-256 and byte-size inventory of the public repository files. Rebuilt before release. |

Two local gate files may appear but are deliberately ignored: `platform_budget_gate.json` records the reproducer's own account-limit acknowledgement, and `api_contract_gate.json` records the one-call model/schema check. Neither should be committed.

For a guided reproduction, use [`docs/REPRODUCIBILITY.md`](../docs/REPRODUCIBILITY.md). For API privacy and cost controls, use [`docs/API_AND_BUDGET.md`](../docs/API_AND_BUDGET.md).
