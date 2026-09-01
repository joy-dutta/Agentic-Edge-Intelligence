from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ojcoms_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import rankdata, wilcoxon
from statsmodels.stats.multitest import multipletests

from .config import load_config


PRIMARY_METRICS: dict[str, tuple[str, str]] = {
    "mean_time_loss_s": ("Mean time loss (s)", "lower"),
    "p95_time_loss_s": ("P95 time loss (s)", "lower"),
    "p95_trip_time_s": ("P95 trip time (s)", "lower"),
    "emergency_trip_time_s": ("Emergency trip time (s)", "lower"),
    "completed_trips": ("Completed trips", "higher"),
    "max_total_queue": ("Maximum total queue", "lower"),
    "max_spillback_duration_s": ("Maximum spillback duration (s)", "lower"),
    "wan_application_bytes": ("WAN application bytes/h", "lower"),
    "peer_application_bytes": ("Peer application bytes/h", "lower"),
    "proposed_unsafe_actions": ("Proposed policy violations", "lower"),
    "blocked_unsafe_actions": ("Blocked policy violations", "context"),
    "executed_unsafe_actions": ("Executed policy violations", "lower"),
    "unsafe_actions_per_1000_decisions": (
        "Executed violations per 1,000 decisions",
        "lower",
    ),
}

MAIN_CONTROLLERS = [
    "cloud_maxpressure",
    "local_maxwave",
    "agentic_unguarded",
    "agentic_governed",
]


def flatten(row: dict[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                output[f"{key}_{child_key}"] = child_value
        elif isinstance(value, (str, int, float, bool)) or value is None:
            output[key] = value
        else:
            output[key] = json.dumps(value, sort_keys=True)
    controller = str(row["controller"])
    if controller == "cloud_maxpressure":
        output["wan_application_bytes"] = int(
            row.get("cloud_wan", {}).get("application_bytes", 0)
        )
    elif controller.startswith("agentic_"):
        output["wan_application_bytes"] = int(
            row.get("api_request_application_bytes", 0)
        ) + int(row.get("api_response_application_bytes", 0))
    else:
        output["wan_application_bytes"] = 0
    output["peer_application_bytes"] = int(
        row.get("peer_network", {}).get("application_bytes", 0)
    )
    output["communication_footprint_bytes"] = (
        output["wan_application_bytes"]
        + output["peer_application_bytes"]
        + int(row.get("audit_log_bytes", 0))
    )
    return output


def load_runs(root: Path, phase: str = "primary") -> pd.DataFrame:
    paths = sorted((root / "artifacts" / "raw" / phase).glob("*/summary.json"))
    if not paths:
        raise FileNotFoundError(f"No completed {phase!r} summary files were found")
    rows = [flatten(json.loads(path.read_text(encoding="utf-8"))) for path in paths]
    frame = pd.DataFrame(rows)
    if frame.duplicated(["controller", "scenario", "seed"]).any():
        raise ValueError("Duplicate controller/scenario/seed summaries detected")
    return frame.sort_values(["scenario", "seed", "controller"]).reset_index(drop=True)


def filter_confirmatory_runs(
    frame: pd.DataFrame,
    primary_seeds: set[int],
    sensitivity_seeds: set[int],
) -> pd.DataFrame:
    expected_seeds = {
        "S0": primary_seeds,
        "S1": sensitivity_seeds,
        "S2": primary_seeds,
        "S3": primary_seeds,
        "S4": sensitivity_seeds,
    }
    keep = frame.apply(
        lambda row: int(row["seed"]) in expected_seeds.get(str(row["scenario"]), set()),
        axis=1,
    )
    return frame.loc[keep].reset_index(drop=True)


def bootstrap_interval(
    values: np.ndarray,
    statistic: Callable[[np.ndarray], float],
    rng: np.random.Generator,
    repetitions: int = 10_000,
) -> tuple[float, float]:
    if len(values) == 1:
        value = statistic(values)
        return value, value
    indices = rng.integers(0, len(values), size=(repetitions, len(values)))
    sampled = values[indices]
    estimates = np.apply_along_axis(statistic, 1, sampled)
    return tuple(float(value) for value in np.quantile(estimates, [0.025, 0.975]))


def rank_biserial(differences: np.ndarray) -> float:
    nonzero = differences[differences != 0]
    if not len(nonzero):
        return 0.0
    ranks = rankdata(np.abs(nonzero))
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    return (positive - negative) / float(ranks.sum())


def summarize(frame: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(20260902)
    rows: list[dict[str, Any]] = []
    for scenario in sorted(frame["scenario"].unique()):
        for controller in sorted(frame["controller"].unique()):
            subset = frame[
                (frame["scenario"] == scenario)
                & (frame["controller"] == controller)
            ]
            if subset.empty:
                continue
            for metric, (label, _) in PRIMARY_METRICS.items():
                values = pd.to_numeric(subset.get(metric), errors="coerce").dropna().to_numpy()
                if not len(values):
                    continue
                statistic = np.median if metric.startswith("p95_") else np.mean
                low, high = bootstrap_interval(values, statistic, rng)
                rows.append(
                    {
                        "scenario": scenario,
                        "controller": controller,
                        "metric": metric,
                        "metric_label": label,
                        "n_runs": len(values),
                        "estimate": float(statistic(values)),
                        "ci95_low": low,
                        "ci95_high": high,
                        "summary_statistic": (
                            "median_of_run_values" if statistic is np.median else "mean_of_runs"
                        ),
                    }
                )
    return pd.DataFrame(rows)


def paired_comparisons(frame: pd.DataFrame) -> pd.DataFrame:
    rng = np.random.default_rng(20260903)
    rows: list[dict[str, Any]] = []
    governed = "agentic_governed"
    for scenario in sorted(frame["scenario"].unique()):
        controllers = sorted(set(frame[frame["scenario"] == scenario]["controller"]) - {governed})
        for metric, (label, direction) in PRIMARY_METRICS.items():
            if direction == "context":
                continue
            for comparator in controllers:
                pair = frame[
                    (frame["scenario"] == scenario)
                    & (frame["controller"].isin([governed, comparator]))
                ].pivot(index="seed", columns="controller", values=metric)
                if governed not in pair or comparator not in pair:
                    continue
                pair = pair[[governed, comparator]].apply(pd.to_numeric, errors="coerce").dropna()
                if len(pair) < 2:
                    continue
                raw = pair[comparator].to_numpy(float) - pair[governed].to_numpy(float)
                differences = -raw if direction == "higher" else raw
                low, high = bootstrap_interval(differences, np.mean, rng)
                if np.allclose(differences, 0):
                    p_value = 1.0
                else:
                    try:
                        p_value = float(
                            wilcoxon(differences, alternative="two-sided").pvalue
                        )
                    except ValueError:
                        p_value = 1.0
                rows.append(
                    {
                        "scenario": scenario,
                        "metric": metric,
                        "metric_label": label,
                        "governed": governed,
                        "comparator": comparator,
                        "n_pairs": len(pair),
                        "difference_definition": "positive_favors_governed",
                        "mean_paired_difference": float(np.mean(differences)),
                        "median_paired_difference": float(np.median(differences)),
                        "ci95_low": low,
                        "ci95_high": high,
                        "rank_biserial": rank_biserial(differences),
                        "wilcoxon_p_raw": p_value,
                    }
                )
    output = pd.DataFrame(rows)
    if output.empty:
        return output
    output["wilcoxon_p_holm"] = math.nan
    output["holm_reject_0_05"] = False
    for metric, indices in output.groupby("metric").groups.items():
        reject, corrected, _, _ = multipletests(
            output.loc[indices, "wilcoxon_p_raw"].to_numpy(float),
            alpha=0.05,
            method="holm",
        )
        output.loc[indices, "wilcoxon_p_holm"] = corrected
        output.loc[indices, "holm_reject_0_05"] = reject
    return output


def _box_strip(ax, data: pd.DataFrame, metric: str, title: str) -> None:
    if data.empty or metric not in data or data[metric].dropna().empty:
        ax.set_title(title)
        ax.text(0.5, 0.5, "Not available in this phase", ha="center", va="center")
        ax.set_axis_off()
        return
    present = set(data["controller"])
    order = [value for value in MAIN_CONTROLLERS if value in present]
    order.extend(sorted(present.difference(order)))
    sns.boxplot(data=data, x="controller", y=metric, order=order, ax=ax, color="#d9e5e8", fliersize=0)
    sns.stripplot(
        data=data,
        x="controller",
        y=metric,
        order=order,
        hue="scenario",
        dodge=True,
        jitter=0.12,
        size=3,
        ax=ax,
    )
    ax.set_title(title)
    ax.set_xlabel("")
    ax.tick_params(axis="x", rotation=24)
    if ax.legend_ is not None:
        ax.legend_.set_title("Scenario")


def figures(frame: pd.DataFrame, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="paper")

    main = frame[frame["controller"].isin(MAIN_CONTROLLERS)].copy()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    _box_strip(axes[0, 0], main, "mean_time_loss_s", "Mean vehicle time loss")
    _box_strip(axes[0, 1], main, "p95_time_loss_s", "Tail vehicle time loss")
    emergency = main[main["emergency_trip_time_s"].notna()]
    _box_strip(axes[1, 0], emergency, "emergency_trip_time_s", "Emergency response")
    _box_strip(axes[1, 1], main, "completed_trips", "Completed trips")
    for suffix in ("png", "pdf"):
        fig.savefig(output / f"figure_A_traffic_performance.{suffix}", dpi=300)
    plt.close(fig)

    agentic = frame[frame["controller"].str.startswith("agentic_")].copy()
    fig, axes = plt.subplots(2, 2, figsize=(11, 7), constrained_layout=True)
    _box_strip(axes[0, 0], main, "wan_application_bytes", "WAN application traffic")
    _box_strip(axes[0, 1], agentic, "api_latency_p95_s", "P95 API latency")
    _box_strip(axes[1, 0], agentic, "executed_unsafe_actions", "Executed policy violations")
    _box_strip(axes[1, 1], agentic, "local_fallback_control_rate", "Local fallback control rate")
    for suffix in ("png", "pdf"):
        fig.savefig(output / f"figure_B_network_governance.{suffix}", dpi=300)
    plt.close(fig)

    ablations = frame[
        frame["controller"].isin(
            [
                "coordinated_maxpressure",
                "agentic_governed_no_peer",
                "agentic_governed",
            ]
        )
    ].copy()
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    _box_strip(axes[0], ablations, "mean_time_loss_s", "Coordination ablations")
    _box_strip(axes[1], ablations, "p95_time_loss_s", "Ablation tail delay")
    _box_strip(axes[2], ablations, "maximum_approach_wait_s", "Maximum approach wait")
    for suffix in ("png", "pdf"):
        fig.savefig(output / f"figure_C_stress_ablations.{suffix}", dpi=300)
    plt.close(fig)


def run_analysis(root: Path, phase: str = "primary") -> dict[str, int]:
    frame = load_runs(root, phase)
    excluded_nonconfirmatory_runs = 0
    if phase == "primary":
        simulation = load_config(root / "configs" / "experiment.yaml").section(
            "simulation"
        )
        confirmatory = filter_confirmatory_runs(
            frame,
            {int(seed) for seed in simulation["test_seeds_primary"]},
            {int(seed) for seed in simulation["test_seeds_sensitivity"]},
        )
        excluded_nonconfirmatory_runs = len(frame) - len(confirmatory)
        frame = confirmatory
    processed = root / "data" / "processed"
    tables = root / "artifacts" / "tables"
    processed.mkdir(parents=True, exist_ok=True)
    tables.mkdir(parents=True, exist_ok=True)
    frame.to_csv(processed / "run_level_results.csv", index=False)
    frame.to_parquet(processed / "run_level_results.parquet", index=False)
    main = summarize(frame)
    paired = paired_comparisons(frame)
    main.to_csv(tables / "main_results.csv", index=False)
    paired.to_csv(tables / "paired_comparisons.csv", index=False)
    figures(frame, root / "artifacts" / "figures")
    return {
        "runs": len(frame),
        "excluded_nonconfirmatory_runs": excluded_nonconfirmatory_runs,
        "summary_rows": len(main),
        "paired_rows": len(paired),
    }
