from types import SimpleNamespace

import pytest

from ojcoms_poc.metrics import parse_safety_statistics, parse_ssm, parse_tripinfo
from ojcoms_poc.signals import SafeSignalExecutor, SignalPlan, create_yellow_state


class TrafficLightStub:
    def __init__(self):
        self.state = "GGrr"
        self.history = []

    def getRedYellowGreenState(self, tls_id):
        return self.state

    def setRedYellowGreenState(self, tls_id, state):
        self.state = state
        self.history.append((tls_id, state))


def test_yellow_and_all_red_are_inserted_before_target_green():
    assert create_yellow_state("GGrr", "rrGG") == "yyrr"
    lights = TrafficLightStub()
    traci = SimpleNamespace(trafficlight=lights)
    plan = SignalPlan("A", ["GGrr", "rrGG"], [], [set(), set()], [set(), set()])
    executor = SafeSignalExecutor(traci, plan, 2, 1, 3, 50)
    executor.initialize()
    for _ in range(3):
        executor.step()
    assert executor.request(1, 10)
    assert lights.state == "yyrr"
    executor.step()
    executor.step()
    assert lights.state == "rrrr"
    executor.step()
    assert lights.state == "rrGG"


def test_executor_rejects_invalid_phase_and_holds_minimum_green():
    lights = TrafficLightStub()
    executor = SafeSignalExecutor(
        SimpleNamespace(trafficlight=lights),
        SignalPlan("A", ["GGrr", "rrGG"], [], [set(), set()], [set(), set()]),
        yellow_s=2,
        all_red_s=1,
        min_green_s=5,
        max_green_s=50,
    )
    executor.initialize()
    with pytest.raises(ValueError, match="Invalid green phase"):
        executor.request(2, 0)
    for _ in range(4):
        executor.step()
    assert not executor.request(1, 4)
    executor.step()
    assert executor.request(1, 5)


def test_metric_parsers(tmp_path):
    tripinfo = tmp_path / "tripinfo.xml"
    tripinfo.write_text(
        '<tripinfos><tripinfo id="normal" depart="0" arrival="10" duration="10" '
        'routeLength="100" waitingTime="2" timeLoss="3" departDelay="0"/>'
        '<tripinfo id="emergency" depart="1" arrival="9" duration="8" '
        'routeLength="100" waitingTime="1" timeLoss="2" departDelay="0"/></tripinfos>',
        encoding="utf-8",
    )
    metrics, trips = parse_tripinfo(tripinfo, "emergency")
    assert len(trips) == 2
    assert metrics["completed_trips"] == 2
    assert metrics["mean_time_loss_s"] == pytest.approx(2.5)
    assert metrics["emergency_trip_time_s"] == 8

    statistics = tmp_path / "statistics.xml"
    statistics.write_text(
        '<statistics><safety collisions="1" emergencyStops="2" emergencyBraking="3"/>'
        '<teleports total="4" jam="1" yield="1" wrongLane="2"/>'
        '<vehicles loaded="12" inserted="11" running="2" waiting="1"/></statistics>',
        encoding="utf-8",
    )
    assert parse_safety_statistics(statistics) == {
        "collisions": 1,
        "emergency_stops": 2,
        "emergency_braking": 3,
        "teleports": 4,
        "teleports_jam": 1,
        "teleports_yield": 1,
        "teleports_wrong_lane": 2,
        "loaded_vehicles": 12,
        "inserted_vehicles": 11,
        "running_vehicles_at_end": 2,
        "waiting_vehicles_at_end": 1,
    }

    ssm = tmp_path / "ssm.xml"
    ssm.write_text(
        '<ssm_log><conflict><minTTC value="1.5"/><PET value="2.5"/>'
        '<maxDRAC value="3.5"/></conflict></ssm_log>',
        encoding="utf-8",
    )
    assert parse_ssm(ssm) == {
        "ssm_conflicts": 1,
        "ssm_unavailable_values": 0,
        "min_ttc_s": 1.5,
        "min_pet_s": 2.5,
        "max_drac_mps2": 3.5,
    }
