from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from ojcoms_poc.analysis import paired_comparisons, summarize


ROOT = Path(__file__).resolve().parents[1]
SCENARIO_SEEDS = {"S0": 20, "S1": 10, "S2": 20, "S3": 20, "S4": 10}
CORE_CONTROLLERS = {
    "fixed",
    "local_maxwave",
    "coordinated_maxpressure",
    "cloud_maxpressure",
    "agentic_unguarded",
    "agentic_governed",
}


def compare_tables(generated: pd.DataFrame, released_path: Path, keys: list[str]) -> None:
    released = pd.read_csv(released_path)
    generated = generated[released.columns]
    generated = generated.sort_values(keys).reset_index(drop=True)
    released = released.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(
        generated,
        released,
        check_dtype=False,
        check_exact=False,
        rtol=1e-12,
        atol=1e-12,
    )


def verify_matrix(frame: pd.DataFrame) -> None:
    if len(frame) != 520:
        raise AssertionError(f"Expected 520 confirmatory runs, found {len(frame)}")
    if frame.duplicated(["scenario", "controller", "seed"]).any():
        raise AssertionError("Duplicate scenario/controller/seed cells found")
    for scenario, seeds in SCENARIO_SEEDS.items():
        for controller in CORE_CONTROLLERS:
            count = len(
                frame[
                    (frame["scenario"] == scenario)
                    & (frame["controller"] == controller)
                ]
            )
            if count != seeds:
                raise AssertionError(
                    f"Expected {seeds} runs for {scenario}/{controller}, found {count}"
                )
    for scenario in ("S0", "S2"):
        count = len(
            frame[
                (frame["scenario"] == scenario)
                & (frame["controller"] == "agentic_governed_no_peer")
            ]
        )
        if count != 20:
            raise AssertionError(f"Expected 20 no-peer runs for {scenario}, found {count}")
    unexpected = frame[
        (frame["controller"] == "agentic_governed_no_peer")
        & (~frame["scenario"].isin(["S0", "S2"]))
    ]
    if not unexpected.empty:
        raise AssertionError("Unexpected no-peer confirmatory cells found")


def verify_governance(frame: pd.DataFrame) -> dict[str, int]:
    governed = frame[frame["controller"] == "agentic_governed"]
    totals = {
        "proposed": int(governed["proposed_unsafe_actions"].sum()),
        "blocked": int(governed["blocked_unsafe_actions"].sum()),
        "executed": int(governed["executed_unsafe_actions"].sum()),
    }
    expected = {"proposed": 1191, "blocked": 1191, "executed": 0}
    if totals != expected:
        raise AssertionError(f"Governance totals changed: expected {expected}, found {totals}")
    return totals


def main() -> None:
    frame_path = ROOT / "data" / "processed" / "run_level_results.csv"
    frame = pd.read_csv(frame_path)
    verify_matrix(frame)

    generated_main = summarize(frame)
    generated_paired = paired_comparisons(frame)
    compare_tables(
        generated_main,
        ROOT / "artifacts" / "tables" / "main_results.csv",
        ["scenario", "controller", "metric"],
    )
    compare_tables(
        generated_paired,
        ROOT / "artifacts" / "tables" / "paired_comparisons.csv",
        ["scenario", "metric", "governed", "comparator"],
    )
    governance = verify_governance(frame)
    print(
        json.dumps(
            {
                "status": "passed",
                "confirmatory_runs": len(frame),
                "main_result_rows": len(generated_main),
                "paired_comparison_rows": len(generated_paired),
                "governance_totals": governance,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

