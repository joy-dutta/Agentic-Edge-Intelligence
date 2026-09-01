# API Privacy and Budget Controls

Live reproduction is optional. Unit tests, result verification, deterministic controllers, and offline SUMO runs make no OpenAI API calls.

## Use Your Own Key

The repository does not contain an API key and does not read a key from another source file. Live scripts use only the `OPENAI_API_KEY` environment variable inherited by the process.

PowerShell 7:

```powershell
$env:OPENAI_API_KEY = Read-Host -MaskInput "OpenAI API key"
python scripts/check_api_access.py
```

Bash:

```bash
read -rsp "OpenAI API key: " OPENAI_API_KEY && echo
export OPENAI_API_KEY
python scripts/check_api_access.py
```

Remove the variable when finished:

```powershell
Remove-Item Env:OPENAI_API_KEY
```

```bash
unset OPENAI_API_KEY
```

Do not place a real value in `.env.example`, a configuration file, a shell script, a notebook, an issue, or a terminal transcript. `.env`, `.env.*`, `.secrets`, private keys, and generated local gates are ignored by Git.

## Three Independent Gates

A live inference request is allowed only when all three layers pass.

1. **Platform gate:** the user records an account-level limit or explicitly acknowledges that the Platform limit is soft.
2. **Protocol gate:** phase cost and call manifests must be within the frozen limits.
3. **Crash-safe local ledger:** the program reserves worst-case cost before every attempt and refuses the next request if it could exceed a local, phase, or attempt ceiling.

The software ledger is an experiment safeguard, not a replacement for the billing controls in the user's OpenAI Platform account.

## Create the Local Platform Gate

Copy the non-sensitive template:

```bash
cp configs/platform_budget_gate.example.json configs/platform_budget_gate.json
```

PowerShell:

```powershell
Copy-Item configs\platform_budget_gate.example.json configs\platform_budget_gate.json
```

Edit only the local copy after verifying the limit in your own account. The file is ignored and must not be committed. A verified hard-limit record can use:

```json
{
  "hard_limit_verified": true,
  "platform_hard_limit_usd": 20.0,
  "verified_utc": "YYYY-MM-DDTHH:MM:SSZ",
  "verification_note": "Verified by the account owner before live reproduction."
}
```

If the account exposes only a soft limit, use the fields in the provided example and acknowledge the lower local hard ceiling explicitly.

## Frozen Local Limits

| Scope | Maximum estimated cost | Request-attempt ceiling |
|---|---:|---:|
| Whole experiment ledger | USD 16 | 10,000 |
| Pilot | USD 1 | 300 |
| Confirmatory live phase | USD 10 | 7,000 |
| Model validation | USD 2 | 1,000 |
| Coordination follow-up | USD 3 | 1,500 |

Unused phase allowance is not transferred automatically. The completed experiment recorded an estimated total API cost of USD 8.90547594 across the pilot, confirmatory, audits, model validation, and follow-up phases. Actual charges for a new reproduction can differ because API pricing and model availability may change.

## Safe Live Sequence

Do not start with the full sweep.

```bash
# 1. Confirm credential and pinned-model access. No inference call.
python scripts/check_api_access.py

# 2. Make one schema-constrained inference and write the local contract gate.
python scripts/probe_responses_contract.py

# 3. Run the two-seed live pilot.
python scripts/pilot.py --mode live --phase pilot

# 4. Build and inspect the pilot acceptance report and cost ledger.
python scripts/pilot_report.py --phase pilot

# 5. Only after every gate passes, run the frozen live matrix.
python scripts/full_sweep.py --mode live --workers 1
```

The generated `configs/api_contract_gate.json`, API audit logs, reservations, and cost ledger remain local and ignored. The API client uses the pinned model snapshot, bounded token limits, at most two retries in the frozen sweep, strict structured output, and `store: false`.

## Before Sharing a Clone or Archive

Run:

```bash
python scripts/secret_scan.py
python scripts/verify_release.py
git status --short
```

The release verifier fails if a local gate, credential-like value, private key, manuscript, or result figure is present in the package.

