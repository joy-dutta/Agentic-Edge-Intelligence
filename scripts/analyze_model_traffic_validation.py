from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
METRICS = (
    "post_5min_mean_time_loss_s",
    "post_5min_p95_time_loss_s",
    "post_5min_completed_trips",
    "executed_unsafe_actions",
    "fallback_rate",
)


def read_phase(phase: str, model_label: str) -> pd.DataFrame:
    rows = []
    for path in sorted((ROOT / "artifacts" / "raw" / phase).glob("S2_agentic_*_100?_gpt-5.4-*/summary.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        if int(row["seed"]) not in {1001, 1002, 1003}:
            continue
        rows.append(
            {
                "model_label": model_label,
                "controller": row["controller"],
                "seed": int(row["seed"]),
                **{metric: row.get(metric) for metric in METRICS},
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    frame = pd.concat(
        [read_phase("primary", "nano"), read_phase("validation", "mini")],
        ignore_index=True,
    )
    if len(frame) != 12 or frame.duplicated(["model_label", "controller", "seed"]).any():
        raise RuntimeError(f"Expected 12 unique validation runs, found {len(frame)}")
    rows = []
    for controller in sorted(frame["controller"].unique()):
        pair = frame[frame["controller"] == controller].set_index(["seed", "model_label"])
        for metric in METRICS:
            nano = pair.xs("nano", level="model_label")[metric].astype(float).sort_index()
            mini = pair.xs("mini", level="model_label")[metric].astype(float).sort_index()
            difference = mini - nano
            rows.append(
                {
                    "controller": controller,
                    "metric": metric,
                    "n_pairs": len(difference),
                    "nano_mean": float(nano.mean()),
                    "mini_mean": float(mini.mean()),
                    "mean_mini_minus_nano": float(difference.mean()),
                    "minimum_mini_minus_nano": float(difference.min()),
                    "maximum_mini_minus_nano": float(difference.max()),
                }
            )
    output = pd.DataFrame(rows)
    tables = ROOT / "artifacts" / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    frame.to_csv(tables / "model_validation_traffic_runs.csv", index=False)
    output.to_csv(tables / "model_validation_traffic_comparison.csv", index=False)
    summary = {
        "runs": len(frame),
        "paired_seeds_per_controller": 3,
        "interpretation": (
            "Descriptive holdout sensitivity check only; n=3 per controller is not "
            "used for confirmatory significance claims."
        ),
        "rows": output.to_dict(orient="records"),
    }
    (tables / "model_validation_traffic_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
