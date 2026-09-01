from __future__ import annotations

from .controllers import (
    CoordinatedMaxPressureController,
    LocalMaxWaveController,
    SignalObservation,
)
from .models import AgentIntent, IntentName, IntersectionState, PeerSummary


def policy_state(
    observation: SignalObservation,
    peers: list[PeerSummary],
    sim_time_s: int,
    spillback_occupancy: float,
) -> IntersectionState:
    phase_queues = [
        int(sum(observation.lane_queues.get(lane, 0) for lane in lanes))
        for lanes in observation.phase_lanes
    ]
    phase_occupancies = [
        max(
            (observation.lane_occupancies.get(lane, 0.0) for lane in lanes),
            default=0.0,
        )
        for lanes in observation.phase_lanes
    ]
    downstream_blocked = any(
        observation.lane_occupancies.get(lane, 0.0) >= spillback_occupancy
        for lanes in observation.phase_out_lanes
        for lane in lanes
    )
    return IntersectionState(
        intersection_id=observation.tls_id,
        sim_time_s=sim_time_s,
        current_phase=observation.current_green,
        phase_elapsed_s=observation.phase_elapsed_s,
        lane_queues=phase_queues,
        lane_occupancies=phase_occupancies,
        max_wait_s=max(observation.max_lane_waits.values(), default=0.0),
        downstream_blocked=downstream_blocked,
        verified_emergency=observation.emergency_phase is not None,
        emergency_phase=observation.emergency_phase,
        sensor_complete=observation.sensor_complete,
        peers=peers,
    )


def supervised_target(
    intent: AgentIntent,
    observation: SignalObservation,
    local: LocalMaxWaveController,
    coordinated: CoordinatedMaxPressureController,
) -> int:
    fallback = local.act(observation)
    if intent.strength == 0 or intent.intent in {
        IntentName.KEEP_LOCAL_PLAN,
        IntentName.REQUEST_FALLBACK,
    }:
        return fallback
    if intent.intent in {IntentName.BIAS_CORRIDOR, IntentName.COORDINATE_OFFSET}:
        return coordinated.act(observation)
    if intent.intent == IntentName.EMERGENCY_PRIORITY:
        return (
            observation.emergency_phase
            if observation.emergency_phase is not None
            else coordinated.act(observation)
        )
    if intent.intent == IntentName.BIAS_CROSS_STREET:
        phase_scores = [
            sum(observation.lane_queues.get(lane, 0.0) for lane in lanes)
            for lanes in observation.phase_lanes
        ]
        corridor = coordinated.act(observation)
        phase_scores[corridor] = float("-inf")
        return max(range(len(phase_scores)), key=phase_scores.__getitem__)
    return fallback


def compact_payload_state(state: IntersectionState) -> dict:
    return {
        "intersection_id": state.intersection_id,
        "sim_time_s": state.sim_time_s,
        "current_phase": state.current_phase,
        "phase_elapsed_s": state.phase_elapsed_s,
        "phase_queues": state.lane_queues,
        "phase_occupancies": [round(value, 3) for value in state.lane_occupancies],
        "max_wait_s": round(state.max_wait_s, 1),
        "downstream_blocked": state.downstream_blocked,
        "verified_emergency": state.verified_emergency,
        "emergency_phase": state.emergency_phase,
        "sensor_complete": state.sensor_complete,
        "peers": [peer.model_dump(mode="json") for peer in state.peers],
    }
