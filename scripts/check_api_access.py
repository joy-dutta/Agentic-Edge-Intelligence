"""Non-billable credential and pinned-model access check."""

from __future__ import annotations

import json
import os

from openai import OpenAI


MODEL = "gpt-5.4-nano-2026-03-17"


def main() -> None:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key.startswith("sk-"):
        raise RuntimeError("OPENAI_API_KEY is missing or malformed")
    client = OpenAI(max_retries=0, timeout=20)
    model = client.models.retrieve(MODEL)
    print(
        json.dumps(
            {
                "credential_present": True,
                "project_scoped_format": key.startswith("sk-proj-"),
                "pinned_model_access": model.id == MODEL,
                "model": model.id,
                "billable_inference_calls": 0,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
