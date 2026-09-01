from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import numpy as np


@dataclass(frozen=True)
class SignalObservation:
    tls_id: str
    phase_lanes: list[set[str]]
    phase_out_lanes: list[set[str]]
    lane_queues: dict[str, float]
    lane_occupancies: dict[str, float]
    max_lane_waits: dict[str, float]
    current_green: int
    phase_elapsed_s: int
    emergency_phase: int | None
    sensor_complete: bool = True


class Controller(Protocol):
    def act(self, observation: SignalObservation) -> int: ...


class LocalMaxWaveController:
    """Local queue-only strong deterministic baseline."""

    def act(self, observation: SignalObservation) -> int:
        scores = [
            sum(observation.lane_queues.get(lane, 0.0) for lane in lanes)
            for lanes in observation.phase_lanes
        ]
        best = int(np.argmax(scores))
        if scores[observation.current_green] >= scores[best]:
            return observation.current_green
        return best


class CoordinatedMaxPressureController:
    """Pressure controller using inbound and downstream queue summaries."""

    def __init__(self, minimum_hold_s: int = 10, switch_margin: float = 2.0) -> None:
        self.minimum_hold_s = int(minimum_hold_s)
        self.switch_margin = float(switch_margin)

    def act(self, observation: SignalObservation) -> int:
        scores: list[float] = []
        for incoming, outgoing in zip(
            observation.phase_lanes, observation.phase_out_lanes, strict=True
        ):
            upstream = sum(observation.lane_queues.get(lane, 0.0) for lane in incoming)
            downstream = sum(
                observation.lane_queues.get(lane, 0.0) for lane in outgoing
            )
            scores.append(upstream - downstream)
        best = int(np.argmax(scores))
        current = observation.current_green
        if observation.phase_elapsed_s < self.minimum_hold_s:
            return current
        if scores[best] - scores[current] <= self.switch_margin:
            return current
        return best


def fairness_override(observation: SignalObservation, max_wait_s: float) -> int | None:
    if not observation.max_lane_waits:
        return None
    lane, wait = max(observation.max_lane_waits.items(), key=lambda item: item[1])
    if wait < max_wait_s:
        return None
    candidates = [
        index for index, lanes in enumerate(observation.phase_lanes) if lane in lanes
    ]
    return candidates[0] if candidates else None


def forced_alternative(observation: SignalObservation) -> int:
    scores = [
        sum(observation.lane_queues.get(lane, 0.0) for lane in lanes)
        if index != observation.current_green
        else float("-inf")
        for index, lanes in enumerate(observation.phase_lanes)
    ]
    return int(np.argmax(scores))
