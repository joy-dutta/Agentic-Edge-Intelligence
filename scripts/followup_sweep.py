from __future__ import annotations

import argparse
import json

from ojcoms_poc.config import load_config
from ojcoms_poc.orchestration import RunSpec, run_matrix


CONTROLLERS = (
    "agentic_governed",
    "agentic_governed_no_peer",
    "local_maxwave",
    "coordinated_maxpressure",
)
NETWORKS = (
    ("configs/followup_cologne8.yaml", "F1_C8"),
    ("configs/followup_cologne3.yaml", "F1_C3"),
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen coordination follow-up")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--network",
        choices=("all", "cologne8", "cologne3"),
        default="all",
    )
    args = parser.parse_args()
    selected = NETWORKS
    if args.network != "all":
        selected = tuple(item for item in NETWORKS if args.network in item[0])

    completed: list[dict] = []
    for config_path, scenario in selected:
        config = load_config(config_path)
        seeds = [int(value) for value in config.section("simulation")["followup_seeds"]]
        specs = [
            RunSpec(controller, scenario, seed)
            for controller in CONTROLLERS
            for seed in seeds
        ]
        completed.extend(
            run_matrix(
                config,
                specs,
                phase="followup",
                shuffle_seed=20260902,
                workers=args.workers,
            )
        )
    print(
        json.dumps(
            {
                "runs": len(completed),
                "planned_live_api_calls": sum(
                    31
                    for row in completed
                    if row["controller"]
                    in {"agentic_governed", "agentic_governed_no_peer"}
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
