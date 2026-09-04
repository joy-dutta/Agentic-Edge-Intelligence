# Supervisor Prompt

`supervisor_v1.txt` is the exact frozen instruction supplied to the LLM supervisor. It asks for a small structured corridor response rather than free-form signal commands. The runtime validates the response against the Pydantic schema in `src/ojcoms_poc/models.py`, then sends each proposed intent through the deterministic policy shield.

The prompt hash is recorded in `configs/frozen_protocol_manifest.json`. Editing the prompt means the released live results no longer represent the same protocol, so prompt experiments should use a new versioned file and a separate configuration.
