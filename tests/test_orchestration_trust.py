import json

import pytest

from ojcoms_poc.config import ExperimentConfig, load_config
from ojcoms_poc.controllers import SignalObservation
from ojcoms_poc.controllers import CoordinatedMaxPressureController, LocalMaxWaveController
from ojcoms_poc.network import NetworkEmulator, NetworkProfile
from ojcoms_poc.orchestration import RunSpec, planned_calls, run_matrix, verify_live_gate
from ojcoms_poc.runner import SumoExperimentRunner


def test_ssm_probability_is_range_checked_before_run(monkeypatch):
    monkeypatch.setattr("ojcoms_poc.runner.load_neighbors", lambda *_args: {})
    runner = SumoExperimentRunner(load_config())
    with pytest.raises(ValueError, match="ssm_probability"):
        runner.run("fixed", "S2", 1101, ssm_probability=1.01)


def test_primary_live_plan_leaves_room_for_registered_audits():
    config = load_config()
    simulation = config.section("simulation")
    primary = simulation["test_seeds_primary"]
    sensitivity = simulation["test_seeds_sensitivity"]
    mapping = {
        "S0": primary,
        "S1": sensitivity,
        "S2": primary,
        "S3": primary,
        "S4": sensitivity,
    }
    specs = [
        RunSpec(controller, scenario, seed)
        for controller in ("agentic_unguarded", "agentic_governed")
        for scenario, seeds in mapping.items()
        for seed in seeds
    ]
    specs.extend(
        RunSpec("agentic_governed_no_peer", scenario, seed)
        for scenario in ("S0", "S2")
        for seed in primary
    )
    registered_audits_and_nano_validation = 250 + 200 + 186
    assert sum(map(planned_calls, specs)) + registered_audits_and_nano_validation <= 7000


def observation(tls_id):
    return SignalObservation(
        tls_id=tls_id,
        phase_lanes=[{"in"}],
        phase_out_lanes=[{"out"}],
        lane_queues={"in": 2.0},
        lane_occupancies={"in": 0.1},
        max_lane_waits={"in": 3.0},
        current_green=0,
        phase_elapsed_s=10,
        emergency_phase=None,
    )


def test_controllers_hold_on_ties_and_pressure_chatter():
    tied = observation("A")
    tied = SignalObservation(
        **{
            **tied.__dict__,
            "phase_lanes": [{"a"}, {"b"}],
            "phase_out_lanes": [{"ao"}, {"bo"}],
            "lane_queues": {"a": 2, "b": 2, "ao": 0, "bo": 0},
            "current_green": 1,
        }
    )
    assert LocalMaxWaveController().act(tied) == 1
    assert CoordinatedMaxPressureController().act(tied) == 1

    small_gain = SignalObservation(
        **{
            **tied.__dict__,
            "lane_queues": {"a": 3, "b": 2, "ao": 0, "bo": 0},
            "current_green": 1,
        }
    )
    assert CoordinatedMaxPressureController().act(small_gain) == 1


def test_s3_and_s4_stale_peer_semantics(monkeypatch):
    monkeypatch.setattr("ojcoms_poc.runner.load_neighbors", lambda *_args: {})
    runner = SumoExperimentRunner(load_config())
    runner.neighbors = {"32319828": {"252017285"}}
    observations = {
        "32319828": observation("32319828"),
        "252017285": observation("252017285"),
    }
    emulator = NetworkEmulator(NetworkProfile("N0", 0, 0, 0, 1000), 1)
    stale_start = int(runner.events["stale_peer_start_rel_s"])

    s3 = runner._peer_summaries(
        "32319828",
        observations,
        scenario_name="S3",
        rel_time_s=stale_start,
        sim_time_s=100,
        emulator=emulator,
        enabled=True,
    )[0]
    s4 = runner._peer_summaries(
        "32319828",
        observations,
        scenario_name="S4",
        rel_time_s=stale_start,
        sim_time_s=100,
        emulator=emulator,
        enabled=True,
    )[0]

    assert s3.authenticated and not s3.replayed and s3.age_s == 15
    assert not s4.authenticated and s4.replayed and s4.age_s == 15
    assert s4.emergency_claim and s4.untrusted_text_present


def test_run_matrix_preserves_incomplete_attempt(tmp_path, monkeypatch):
    config = ExperimentConfig(root=tmp_path, raw={"paths": {"artifacts": "artifacts"}})
    spec = RunSpec("fixed_time", "S2", 1102)
    run_dir = tmp_path / "artifacts" / "raw" / "pilot" / spec.run_id
    run_dir.mkdir(parents=True)
    (run_dir / "partial.jsonl").write_text("partial\n", encoding="utf-8")

    class FakeRunner:
        def __init__(self, _config):
            pass

        def run(self, *_args, **_kwargs):
            run_dir.mkdir(parents=True)
            summary = {"status": "completed"}
            (run_dir / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
            return summary

    monkeypatch.setattr("ojcoms_poc.orchestration.SumoExperimentRunner", FakeRunner)
    assert run_matrix(config, [spec], phase="pilot", shuffle_seed=1) == [
        {"status": "completed"}
    ]
    preserved = list(run_dir.parent.glob(f"{spec.run_id}_incomplete_*"))
    assert len(preserved) == 1
    assert (preserved[0] / "partial.jsonl").read_text(encoding="utf-8") == "partial\n"


def test_corrected_pilot_artifact_phase_uses_pilot_budget(tmp_path, monkeypatch):
    config = ExperimentConfig(
        root=tmp_path,
        raw={
            "paths": {"artifacts": "artifacts"},
            "budget": {"phase_limits_usd": {"pilot": 1.0}},
        },
    )
    checked_phases = []

    class FakeRunner:
        def __init__(self, _config):
            pass

        def run(self, *_args, **kwargs):
            assert kwargs["phase"] == "pilot_corrected_v4"
            return {"status": "completed"}

    monkeypatch.setattr("ojcoms_poc.orchestration.SumoExperimentRunner", FakeRunner)
    monkeypatch.setattr(
        "ojcoms_poc.orchestration.verify_live_gate",
        lambda _config, phase: checked_phases.append(phase),
    )
    result = run_matrix(
        config,
        [RunSpec("agentic_governed", "S2", 1101)],
        phase="pilot_corrected_v4",
        shuffle_seed=1,
    )
    assert result == [{"status": "completed"}]
    assert checked_phases == ["pilot"]


def test_unknown_live_artifact_phase_is_rejected(tmp_path):
    config = ExperimentConfig(
        root=tmp_path,
        raw={
            "paths": {"artifacts": "artifacts"},
            "budget": {"phase_limits_usd": {"pilot": 1.0}},
        },
    )
    with pytest.raises(RuntimeError, match="No budget allowance"):
        run_matrix(
            config,
            [RunSpec("agentic_governed", "S2", 1101)],
            phase="typo",
            shuffle_seed=1,
        )


def test_worker_count_must_be_positive(tmp_path):
    config = ExperimentConfig(root=tmp_path, raw={})
    with pytest.raises(ValueError, match="workers"):
        run_matrix(config, [], phase="pilot", shuffle_seed=1, workers=0)


def test_live_gate_requires_approved_phase_manifest(tmp_path, monkeypatch):
    config = ExperimentConfig(
        root=tmp_path,
        raw={
            "budget": {
                "platform_limit_usd": 20,
                "phase_limits_usd": {"primary": 10},
                "phase_call_limits": {"primary": 7000},
            }
        },
    )
    configs = tmp_path / "configs"
    configs.mkdir()
    (configs / "platform_budget_gate.json").write_text(
        json.dumps({"hard_limit_verified": True, "platform_hard_limit_usd": 20}),
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "only-present-for-gate-test")
    with pytest.raises(RuntimeError, match="budget_manifest_primary.json is absent"):
        verify_live_gate(config, "primary")

    manifest = {
        "phase": "primary",
        "planned_request_ceiling": 6896,
        "worst_case_cost_usd": 9.9,
        "proceed": True,
    }
    (configs / "budget_manifest_primary.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    assert verify_live_gate(config, "primary")["hard_limit_verified"] is True


def test_soft_platform_gate_requires_matching_local_hard_cap(tmp_path, monkeypatch):
    config = ExperimentConfig(
        root=tmp_path,
        raw={
            "budget": {
                "platform_limit_usd": 20,
                "local_limit_usd": 16,
                "phase_limits_usd": {"pilot": 1},
                "phase_call_limits": {"pilot": 300},
            }
        },
    )
    configs = tmp_path / "configs"
    configs.mkdir()
    gate = {
        "hard_limit_verified": False,
        "platform_limit_type": "soft",
        "platform_soft_limit_usd": 20,
        "user_acknowledged_soft_limit": True,
        "local_hard_cap_authorized": True,
        "local_hard_limit_usd": 15,
        "protocol_deviation_documented": True,
    }
    (configs / "platform_budget_gate.json").write_text(json.dumps(gate), encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "only-present-for-gate-test")
    with pytest.raises(RuntimeError, match="local hard limit"):
        verify_live_gate(config, "pilot")

    gate["local_hard_limit_usd"] = 16
    (configs / "platform_budget_gate.json").write_text(json.dumps(gate), encoding="utf-8")
    (configs / "budget_manifest_pilot.json").write_text(
        json.dumps(
            {
                "phase": "pilot",
                "planned_request_ceiling": 240,
                "worst_case_cost_usd": 0.51,
                "proceed": True,
            }
        ),
        encoding="utf-8",
    )
    assert verify_live_gate(config, "pilot")["platform_limit_type"] == "soft"
