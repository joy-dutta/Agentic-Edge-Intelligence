import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

from ojcoms_poc.budget import BudgetExceeded, BudgetLedger


PRICES = {"test-model": {"input": 1.0, "cached_input": 0.1, "output": 2.0}}


def _concurrent_budget_worker(path_value: str) -> int:
    ledger = BudgetLedger(
        Path(path_value),
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"primary": 1},
        max_attempts=20,
        phase_call_limits={"primary": 20},
    )
    completed = 0
    for _ in range(8):
        try:
            reservation_id = ledger.authorize("primary", 0)
        except BudgetExceeded:
            break
        time.sleep(0.005)
        ledger.append(
            "primary",
            "test-model",
            "ok",
            0,
            0,
            reservation_id=reservation_id,
        )
        completed += 1
    return completed


def test_budget_ledger_cost_and_hard_limit(tmp_path):
    ledger = BudgetLedger(
        tmp_path / "usage.jsonl",
        PRICES,
        local_limit_usd=0.004,
        phase_limits_usd={"pilot": 0.003},
        max_attempts=2,
    )
    assert ledger.estimate_cost("test-model", 1_000, 1_000, 500) == pytest.approx(
        0.00255
    )
    ledger.authorize("pilot", 0.00255)
    record = ledger.append("pilot", "test-model", "ok", 1_000, 1_000, 500)
    assert record.cost_usd == pytest.approx(0.00255)
    assert "api_key" not in json.dumps(ledger.records()).lower()
    with pytest.raises(BudgetExceeded, match="Phase"):
        ledger.authorize("pilot", 0.001)


def test_attempt_ceiling_is_enforced(tmp_path):
    ledger = BudgetLedger(
        tmp_path / "usage.jsonl",
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"pilot": 1},
        max_attempts=1,
    )
    ledger.append("pilot", "test-model", "failed", 0, 0)
    with pytest.raises(BudgetExceeded, match="attempt"):
        ledger.authorize("pilot", 0)


def test_phase_attempt_ceiling_is_enforced(tmp_path):
    ledger = BudgetLedger(
        tmp_path / "usage.jsonl",
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"pilot": 1},
        max_attempts=10,
        phase_call_limits={"pilot": 1},
    )
    ledger.append("pilot", "test-model", "ok", 0, 0)
    with pytest.raises(BudgetExceeded, match="Phase"):
        ledger.authorize("pilot", 0)


def test_in_flight_reservations_are_counted_and_released(tmp_path):
    ledger = BudgetLedger(
        tmp_path / "usage.jsonl",
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"pilot": 0.006},
        max_attempts=10,
        phase_call_limits={"pilot": 3},
    )
    ledger.authorize("pilot", 0.003)
    ledger.authorize("pilot", 0.003)
    with pytest.raises(BudgetExceeded, match="Phase"):
        ledger.authorize("pilot", 0.001)

    ledger.append("pilot", "test-model", "ok", 0, 0)
    ledger.authorize("pilot", 0.001)


def test_crash_or_restart_preserves_worst_case_reservation(tmp_path):
    path = tmp_path / "usage.jsonl"
    first = BudgetLedger(
        path,
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"pilot": 0.004},
        max_attempts=2,
    )
    reservation_id = first.authorize("pilot", 0.003)

    restarted = BudgetLedger(
        path,
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"pilot": 0.004},
        max_attempts=2,
    )
    with pytest.raises(BudgetExceeded, match="Phase"):
        restarted.authorize("pilot", 0.002)

    first.append(
        "pilot",
        "test-model",
        "ok",
        0,
        0,
        reservation_id=reservation_id,
    )
    restarted.authorize("pilot", 0.002)


def test_processes_cannot_race_past_attempt_limit(tmp_path):
    path = tmp_path / "usage.jsonl"
    with ProcessPoolExecutor(max_workers=4) as executor:
        counts = list(executor.map(_concurrent_budget_worker, [str(path)] * 4))
    ledger = BudgetLedger(
        path,
        PRICES,
        local_limit_usd=1,
        phase_limits_usd={"primary": 1},
        max_attempts=20,
        phase_call_limits={"primary": 20},
    )
    assert sum(counts) == 20
    assert len(ledger.records()) == 20
    assert ledger._active_reservations() == {}
