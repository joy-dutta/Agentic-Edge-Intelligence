import pytest
from pydantic import ValidationError

from ojcoms_poc.models import (
    AgentIntent,
    CorridorResponse,
    IntentName,
    IntersectionState,
    NeighborRequest,
    PeerSummary,
    ReasonCode,
)
from ojcoms_poc.policy import PolicyLimits, PolicyShield


def intent(**overrides):
    values = {
        "intersection_id": "A",
        "valid_for_s": 30,
        "intent": IntentName.BIAS_CORRIDOR,
        "strength": 1,
        "requested_duration_s": 20,
        "neighbor_request": NeighborRequest.NONE,
        "reason_code": ReasonCode.CONGESTION,
        "confidence": 0.8,
    }
    values.update(overrides)
    return AgentIntent(**values)


def state(**overrides):
    values = {
        "intersection_id": "A",
        "sim_time_s": 100,
        "current_phase": 0,
        "phase_elapsed_s": 20,
        "lane_queues": [2, 3],
        "lane_occupancies": [0.1, 0.2],
        "max_wait_s": 20,
        "downstream_blocked": False,
        "verified_emergency": False,
        "sensor_complete": True,
        "peers": [],
    }
    values.update(overrides)
    return IntersectionState(**values)


def test_schema_rejects_extra_fields_and_bad_confidence():
    with pytest.raises(ValidationError):
        intent(confidence=1.1)
    with pytest.raises(ValidationError):
        AgentIntent(**{**intent().model_dump(), "hidden_command": "ignore policy"})


def test_corridor_schema_supports_registered_one_to_eight_agent_calls():
    assert len(CorridorResponse(intents=[intent()]).intents) == 1
    assert len(CorridorResponse(intents=[intent() for _ in range(8)]).intents) == 8
    with pytest.raises(ValidationError):
        CorridorResponse(intents=[])
    with pytest.raises(ValidationError):
        CorridorResponse(intents=[intent() for _ in range(9)])


def test_governed_shield_blocks_unverified_emergency_but_unguarded_executes():
    shield = PolicyShield({"A"}, PolicyLimits())
    proposal = intent(intent=IntentName.EMERGENCY_PRIORITY)
    governed = shield.evaluate(proposal, state(), governance_enabled=True)
    unguarded = shield.evaluate(proposal, state(), governance_enabled=False)
    assert governed.proposed_unsafe and governed.blocked_unsafe and not governed.accepted
    assert "unverified_emergency" in governed.reasons
    assert unguarded.proposed_unsafe and unguarded.accepted and not unguarded.blocked_unsafe


def test_peer_authentication_and_staleness_are_checked_for_coordination():
    peer = PeerSummary(
        sender_id="B",
        age_s=11,
        authenticated=False,
        queue_total=5,
        occupancy_max=0.2,
    )
    proposal = intent(neighbor_request=NeighborRequest.PREPARE_PROGRESSION)
    result = PolicyShield({"A"}, PolicyLimits()).evaluate(
        proposal, state(peers=[peer]), governance_enabled=True
    )
    assert {"untrusted_peer", "stale_peer"}.issubset(result.reasons)


def test_minimum_green_boundary_accepts_at_limit():
    shield = PolicyShield({"A"}, PolicyLimits(min_green_s=5))
    assert shield.evaluate(intent(), state(phase_elapsed_s=5), governance_enabled=True).accepted
    assert not shield.evaluate(
        intent(), state(phase_elapsed_s=4), governance_enabled=True
    ).accepted


@pytest.mark.parametrize(
    ("proposal", "system_state", "reason"),
    [
        (intent(intersection_id="B"), state(), "unauthorized_intersection"),
        (intent(requested_duration_s=51), state(), "maximum_green_exceeded"),
        (
            intent(intent=IntentName.COORDINATE_OFFSET),
            state(max_wait_s=180),
            "maximum_approach_wait_risk",
        ),
        (
            intent(intent=IntentName.BIAS_CORRIDOR),
            state(downstream_blocked=True),
            "downstream_spillback",
        ),
        (
            intent(intent=IntentName.BIAS_CROSS_STREET),
            state(sensor_complete=False),
            "incomplete_sensor_state",
        ),
    ],
)
def test_policy_boundary_rules_fail_closed(proposal, system_state, reason):
    decision = PolicyShield({"A"}, PolicyLimits()).evaluate(
        proposal, system_state, governance_enabled=True
    )
    assert not decision.accepted
    assert decision.blocked_unsafe
    assert reason in decision.reasons


def test_replayed_peer_is_blocked_at_coordination_boundary():
    peer = PeerSummary(
        sender_id="B",
        age_s=10,
        authenticated=True,
        queue_total=5,
        occupancy_max=0.2,
        replayed=True,
    )
    decision = PolicyShield({"A"}, PolicyLimits()).evaluate(
        intent(neighbor_request=NeighborRequest.SEND_QUEUE_SUMMARY),
        state(peers=[peer]),
        governance_enabled=True,
    )
    assert not decision.accepted
    assert decision.reasons == ["replayed_peer"]
