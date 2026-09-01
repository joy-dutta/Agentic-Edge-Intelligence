# Security and Privacy

## Reporting a Vulnerability

Please do not open a public issue for a vulnerability that could expose credentials, bypass the policy shield, evade the cost gate, or alter experiment evidence without detection. Use GitHub's private security-advisory workflow for this repository.

Include the affected file or component, the conditions required to reproduce the issue, its likely impact, and a minimal proof of concept that contains no real credential or personal data.

## Credential Rules

- Never commit an API key, `.env` file, cloud-account identifier, private certificate, or local key-source path.
- Use the `OPENAI_API_KEY` process environment variable only for live reproduction.
- Keep `configs/platform_budget_gate.json` and `configs/api_contract_gate.json` local. Both are ignored by Git.
- Generated TLS keys under `artifacts/network_tls` are disposable test credentials and are also ignored.
- Run `python scripts/secret_scan.py` and `python scripts/verify_release.py` before every commit intended for release.

The repository's CI never receives an API key and never makes a billable API request.

