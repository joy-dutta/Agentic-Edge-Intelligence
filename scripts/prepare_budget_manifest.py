from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ojcoms_poc.budget import BudgetLedger
from ojcoms_poc.config import load_config


CALLS = {
    "primary": 6_896,
    "validation": 236,
    "followup": 1_240,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a post-pilot API budget manifest")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--phase", choices=tuple(CALLS), required=True)
    parser.add_argument("--pilot-phase", default="pilot_corrected_v4")
    args = parser.parse_args()
    config = load_config(args.config)
    root = config.root
    openai_config = config.section("openai")
    budget = config.section("budget")
    phase = args.phase
    model = str(
        openai_config["validation_model"]
        if phase == "validation"
        else openai_config["primary_model"]
    )
    artifacts = config.resolve(config.section("paths")["artifacts"])
    ledger = BudgetLedger(
        artifacts / "logs" / "api_usage.jsonl",
        openai_config["prices_per_million"],
        float(budget["local_limit_usd"]),
        budget["phase_limits_usd"],
        int(budget["max_request_attempts"]),
        budget["phase_call_limits"],
    )
    pilot_rows = []
    pilot_root = artifacts / "raw" / args.pilot_phase
    for run_dir in sorted(path for path in pilot_root.iterdir() if path.is_dir()):
        if not (run_dir / "summary.json").exists():
            continue
        audit_path = run_dir / "api_calls.jsonl"
        if not audit_path.exists():
            continue
        pilot_rows.extend(
            json.loads(line)
            for line in audit_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        )
    billed_rows = [
        row
        for row in pilot_rows
        if row.get("model") == str(openai_config["primary_model"])
        and row.get("input_tokens") is not None
        and row.get("output_tokens") is not None
    ]
    successful_rows = [row for row in billed_rows if row.get("schema_valid") is True]
    if not successful_rows:
        raise RuntimeError(
            f"No successful live pilot usage is available in {args.pilot_phase}"
        )
    input_values = [int(row["input_tokens"]) for row in billed_rows]
    output_values = [int(row["output_tokens"]) for row in billed_rows]
    expected_input = int(math.ceil(float(np.mean(input_values))))
    expected_output = int(math.ceil(float(np.mean(output_values))))
    planned = CALLS[phase]
    worst_input = int(openai_config["worst_case_billed_input_tokens"])
    worst_output = int(openai_config["max_output_tokens"])
    expected_cost = planned * ledger.estimate_cost(
        model, expected_input, expected_output
    )
    worst_cost = planned * ledger.estimate_cost(model, worst_input, worst_output)
    phase_limit = float(budget["phase_limits_usd"][phase])
    manifest = {
        "phase": phase,
        "created_utc": datetime.now(UTC).isoformat(),
        "model": model,
        "planned_request_ceiling": planned,
        "pilot_artifact_phase": args.pilot_phase,
        "pilot_billed_calls": len(billed_rows),
        "pilot_successful_calls": len(successful_rows),
        "pilot_invalid_responses": len(billed_rows) - len(successful_rows),
        "pilot_observed_input_tokens": {
            "mean": expected_input,
            "p95": int(math.ceil(float(np.quantile(input_values, 0.95)))),
            "maximum": max(input_values),
        },
        "pilot_observed_output_tokens": {
            "mean": expected_output,
            "p95": int(math.ceil(float(np.quantile(output_values, 0.95)))),
            "maximum": max(output_values),
        },
        "expected_tokens_per_request": {
            "input": expected_input,
            "output_including_reasoning": expected_output,
        },
        "worst_case_tokens_per_request": {
            "input": worst_input,
            "output_including_reasoning": worst_output,
        },
        "prices_per_million_usd": openai_config["prices_per_million"][model],
        "price_source": f"https://developers.openai.com/api/docs/models/{model.split('-2026-')[0]}",
        "price_verified_utc_date": datetime.now(UTC).date().isoformat(),
        "expected_cost_usd": round(expected_cost, 6),
        "worst_case_cost_usd": round(worst_cost, 6),
        "phase_hard_limit_usd": phase_limit,
        "proceed": worst_cost <= phase_limit,
        "note": "Token sizing uses billed calls only from completed runs in the named current-protocol pilot phase. A false proceed value blocks the phase.",
    }
    output = root / "configs" / f"budget_manifest_{phase}.json"
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
