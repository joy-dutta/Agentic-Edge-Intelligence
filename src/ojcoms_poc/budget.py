from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4

from .file_lock import interprocess_lock


class BudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True)
class UsageRecord:
    timestamp_utc: str
    phase: str
    model: str
    status: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    cost_usd: float
    request_id: str | None


class BudgetLedger:
    def __init__(
        self,
        path: Path,
        prices: dict[str, dict[str, float]],
        local_limit_usd: float,
        phase_limits_usd: dict[str, float],
        max_attempts: int,
        phase_call_limits: dict[str, int] | None = None,
    ) -> None:
        self.path = path
        self.prices = prices
        self.local_limit_usd = float(local_limit_usd)
        self.phase_limits_usd = {k: float(v) for k, v in phase_limits_usd.items()}
        self.max_attempts = int(max_attempts)
        self.phase_call_limits = {
            key: int(value) for key, value in (phase_call_limits or {}).items()
        }
        self._lock = Lock()
        self.reservation_path = path.with_name(
            f"{path.stem}_reservations{path.suffix}"
        )
        self.process_lock_path = path.with_suffix(path.suffix + ".lock")
        self._local_reservation_ids: dict[str, list[str]] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def totals(self, phase: str | None = None) -> tuple[int, float]:
        rows = self.records()
        if phase is not None:
            rows = [row for row in rows if row["phase"] == phase]
        return len(rows), sum(float(row["cost_usd"]) for row in rows)

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
    ) -> float:
        price = self.prices[model]
        uncached = max(0, input_tokens - cached_input_tokens)
        return (
            uncached * price["input"]
            + cached_input_tokens * price.get("cached_input", price["input"])
            + output_tokens * price["output"]
        ) / 1_000_000

    def _active_reservations(self) -> dict[str, dict[str, Any]]:
        if not self.reservation_path.exists():
            return {}
        active: dict[str, dict[str, Any]] = {}
        with self.reservation_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                event = json.loads(line)
                reservation_id = str(event["reservation_id"])
                if event["event"] == "reserved":
                    active[reservation_id] = event
                elif event["event"] == "settled":
                    active.pop(reservation_id, None)
                else:
                    raise RuntimeError("Unknown budget reservation event")
        return active

    def _append_reservation_event(self, event: dict[str, Any]) -> None:
        with self.reservation_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")

    def authorize(self, phase: str, worst_case_cost_usd: float) -> str:
        with self._lock:
            with interprocess_lock(self.process_lock_path):
                attempts, total = self.totals()
                phase_attempts, phase_total = self.totals(phase)
                active = self._active_reservations()
                reserved_attempts = len(active)
                reserved_total = sum(
                    float(event["worst_case_cost_usd"])
                    for event in active.values()
                )
                phase_reservations = [
                    event for event in active.values() if event["phase"] == phase
                ]
                if attempts + reserved_attempts >= self.max_attempts:
                    raise BudgetExceeded("Global request-attempt ceiling reached")
                if (
                    phase in self.phase_call_limits
                    and phase_attempts + len(phase_reservations)
                    >= self.phase_call_limits[phase]
                ):
                    raise BudgetExceeded(
                        f"Phase {phase!r} request-attempt ceiling reached"
                    )
                if total + reserved_total + worst_case_cost_usd > self.local_limit_usd:
                    raise BudgetExceeded("Local USD ceiling would be exceeded")
                phase_limit = self.phase_limits_usd[phase]
                phase_reserved_total = sum(
                    float(event["worst_case_cost_usd"])
                    for event in phase_reservations
                )
                if phase_total + phase_reserved_total + worst_case_cost_usd > phase_limit:
                    raise BudgetExceeded(f"Phase {phase!r} USD ceiling would be exceeded")
                reservation_id = uuid4().hex
                self._append_reservation_event(
                    {
                        "event": "reserved",
                        "reservation_id": reservation_id,
                        "timestamp_utc": datetime.now(UTC).isoformat(),
                        "phase": phase,
                        "worst_case_cost_usd": float(worst_case_cost_usd),
                    }
                )
                self._local_reservation_ids.setdefault(phase, []).append(
                    reservation_id
                )
                return reservation_id

    def append(
        self,
        phase: str,
        model: str,
        status: str,
        input_tokens: int,
        output_tokens: int,
        cached_input_tokens: int = 0,
        request_id: str | None = None,
        reservation_id: str | None = None,
    ) -> UsageRecord:
        cost = self.estimate_cost(
            model, input_tokens, output_tokens, cached_input_tokens
        )
        record = UsageRecord(
            timestamp_utc=datetime.now(UTC).isoformat(),
            phase=phase,
            model=model,
            status=status,
            input_tokens=int(input_tokens),
            cached_input_tokens=int(cached_input_tokens),
            output_tokens=int(output_tokens),
            cost_usd=round(cost, 10),
            request_id=request_id,
        )
        with self._lock:
            with interprocess_lock(self.process_lock_path):
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
                local_ids = self._local_reservation_ids.get(phase, [])
                if reservation_id is None and local_ids:
                    reservation_id = local_ids.pop()
                elif reservation_id in local_ids:
                    local_ids.remove(reservation_id)
                if reservation_id is not None:
                    self._append_reservation_event(
                        {
                            "event": "settled",
                            "reservation_id": reservation_id,
                            "timestamp_utc": datetime.now(UTC).isoformat(),
                            "phase": phase,
                        }
                    )
        return record
