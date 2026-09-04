# Runtime Logs

Live LLM-assisted runs write their append-only accounting records here. A fresh clone contains no runtime log because logs are generated for the reproducer's own API project.

| Generated file | Meaning |
|---|---|
| `api_usage.jsonl` | Completed request status, token usage, and estimated cost. |
| `api_usage_reservations.jsonl` | Cost reserved before each request so concurrent workers cannot exceed the local phase cap. |
| Other phase-labelled logs | The same records kept separately for a pilot, confirmatory run, validation, or follow-up. |

The logs are designed to support cost and failure audits. They must never contain `OPENAI_API_KEY`; API payloads stored elsewhere are redacted. See [`docs/API_AND_BUDGET.md`](../../docs/API_AND_BUDGET.md) before a live run.
