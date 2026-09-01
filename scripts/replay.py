from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

from ojcoms_poc.config import load_config
from ojcoms_poc.runner import SumoExperimentRunner


IGNORED_SUMMARY_FIELDS = {
    "api_mode",
    "audit_log_bytes",
    "local_process_cpu_s",
    "local_process_rss_bytes",
    "policy_check_p50_ms",
    "policy_check_p95_ms",
    "policy_check_p99_ms",
    "run_id",
    "started_utc",
    "wall_clock_s",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def equal_value(left: Any, right: Any) -> bool:
    if isinstance(left, float) and isinstance(right, float):
        return math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-12)
    return left == right


def main() -> None:
    parser = argparse.ArgumentParser(description="Exactly replay one live agentic run")
    parser.add_argument("source_run_dir", type=Path)
    parser.add_argument("--config", default="configs/experiment.yaml")
    args = parser.parse_args()
    config = load_config(args.config)
    source = args.source_run_dir.resolve()
    original = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    calls = source / "api_calls.jsonl"
    if not calls.exists():
        raise FileNotFoundError(calls)
    tag = f"replay_{original['run_id']}"
    replay = SumoExperimentRunner(config).run(
        original["controller"],
        original["scenario"],
        int(original["seed"]),
        phase="replay",
        run_tag=tag,
        model_override=original["api_model"],
        replay_api_calls=calls,
        ssm_probability=float(original["ssm_probability"]),
    )
    replay_dir = config.root / "artifacts" / "raw" / "replay" / tag
    mismatches = {
        key: {"original": value, "replay": replay.get(key)}
        for key, value in original.items()
        if key not in IGNORED_SUMMARY_FIELDS and not equal_value(value, replay.get(key))
    }
    log_hashes = {
        name: {"original": digest(source / name), "replay": digest(replay_dir / name)}
        for name in ("decisions.jsonl", "policy_decisions.jsonl")
    }
    logs_exact = all(row["original"] == row["replay"] for row in log_hashes.values())
    validation = {
        "source_run": str(source),
        "source_api_calls_sha256": digest(calls),
        "replay_run": str(replay_dir),
        "scientific_summary_exact": not mismatches,
        "decision_logs_exact": logs_exact,
        "summary_mismatches": mismatches,
        "decision_log_hashes": log_hashes,
        "passed": not mismatches and logs_exact,
    }
    (replay_dir / "replay_validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(validation, indent=2, sort_keys=True))
    if not validation["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
