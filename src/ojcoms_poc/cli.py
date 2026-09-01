from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .runner import SumoExperimentRunner


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Run the OJCOMS traffic-control PoC")
    command.add_argument("--config", default="configs/experiment.yaml")
    subcommands = command.add_subparsers(dest="command", required=True)
    run = subcommands.add_parser("run")
    run.add_argument("--controller", required=True)
    run.add_argument("--scenario", required=True)
    run.add_argument("--seed", required=True, type=int)
    run.add_argument("--phase", default="preflight")
    run.add_argument("--tag")
    run.add_argument("--model")
    run.add_argument("--replay-api-calls", type=Path)
    run.add_argument("--ssm-probability", type=float)
    return command


def main() -> None:
    args = parser().parse_args()
    config = load_config(args.config)
    if args.command == "run":
        result = SumoExperimentRunner(config).run(
            args.controller,
            args.scenario,
            args.seed,
            phase=args.phase,
            run_tag=args.tag,
            model_override=args.model,
            replay_api_calls=args.replay_api_calls,
            ssm_probability=args.ssm_probability,
        )
        print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
