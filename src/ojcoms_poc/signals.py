from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def create_yellow_state(current: str, target: str) -> str:
    colors: list[str] = []
    for now, next_color in zip(current, target, strict=True):
        if now in {"G", "g"} and next_color in {"r", "s"}:
            colors.append("y")
        else:
            colors.append(now)
    return "".join(colors)


@dataclass
class SignalPlan:
    tls_id: str
    green_states: list[str]
    controlled_links: list[list[tuple[str, str, str]]]
    phase_lanes: list[set[str]]
    phase_out_lanes: list[set[str]]

    @classmethod
    def from_traci(cls, traci: Any, tls_id: str) -> "SignalPlan":
        logic = traci.trafficlight.getAllProgramLogics(tls_id)[0]
        green_states = [
            phase.state
            for phase in logic.phases
            if "y" not in phase.state
            and phase.state.count("r") + phase.state.count("s") != len(phase.state)
        ]
        controlled_links = traci.trafficlight.getControlledLinks(tls_id)
        phase_lanes: list[set[str]] = []
        phase_out_lanes: list[set[str]] = []
        for state in green_states:
            incoming: set[str] = set()
            outgoing: set[str] = set()
            for index, color in enumerate(state):
                if color not in {"G", "g"} or index >= len(controlled_links):
                    continue
                for connection in controlled_links[index]:
                    if not connection:
                        continue
                    incoming.add(connection[0])
                    outgoing.add(connection[1])
            phase_lanes.append(incoming)
            phase_out_lanes.append(outgoing)
        return cls(
            tls_id=tls_id,
            green_states=green_states,
            controlled_links=controlled_links,
            phase_lanes=phase_lanes,
            phase_out_lanes=phase_out_lanes,
        )


@dataclass
class SafeSignalExecutor:
    traci: Any
    plan: SignalPlan
    yellow_s: int
    all_red_s: int
    min_green_s: int
    max_green_s: int
    current_green: int = 0
    phase_elapsed_s: int = 0
    pending_green: int | None = None
    stage: str = "green"
    stage_remaining_s: int = 0
    action_count: int = 0
    transition_log: list[dict[str, Any]] = field(default_factory=list)

    def initialize(self) -> None:
        current_state = self.traci.trafficlight.getRedYellowGreenState(self.plan.tls_id)
        if current_state in self.plan.green_states:
            self.current_green = self.plan.green_states.index(current_state)
        else:
            self.current_green = 0
            self.traci.trafficlight.setRedYellowGreenState(
                self.plan.tls_id, self.plan.green_states[0]
            )
        self.stage = "green"
        self.phase_elapsed_s = 0

    @property
    def transitioning(self) -> bool:
        return self.stage != "green"

    def request(self, target_green: int, sim_time_s: int) -> bool:
        if target_green < 0 or target_green >= len(self.plan.green_states):
            raise ValueError(f"Invalid green phase {target_green} for {self.plan.tls_id}")
        if self.transitioning or target_green == self.current_green:
            return False
        if self.phase_elapsed_s < self.min_green_s:
            return False

        yellow = create_yellow_state(
            self.plan.green_states[self.current_green],
            self.plan.green_states[target_green],
        )
        self.pending_green = target_green
        self.stage = "yellow"
        self.stage_remaining_s = self.yellow_s
        self.traci.trafficlight.setRedYellowGreenState(self.plan.tls_id, yellow)
        self.action_count += 1
        self.transition_log.append(
            {
                "sim_time_s": sim_time_s,
                "tls_id": self.plan.tls_id,
                "from_green": self.current_green,
                "to_green": target_green,
                "yellow_state": yellow,
            }
        )
        return True

    def step(self) -> None:
        if self.stage == "green":
            self.phase_elapsed_s += 1
            return

        self.stage_remaining_s -= 1
        if self.stage_remaining_s > 0:
            return
        if self.stage == "yellow" and self.all_red_s > 0:
            self.stage = "all_red"
            self.stage_remaining_s = self.all_red_s
            all_red = "r" * len(self.plan.green_states[self.current_green])
            self.traci.trafficlight.setRedYellowGreenState(self.plan.tls_id, all_red)
            return

        if self.pending_green is None:
            raise RuntimeError("Transition completed without a pending phase")
        self.current_green = self.pending_green
        self.pending_green = None
        self.stage = "green"
        self.phase_elapsed_s = 0
        self.traci.trafficlight.setRedYellowGreenState(
            self.plan.tls_id, self.plan.green_states[self.current_green]
        )

