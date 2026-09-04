# Test Fixtures

`replay_api_calls.jsonl` is a small, redacted recording used to test exact-response replay without contacting the API. It contains canonical payload hashes and structured responses, not an API key or an unredacted private conversation.

Fixtures should stay small, deterministic, and safe to publish. A new fixture must be exercised by an offline test and pass `python scripts/secret_scan.py`.
