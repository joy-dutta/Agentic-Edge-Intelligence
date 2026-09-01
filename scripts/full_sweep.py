from __future__ import annotations

import argparse
import json

from ojcoms_poc.config import load_config
from ojcoms_poc.orchestration import RunSpec, planned_calls, run_matrix


OFFLINE = ("fixed", "local_maxwave", "coordinated_maxpressure", "cloud_maxpressure")
LIVE = ("agentic_unguarded", "agentic_governed")


def scenarios_and_seeds(config):
    simulation = config.section("simulation")
    primary = [int(seed) for seed in simulation["test_seeds_primary"]]
    sensitivity = [int(seed) for seed in simulation["test_seeds_sensitivity"]]
    return {
        "S0": primary,
        "S1": sensitivity,
        "S2": primary,
        "S3": primary,
        "S4": sensitivity,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen confirmatory matrix")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--mode", choices=("offline", "live", "all"), required=True)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    config = load_config(args.config)
    mapping = scenarios_and_seeds(config)
    specs: list[RunSpec] = []
    if args.mode in {"offline", "all"}:
        specs.extend(
            RunSpec(controller, scenario, seed)
            for controller in OFFLINE
            for scenario, seeds in mapping.items()
            for seed in seeds
        )
    if args.mode in {"live", "all"}:
        specs.extend(
            RunSpec(controller, scenario, seed)
            for controller in LIVE
            for scenario, seeds in mapping.items()
            for seed in seeds
        )
        specs.extend(
            RunSpec("agentic_governed_no_peer", scenario, seed)
            for scenario in ("S0", "S2")
            for seed in mapping[scenario]
        )
    calls = sum(planned_calls(spec) for spec in specs)
    limit = int(config.section("budget")["phase_call_limits"]["primary"])
    if calls > limit:
        raise RuntimeError(f"Full plan requires {calls} calls, above limit {limit}")
    results = run_matrix(
        config,
        specs,
        phase="primary",
        shuffle_seed=20260901,
        workers=args.workers,
    )
    print(json.dumps({"runs": len(results), "planned_api_calls": calls}, indent=2))


if __name__ == "__main__":
    main()
