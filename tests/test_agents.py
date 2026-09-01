import json
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from ojcoms_poc.agents import (
    InvalidSupervisorResponseError,
    OpenAISupervisor,
    ReplaySupervisor,
)
from ojcoms_poc.budget import BudgetLedger


MODEL = "test-model"


def response_json(ids):
    return json.dumps(
        {
            "intents": [
                {
                    "intersection_id": intersection_id,
                    "valid_for_s": 60,
                    "intent": "keep_local_plan",
                    "strength": 0,
                    "requested_duration_s": 0,
                    "neighbor_request": "none",
                    "reason_code": "balanced",
                    "confidence": 0.8,
                }
                for intersection_id in ids
            ]
        }
    )


class FakeResponses:
    def __init__(self, ids, returned_model=MODEL):
        self.ids = ids
        self.returned_model = returned_model
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            id="resp_test",
            model=self.returned_model,
            output_text=response_json(self.ids),
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=50,
                input_tokens_details=SimpleNamespace(cached_tokens=20),
            ),
        )


def make_supervisor(
    tmp_path, ids, returned_model=MODEL, max_estimated_input_tokens=5_000
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Use only supplied structured state.", encoding="utf-8")
    ledger = BudgetLedger(
        tmp_path / "usage.jsonl",
        {MODEL: {"input": 0.2, "cached_input": 0.02, "output": 1.25}},
        local_limit_usd=1,
        phase_limits_usd={"pilot": 1},
        max_attempts=10,
        phase_call_limits={"pilot": 10},
    )
    responses = FakeResponses(ids, returned_model)
    client = SimpleNamespace(responses=responses)
    supervisor = OpenAISupervisor(
        model=MODEL,
        prompt_path=prompt,
        ledger=ledger,
        phase="pilot",
        max_output_tokens=500,
        max_estimated_input_tokens=max_estimated_input_tokens,
        reasoning_effort="low",
        store=False,
        max_retries=0,
        audit_path=tmp_path / "calls.jsonl",
        client=client,
    )
    return supervisor, ledger, responses


def payload(ids):
    return {
        "protocol_version": "1.0",
        "agents": [{"intersection_id": value} for value in ids],
    }


def test_structured_call_is_stateless_and_usage_is_recorded(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    supervisor, ledger, responses = make_supervisor(tmp_path, ids)
    result = supervisor.decide(
        payload(ids), observation_sim_time_s=100, request_kind="scheduled"
    )
    assert result.response_id == "resp_test"
    assert result.cached_input_tokens == 20
    assert responses.kwargs["store"] is False
    assert responses.kwargs["text"]["format"]["strict"] is True
    assert ledger.totals("pilot")[0] == 1
    audit = (tmp_path / "calls.jsonl").read_text()
    assert "OPENAI_API_KEY" not in audit
    assert json.loads(audit)["payload"] == payload(ids)


def test_identity_reordering_fails_closed(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    supervisor, ledger, _ = make_supervisor(tmp_path, list(reversed(ids)))
    with pytest.raises(InvalidSupervisorResponseError, match="identities"):
        supervisor.decide(
            payload(ids), observation_sim_time_s=100, request_kind="scheduled"
        )
    assert ledger.records()[0]["status"] == "InvalidSupervisorResponseError"


def test_incomplete_response_exposes_billed_fallback_accounting(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    supervisor, ledger, responses = make_supervisor(tmp_path, ids)
    original_create = responses.create

    def incomplete_create(**kwargs):
        response = original_create(**kwargs)
        response.status = "incomplete"
        response.output_text = response.output_text[:100]
        response.usage.output_tokens = 500
        return response

    responses.create = incomplete_create
    with pytest.raises(InvalidSupervisorResponseError) as caught:
        supervisor.decide(
            payload(ids), observation_sim_time_s=100, request_kind="scheduled"
        )
    assert caught.value.output_tokens == 500
    assert caught.value.request_application_bytes > 0
    assert caught.value.response_application_bytes == 100
    assert ledger.records()[0]["status"] == "InvalidSupervisorResponseError"


def test_returned_model_mismatch_fails_closed(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    supervisor, ledger, _ = make_supervisor(tmp_path, ids, "different-model")
    with pytest.raises(ValueError, match="pinned model"):
        supervisor.decide(
            payload(ids), observation_sim_time_s=100, request_kind="scheduled"
        )
    record = ledger.records()[0]
    assert record["status"] == "ValueError"
    assert record["input_tokens"] == 100
    assert record["output_tokens"] == 50
    assert record["cost_usd"] > 0


def test_oversized_input_is_rejected_before_api_or_ledger(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    supervisor, ledger, responses = make_supervisor(
        tmp_path, ids, max_estimated_input_tokens=10
    )
    with pytest.raises(ValueError, match="Estimated input token count"):
        supervisor.decide(
            payload(ids), observation_sim_time_s=100, request_kind="scheduled"
        )
    assert responses.kwargs is None
    assert ledger.records() == []


def test_replay_requires_exact_payload_and_consumes_all_calls(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    request_payload = payload(ids)
    canonical = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    row = {
        "observation_sim_time_s": 100,
        "request_kind": "scheduled",
        "model": MODEL,
        "response_id": "resp_recorded",
        "latency_s": 0.25,
        "attempts": 1,
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "output_tokens": 50,
        "request_application_bytes": 1234,
        "response_application_bytes": 567,
        "schema_valid": True,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "intents": json.loads(response_json(ids)),
    }
    source = tmp_path / "api_calls.jsonl"
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")
    replay = ReplaySupervisor(
        source, tmp_path / "replay_calls.jsonl", expected_model=MODEL
    )

    result = replay.decide(
        request_payload, observation_sim_time_s=100, request_kind="scheduled"
    )
    replay.assert_consumed()

    assert result.response_id == "resp_recorded"
    audit = json.loads((tmp_path / "replay_calls.jsonl").read_text())
    assert audit["source_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()


def test_replay_rejects_payload_or_model_mismatch(tmp_path):
    ids = [f"C{index}" for index in range(8)]
    request_payload = payload(ids)
    canonical = json.dumps(request_payload, sort_keys=True, separators=(",", ":"))
    row = {
        "observation_sim_time_s": 100,
        "request_kind": "scheduled",
        "model": MODEL,
        "response_id": "resp_recorded",
        "latency_s": 0.25,
        "attempts": 1,
        "input_tokens": 100,
        "cached_input_tokens": 20,
        "output_tokens": 50,
        "request_application_bytes": 1234,
        "response_application_bytes": 567,
        "schema_valid": True,
        "payload_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "intents": json.loads(response_json(ids)),
    }
    source = tmp_path / "api_calls.jsonl"
    source.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="models other than"):
        ReplaySupervisor(source, expected_model="different-model")

    replay = ReplaySupervisor(source, expected_model=MODEL)
    with pytest.raises(ValueError, match="does not match recorded"):
        replay.decide(
            payload(list(reversed(ids))),
            observation_sim_time_s=100,
            request_kind="scheduled",
        )


def test_static_redacted_replay_fixture_requires_no_api():
    ids = [f"C{index}" for index in range(8)]
    source = Path(__file__).parent / "fixtures" / "replay_api_calls.jsonl"
    replay = ReplaySupervisor(source, expected_model="fixture-model")
    result = replay.decide(
        payload(ids), observation_sim_time_s=100, request_kind="scheduled"
    )
    replay.assert_consumed()
    assert result.response_id == "resp_redacted_fixture"
    assert result.estimated_input_tokens == 300
