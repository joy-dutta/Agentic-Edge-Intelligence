from __future__ import annotations

import argparse
import json
from pathlib import Path

from ojcoms_poc.analysis import run_analysis


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze paired agentic-edge PoC runs")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--phase", default="primary")
    args = parser.parse_args()
    print(json.dumps(run_analysis(args.root.resolve(), args.phase), indent=2))


if __name__ == "__main__":
    main()
