from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import bootstrap, rankdata, wilcoxon
from statsmodels.stats.multitest import multipletests

from ojcoms_poc.analysis import load_runs


ROOT = Path(__file__).resolve().parents[1]
GOVERNED = "agentic_governed"
COMPARATORS = (
    "agentic_governed_no_peer",
    "local_maxwave",
    "coordinated_maxpressure",
)
METRICS = {
    "post_5min_mean_time_loss_s": ("Post-warm-up mean time loss (s)", "lower"),
    "post_5min_p95_time_loss_s": ("Post-warm-up P95 time loss (s)", "lower"),
    "maximum_approach_wait_s": ("Maximum approach wait (s)", "lower"),
    "max_spillback_duration_s": ("Maximum spillback duration (s)", "lower"),
    "post_5min_completed_trips": ("Post-warm-up completed trips", "higher"),
    "approach_wait_fairness_jain": ("Approach-wait Jain fairness", "higher"),
    "collisions": ("SUMO collisions", "lower"),
    "teleports": ("SUMO teleports", "lower"),
    "executed_unsafe_actions": ("Executed unsafe actions", "lower"),
    "fallback_rate": ("Fallback rate", "lower"),
    "wan_application_bytes": ("API application bytes", "context"),
    "peer_application_bytes": ("Peer application bytes", "context"),
}


def bca_interval(values: np.ndarray, seed: int) -> tuple[float, float]:
    if np.allclose(values, values[0]):
        return float(values[0]), float(values[0])
    result = bootstrap(
        (values,),
        np.mean,
        n_resamples=10_000,
        confidence_level=0.95,
        method="BCa",
        rng=np.random.default_rng(seed),
    )
    return float(result.confidence_interval.low), float(result.confidence_interval.high)


def rank_biserial(values: np.ndarray) -> float:
    nonzero = values[values != 0]
    if not len(nonzero):
        return 0.0
    ranks = rankdata(np.abs(nonzero))
    return float((ranks[nonzero > 0].sum() - ranks[nonzero < 0].sum()) / ranks.sum())


def paired_table(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    seed = 20260910
    for scenario in sorted(frame["scenario"].unique()):
        for metric, (label, direction) in METRICS.items():
            for comparator in COMPARATORS:
                pair = frame[
                    (frame["scenario"] == scenario)
                    & frame["controller"].isin([GOVERNED, comparator])
                ].pivot(index="seed", columns="controller", values=metric)
                if GOVERNED not in pair or comparator not in pair:
                    continue
                pair = pair[[GOVERNED, comparator]].apply(pd.to_numeric, errors="coerce").dropna()
                if len(pair) < 2:
                    continue
                governed = pair[GOVERNED].to_numpy(float)
                compared = pair[comparator].to_numpy(float)
                raw = compared - governed
                benefit = -raw if direction == "higher" else raw
                low, high = bca_interval(benefit, seed)
                seed += 1
                p_value = 1.0
                if not np.allclose(benefit, 0):
                    p_value = float(wilcoxon(benefit, alternative="two-sided").pvalue)
                denominator = float(np.mean(compared))
                percent = float(np.mean(benefit) / denominator * 100) if denominator else math.nan
                rows.append(
                    {
                        "scenario": scenario,
                        "metric": metric,
                        "metric_label": label,
                        "direction": direction,
                        "comparator": comparator,
                        "n_pairs": len(pair),
                        "governed_mean": float(np.mean(governed)),
                        "comparator_mean": float(np.mean(compared)),
                        "mean_paired_benefit": float(np.mean(benefit)),
                        "percent_benefit_vs_comparator": percent,
                        "ci95_bca_low": low,
                        "ci95_bca_high": high,
                        "rank_biserial": rank_biserial(benefit),
                        "wilcoxon_p_raw": p_value,
                    }
                )
    output = pd.DataFrame(rows)
    output["wilcoxon_p_holm"] = math.nan
    output["holm_reject_0_05"] = False
    tested = output[output["direction"] != "context"]
    for _, indices in tested.groupby("metric").groups.items():
        reject, corrected, _, _ = multipletests(
            output.loc[indices, "wilcoxon_p_raw"].to_numpy(float),
            alpha=0.05,
            method="holm",
        )
        output.loc[indices, "wilcoxon_p_holm"] = corrected
        output.loc[indices, "holm_reject_0_05"] = reject
    return output


def api_summary() -> dict:
    rows = [
        json.loads(line)
        for line in (ROOT / "artifacts" / "logs" / "api_usage.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    followup = [row for row in rows if row.get("phase") == "followup"]
    statuses = pd.Series([row.get("status", "unknown") for row in followup]).value_counts()
    return {
        "attempts_reaching_api": len(followup),
        "cost_usd": round(sum(float(row.get("cost_usd", 0)) for row in followup), 8),
        "status_counts": {str(key): int(value) for key, value in statuses.items()},
    }


def decision_summary(frame: pd.DataFrame, paired: pd.DataFrame) -> dict:
    comparison = paired[
        (paired["metric"] == "post_5min_mean_time_loss_s")
        & (paired["comparator"] == "agentic_governed_no_peer")
    ].set_index("scenario")
    c8 = comparison.loc["F1_C8"]
    c3 = comparison.loc["F1_C3"]
    all_zero = bool((frame[["collisions", "teleports"]].fillna(0) == 0).all().all())
    c8_primary = bool(
        c8["percent_benefit_vs_comparator"] >= 5.0
        and c8["ci95_bca_low"] > 0
    )
    c3_consistent = bool(c3["mean_paired_benefit"] > 0)
    return {
        "cologne8_five_percent_and_ci_excludes_zero": c8_primary,
        "cologne3_direction_consistent": c3_consistent,
        "all_registered_collision_and_teleport_counts_zero": all_zero,
        "coordination_claim_decision_rule_met": bool(c8_primary and c3_consistent and all_zero),
        "verdict_effect": (
            "followup_does_not_upgrade_initial_verdict"
            if not (c8_primary and c3_consistent and all_zero)
            else "followup_supports_coordination_upgrade_subject_to_secondary_metrics"
        ),
    }


def make_figure(frame: pd.DataFrame, output: Path) -> None:
    labels = {
        "agentic_governed": "Governed peer-aware",
        "agentic_governed_no_peer": "Governed no-peer",
        "local_maxwave": "Local MaxWave",
        "coordinated_maxpressure": "Coordinated MP",
    }
    plot = frame.copy()
    plot["Controller"] = plot["controller"].map(labels)
    plot["Network"] = plot["scenario"].map({"F1_C8": "Cologne-8", "F1_C3": "Cologne-3"})
    order = list(labels.values())
    sns.set_theme(style="whitegrid", context="paper")
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), constrained_layout=True)
    for ax, metric, title in (
        (axes[0], "post_5min_mean_time_loss_s", "Mean trip time loss"),
        (axes[1], "post_5min_p95_time_loss_s", "P95 trip time loss"),
    ):
        sns.boxplot(
            data=plot,
            x="Controller",
            y=metric,
            hue="Network",
            order=order,
            showfliers=False,
            ax=ax,
        )
        sns.stripplot(
            data=plot,
            x="Controller",
            y=metric,
            hue="Network",
            order=order,
            dodge=True,
            alpha=0.6,
            size=3,
            legend=False,
            ax=ax,
        )
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_ylabel("Seconds")
        ax.tick_params(axis="x", rotation=18)
    handles, legend_labels = axes[0].get_legend_handles_labels()
    axes[0].legend(handles[:2], legend_labels[:2], frameon=False, loc="upper left")
    axes[1].get_legend().remove()
    fig.savefig(output.with_suffix(".png"), dpi=300)
    fig.savefig(output.with_suffix(".pdf"))
    plt.close(fig)


def main() -> None:
    frame = load_runs(ROOT, "followup")
    expected = {
        (scenario, controller, seed)
        for scenario, seeds in (
            ("F1_C8", range(4101, 4111)),
            ("F1_C3", range(4201, 4211)),
        )
        for controller in (GOVERNED, *COMPARATORS)
        for seed in seeds
    }
    observed = set(frame[["scenario", "controller", "seed"]].itertuples(index=False, name=None))
    if observed != expected:
        raise RuntimeError(
            f"Follow-up matrix mismatch: missing={sorted(expected - observed)}, "
            f"unexpected={sorted(observed - expected)}"
        )
    paired = paired_table(frame)
    tables = ROOT / "artifacts" / "tables"
    figures = ROOT / "artifacts" / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    frame.to_csv(tables / "followup_run_level.csv", index=False)
    paired.to_csv(tables / "followup_paired_comparisons.csv", index=False)
    summary = {
        "registered_runs": len(frame),
        "runs_by_scenario_controller": {
            f"{scenario}:{controller}": int(count)
            for (scenario, controller), count in frame.groupby(["scenario", "controller"]).size().items()
        },
        "api": api_summary(),
        "safety_totals": {
            "collisions": int(pd.to_numeric(frame["collisions"]).sum()),
            "teleports": int(pd.to_numeric(frame["teleports"]).sum()),
            "executed_unsafe_actions": int(pd.to_numeric(frame["executed_unsafe_actions"]).sum()),
        },
        "decision": decision_summary(frame, paired),
    }
    (tables / "followup_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    make_figure(frame, figures / "figure_E_followup_coordination")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
