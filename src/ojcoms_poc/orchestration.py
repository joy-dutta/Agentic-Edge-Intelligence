from __future__ import annotations

import json
import os
import random
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

from .config import ExperimentConfig
from .file_lock import append_jsonl_locked
from .runner import AGENTIC, SumoExperimentRunner


@dataclass(frozen=True)
class RunSpec:
    controller: str
    scenario: str
    seed: int
    model: str | None = None

    @property
    def run_id(self) -> str:
        suffix = f"_{self.model}" if self.model else ""
        return f"{self.scenario}_{self.controller}_{self.seed}{suffix}"


def planned_calls(spec: RunSpec) -> int:
    if spec.controller not in AGENTIC:
        return 0
    scheduled = 30
    event_calls = {
        "S0": 0,
        "S1": 0,
        "S2": 1,
        "S3": 3,
        "S4": 4,
    }
    return scheduled + event_calls[spec.scenario]


def verify_live_gate(config: ExperimentConfig, phase: str) -> dict:
    gate_path = config.root / "configs" / "platform_budget_gate.json"
    if not gate_path.exists():
        raise RuntimeError(
            "Live API gate is closed: configs/platform_budget_gate.json is absent"
        )
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    budget = config.section("budget")
    hard_verified = gate.get("hard_limit_verified") is True
    soft_acknowledged = (
        gate.get("platform_limit_type") == "soft"
        and gate.get("user_acknowledged_soft_limit") is True
        and gate.get("local_hard_cap_authorized") is True
        and gate.get("protocol_deviation_documented") is True
    )
    if not hard_verified and not soft_acknowledged:
        raise RuntimeError(
            "Live API gate is closed: neither the hard Platform gate nor the "
            "documented soft-Platform/local-hard deviation is verified"
        )
    platform_limit_key = (
        "platform_hard_limit_usd" if hard_verified else "platform_soft_limit_usd"
    )
    if float(gate.get(platform_limit_key, float("inf"))) > float(
        budget["platform_limit_usd"]
    ):
        raise RuntimeError("Live API gate is closed: Platform limit exceeds protocol")
    if not hard_verified and float(
        gate.get("local_hard_limit_usd", float("inf"))
    ) != float(budget["local_limit_usd"]):
        raise RuntimeError("Live API gate is closed: local hard limit does not match protocol")
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Live API gate is closed: OPENAI_API_KEY is unavailable")
    if phase not in budget["phase_limits_usd"]:
        raise RuntimeError(f"No budget allowance is configured for phase {phase!r}")
    manifest_path = config.root / "configs" / f"budget_manifest_{phase}.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Live API gate is closed: {manifest_path.name} is absent")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != phase or manifest.get("proceed") is not True:
        raise RuntimeError(f"Live API gate is closed: {manifest_path.name} is not approved")
    phase_limit = float(budget["phase_limits_usd"][phase])
    if float(manifest.get("worst_case_cost_usd", float("inf"))) > phase_limit:
        raise RuntimeError(f"Live API gate is closed: {manifest_path.name} exceeds phase cost")
    call_limit = int(budget["phase_call_limits"][phase])
    if int(manifest.get("planned_request_ceiling", call_limit + 1)) > call_limit:
        raise RuntimeError(f"Live API gate is closed: {manifest_path.name} exceeds call limit")
    return gate


def run_matrix(
    config: ExperimentConfig,
    specs: Iterable[RunSpec],
    *,
    phase: str,
    shuffle_seed: int,
    workers: int = 1,
) -> list[dict]:
    if workers < 1:
        raise ValueError("workers must be at least one")
    ordered = list(specs)
    random.Random(shuffle_seed).shuffle(ordered)
    if any(spec.controller in AGENTIC for spec in ordered):
        budget_phases = config.section("budget")["phase_limits_usd"]
        if phase in budget_phases:
            budget_phase = phase
        elif phase.startswith("pilot_"):
            budget_phase = "pilot"
        else:
            raise RuntimeError(f"No budget allowance is configured for phase {phase!r}")
        verify_live_gate(config, budget_phase)

    if workers > 1 and len(ordered) > 1:
        chunks = [ordered[index::workers] for index in range(workers)]
        chunks = [chunk for chunk in chunks if chunk]
        with ProcessPoolExecutor(max_workers=len(chunks)) as executor:
            futures = [
                executor.submit(_run_ordered, config, chunk, phase)
                for chunk in chunks
            ]
            completed = []
            for future in futures:
                completed.extend(future.result())
            return completed
    return _run_ordered(config, ordered, phase)


def _run_ordered(
    config: ExperimentConfig, ordered: list[RunSpec], phase: str
) -> list[dict]:
    transcript = (
        config.resolve(config.section("paths")["artifacts"])
        / "logs"
        / "command_transcript.jsonl"
    )
    transcript.parent.mkdir(parents=True, exist_ok=True)
    runner = SumoExperimentRunner(config)
    completed: list[dict] = []
    for spec in ordered:
        run_dir = (
            config.resolve(config.section("paths")["artifacts"])
            / "raw"
            / phase
            / spec.run_id
        )
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            completed.append(json.loads(summary_path.read_text(encoding="utf-8")))
            continue
        if run_dir.exists():
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            preserved_dir = run_dir.with_name(f"{run_dir.name}_incomplete_{stamp}")
            run_dir.rename(preserved_dir)
            recovery_row = {
                "completed_utc": datetime.now(UTC).isoformat(),
                "phase": phase,
                "run": asdict(spec),
                "run_id": spec.run_id,
                "status": "incomplete_attempt_preserved",
                "preserved_path": str(preserved_dir.relative_to(config.root)),
            }
            append_jsonl_locked(transcript, recovery_row)
        started = datetime.now(UTC).isoformat()
        try:
            summary = runner.run(
                spec.controller,
                spec.scenario,
                spec.seed,
                phase=phase,
                run_tag=spec.run_id,
                model_override=spec.model,
            )
        except Exception as exc:
            row = {
                "started_utc": started,
                "completed_utc": datetime.now(UTC).isoformat(),
                "phase": phase,
                "run": asdict(spec),
                "run_id": spec.run_id,
                "status": "failed",
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            append_jsonl_locked(transcript, row)
            raise
        row = {
            "started_utc": started,
            "completed_utc": datetime.now(UTC).isoformat(),
            "phase": phase,
            "run": asdict(spec),
            "run_id": spec.run_id,
            "status": "completed",
            "summary": str(summary_path.relative_to(config.root)),
        }
        append_jsonl_locked(transcript, row)
        completed.append(summary)
    return completed
