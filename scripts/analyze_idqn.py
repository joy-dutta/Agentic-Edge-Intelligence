from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "ojcoms_matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import wilcoxon

from ojcoms_poc.analysis import bootstrap_interval, rank_biserial


METRICS = {
    "mean_time_loss_s": "lower",
    "p95_time_loss_s": "lower",
    "p95_trip_time_s": "lower",
    "completed_trips": "higher",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze paired frozen-IDQN placement runs")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    source = root / "data" / "processed" / "idqn_placement_results.csv"
    frame = pd.read_csv(source)
    if len(frame) != 40 or set(frame["placement"]) != {"local", "cloud"}:
        raise RuntimeError("Expected 20 paired local and cloud IDQN runs")
    if frame.duplicated(["placement", "seed"]).any():
        raise RuntimeError("Duplicate IDQN placement/seed rows")

    rng = np.random.default_rng(20260905)
    summary_rows = []
    paired_rows = []
    for metric, direction in METRICS.items():
        for placement in ("local", "cloud"):
            values = frame.loc[frame["placement"] == placement, metric].to_numpy(float)
            low, high = bootstrap_interval(values, np.mean, rng)
            summary_rows.append(
                {
                    "metric": metric,
                    "placement": placement,
                    "n_runs": len(values),
                    "mean": float(np.mean(values)),
                    "ci95_low": low,
                    "ci95_high": high,
                }
            )
        pair = frame.pivot(index="seed", columns="placement", values=metric).dropna()
        raw = pair["cloud"].to_numpy(float) - pair["local"].to_numpy(float)
        differences = -raw if direction == "higher" else raw
        low, high = bootstrap_interval(differences, np.mean, rng)
        p_value = 1.0 if np.allclose(differences, 0) else float(wilcoxon(differences).pvalue)
        paired_rows.append(
            {
                "metric": metric,
                "n_pairs": len(pair),
                "difference_definition": "positive_favors_local_placement",
                "mean_paired_difference": float(np.mean(differences)),
                "ci95_low": low,
                "ci95_high": high,
                "rank_biserial": rank_biserial(differences),
                "wilcoxon_p": p_value,
            }
        )

    tables = root / "artifacts" / "tables"
    figures = root / "artifacts" / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(summary_rows).to_csv(tables / "idqn_placement_summary.csv", index=False)
    pd.DataFrame(paired_rows).to_csv(tables / "idqn_placement_paired.csv", index=False)

    curve = pd.read_csv(root / "checkpoints" / "idqn_100episodes" / "learning_curve.csv")
    curve["reward_rolling_10"] = curve["episode_reward"].rolling(10, min_periods=1).mean()
    sns.set_theme(style="whitegrid", context="paper")
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
    axes[0].plot(curve["episode"], curve["episode_reward"], color="#8ba6aa", alpha=0.45)
    axes[0].plot(curve["episode"], curve["reward_rolling_10"], color="#1d4f5a")
    axes[0].set(title="IDQN training", xlabel="Episode", ylabel="Episode reward")
    sns.boxplot(
        data=frame,
        x="placement",
        y="mean_time_loss_s",
        color="#d9e5e8",
        fliersize=0,
        ax=axes[1],
    )
    sns.stripplot(
        data=frame,
        x="placement",
        y="mean_time_loss_s",
        hue="seed",
        palette="viridis",
        jitter=0.08,
        size=3,
        legend=False,
        ax=axes[1],
    )
    axes[1].set(title="Frozen IDQN placement", xlabel="", ylabel="Mean time loss (s)")
    for suffix in ("png", "pdf"):
        fig.savefig(figures / f"figure_D_idqn_placement.{suffix}", dpi=300)
    plt.close(fig)
    print(json.dumps({"runs": len(frame), "paired_metrics": len(paired_rows)}, indent=2))


if __name__ == "__main__":
    main()
