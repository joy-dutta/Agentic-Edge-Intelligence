from __future__ import annotations

import argparse
import json

from ojcoms_poc.config import load_config
from ojcoms_poc.orchestration import RunSpec, planned_calls, run_matrix


OFFLINE = ("fixed", "local_maxwave", "coordinated_maxpressure", "cloud_maxpressure")
LIVE = ("agentic_unguarded", "agentic_governed", "agentic_governed_no_peer")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the frozen two-seed S2 pilot")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument("--mode", choices=("offline", "live", "all"), default="offline")
    parser.add_argument("--phase", default="pilot")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    config = load_config(args.config)
    seeds = [int(seed) for seed in config.section("simulation")["pilot_seeds"]]
    controllers = (
        OFFLINE if args.mode == "offline" else LIVE if args.mode == "live" else OFFLINE + LIVE
    )
    specs = [RunSpec(controller, "S2", seed) for controller in controllers for seed in seeds]
    calls = sum(planned_calls(spec) for spec in specs)
    limit = int(config.section("budget")["phase_call_limits"]["pilot"])
    if calls > limit:
        raise RuntimeError(f"Pilot plan requires {calls} calls, above limit {limit}")
    results = run_matrix(
        config,
        specs,
        phase=args.phase,
        shuffle_seed=20260831,
        workers=args.workers,
    )
    print(json.dumps({"runs": len(results), "planned_api_calls": calls}, indent=2))


if __name__ == "__main__":
    main()
