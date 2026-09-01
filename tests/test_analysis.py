import pandas as pd
from matplotlib import pyplot as plt

from ojcoms_poc.analysis import (
    _box_strip,
    filter_confirmatory_runs,
    flatten,
    paired_comparisons,
    summarize,
)


def test_flatten_defines_architecture_byte_denominators():
    row = {
        "controller": "agentic_governed",
        "scenario": "S0",
        "seed": 1,
        "api_request_application_bytes": 100,
        "api_response_application_bytes": 20,
        "audit_log_bytes": 50,
        "peer_network": {"application_bytes": 30, "modeled_transport_bytes": 60},
        "cloud_wan": {"application_bytes": 0},
    }
    flat = flatten(row)
    assert flat["wan_application_bytes"] == 120
    assert flat["peer_application_bytes"] == 30
    assert flat["communication_footprint_bytes"] == 200


def test_partial_phase_plot_accepts_ablation_only_controller():
    frame = pd.DataFrame(
        [{"controller": "coordinated_maxpressure", "scenario": "S2", "value": 1.0}]
    )
    figure, axis = plt.subplots()
    _box_strip(axis, frame, "value", "Pilot ablation")
    assert axis.get_title() == "Pilot ablation"
    plt.close(figure)


def test_confirmatory_filter_excludes_validation_seeds():
    frame = pd.DataFrame(
        [
            {"controller": "agentic_governed", "scenario": "S2", "seed": 2101},
            {"controller": "agentic_governed", "scenario": "S2", "seed": 1001},
            {"controller": "agentic_governed", "scenario": "S4", "seed": 3101},
        ]
    )
    filtered = filter_confirmatory_runs(frame, {2101}, {3101})
    assert list(filtered[["scenario", "seed"]].itertuples(index=False, name=None)) == [
        ("S2", 2101),
        ("S4", 3101),
    ]


def test_paired_statistics_use_runs_and_positive_favors_governed():
    rows = []
    for seed, governed, comparison in [(1, 10, 15), (2, 11, 16), (3, 12, 17)]:
        common = {
            "scenario": "S0",
            "seed": seed,
            "p95_time_loss_s": governed,
            "p95_trip_time_s": governed,
            "completed_trips": 100,
            "max_total_queue": governed,
            "max_spillback_duration_s": 0,
            "wan_application_bytes": 10,
            "peer_application_bytes": 10,
            "proposed_unsafe_actions": 0,
            "blocked_unsafe_actions": 0,
            "executed_unsafe_actions": 0,
            "unsafe_actions_per_1000_decisions": 0,
            "emergency_trip_time_s": None,
        }
        rows.append(
            {
                **common,
                "controller": "agentic_governed",
                "mean_time_loss_s": governed,
            }
        )
        rows.append(
            {
                **common,
                "controller": "local_maxwave",
                "mean_time_loss_s": comparison,
                "p95_time_loss_s": comparison,
                "p95_trip_time_s": comparison,
                "max_total_queue": comparison,
            }
        )
    frame = pd.DataFrame(rows)
    summary = summarize(frame)
    paired = paired_comparisons(frame)
    result = paired[
        (paired["metric"] == "mean_time_loss_s")
        & (paired["comparator"] == "local_maxwave")
    ].iloc[0]
    assert len(summary) > 0
    assert result["n_pairs"] == 3
    assert result["mean_paired_difference"] == 5
    assert result["rank_biserial"] == 1
