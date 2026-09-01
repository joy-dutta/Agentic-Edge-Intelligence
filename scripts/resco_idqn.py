from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pandas as pd

from ojcoms_poc.config import load_config
from ojcoms_poc.metrics import parse_safety_statistics, parse_tripinfo


EPISODE_PATTERN = re.compile(
    r"Episode: (?P<episode>\d+), Best: (?P<best>\d+), Best Reward: "
    r"(?P<best_reward>-?[0-9.]+), Episode Reward: (?P<reward>-?[0-9.]+)"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_directory(root: Path) -> Path:
    candidates = sorted(
        {path.parent for path in root.rglob("config.json")},
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        archives = sorted(root.rglob("*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
        if not archives:
            raise FileNotFoundError(f"No RESCO run directory or final archive found under {root}")
        archive = archives[0]
        destination = root / "_materialized" / archive.stem
        if not (destination / "config.json").exists():
            destination.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as handle:
                for member in handle.infolist():
                    member_path = Path(member.filename)
                    if member_path.is_absolute() or ".." in member_path.parts:
                        raise RuntimeError(f"Unsafe path in RESCO archive: {member.filename}")
                handle.extractall(destination)
        return destination
    return candidates[0]


def windows_posix(path: Path) -> str:
    resolved = path.resolve()
    if os.name == "nt":
        drive, tail = os.path.splitdrive(str(resolved))
        if drive.upper() != "C:":
            raise ValueError("RESCO short-path adapter currently requires the C drive")
        return "/" + tail.lstrip("\\/").replace("\\", "/")
    return str(resolved)


def package(training_root: Path, training_log: Path, repository: Path) -> None:
    source = run_directory(training_root)
    metrics = sorted(
        source.glob("metrics_*.csv"),
        key=lambda path: int(path.stem.split("_")[-1]),
    )
    episodes = [int(path.stem.split("_")[-1]) for path in metrics]
    if episodes != list(range(1, 101)):
        raise RuntimeError(f"Expected episodes 1-100, found {episodes[:3]}...{episodes[-3:]}")
    checkpoints = sorted(source.glob("agt_*.pt"))
    if len(checkpoints) != 8:
        raise RuntimeError(f"Expected eight IDQN checkpoints, found {len(checkpoints)}")

    destination = repository / "checkpoints" / "idqn_100episodes"
    destination.mkdir(parents=True, exist_ok=True)
    for checkpoint in checkpoints:
        shutil.copy2(checkpoint, destination / checkpoint.name)
    shutil.copy2(source / "config.json", destination / "resco_training_config.json")

    curve_rows = []
    for match in EPISODE_PATTERN.finditer(training_log.read_text(encoding="utf-8")):
        curve_rows.append(
            {
                "episode": int(match.group("episode")),
                "training_seed": 101 + int(match.group("episode")) % 10,
                "episode_reward": float(match.group("reward")),
                "best_episode_to_date": int(match.group("best")),
                "best_reward_to_date": float(match.group("best_reward")),
            }
        )
    if [row["episode"] for row in curve_rows] != list(range(1, 101)):
        raise RuntimeError("Training log does not contain one ordered record per episode")
    curve = pd.DataFrame(curve_rows)
    curve.to_csv(destination / "learning_curve.csv", index=False)

    manifest = {
        "resco_commit": "f1ed9a174f8de41fc9d8689373b836bc882570dc",
        "episodes": 100,
        "training_seeds": list(range(101, 111)),
        "source_temp_directory": str(training_root),
        "excluded_interrupted_branch": "C:/Users/joydu/idqntrain episodes 21-38 after checkpoint 20",
        "files_sha256": {
            path.name: sha256(path)
            for path in sorted(destination.iterdir())
            if path.is_file()
        },
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"source": str(source), "destination": str(destination)}, indent=2))


def evaluate_one(
    repository: Path,
    checkpoints: Path,
    output_root: Path,
    *,
    placement: str,
) -> Path:
    output_root.mkdir(parents=True, exist_ok=False)
    delay = 0 if placement == "local" else 1
    loss = 0.0 if placement == "local" else 0.005
    command = [
        sys.executable,
        "main.py",
        "@cologne8",
        "@IDQN",
        "libsumo:False",
        "episodes:0",
        "testing:20",
        "save_model:False",
        "save_console_log:False",
        "delete_episode_logs:False",
        "seed:2101",
        "seed_cycle:20",
        "seed_episode_origin:1",
        "training:False",
        "load_replay:False",
        f"load_model:{checkpoints.name}",
        f"action_delay_s:{delay}",
        f"action_loss_rate:{loss}",
        f"log_dir:{windows_posix(output_root)}",
    ]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(repository / "external" / "RESCO")
    completed = subprocess.run(
        command,
        cwd=repository / "external" / "RESCO" / "resco_benchmark",
        env=environment,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"RESCO {placement} evaluation failed: {completed.returncode}")
    return run_directory(output_root)


def evaluation_rows(source: Path, placement: str) -> list[dict]:
    tripinfos = sorted(
        source.glob("tripinfo_*.xml"),
        key=lambda path: int(path.stem.split("_")[-1]),
    )
    tripinfos = [path for path in tripinfos if path.stem != "tripinfo_0"]
    if len(tripinfos) != 20:
        raise RuntimeError(f"Expected 20 real IDQN test episodes, found {len(tripinfos)}")
    rows = []
    for index, tripinfo in enumerate(tripinfos):
        trip_metrics, _ = parse_tripinfo(tripinfo, "no_emergency_in_s0")
        statistic = source / f"statistics_{index + 1}.xml"
        safety = parse_safety_statistics(statistic) if statistic.exists() else {}
        rows.append(
            {
                **trip_metrics,
                **safety,
                "controller": f"idqn_{placement}",
                "placement": placement,
                "scenario": "S0",
                "seed": 2101 + index,
                "action_delay_s": 0 if placement == "local" else 1,
                "action_loss_rate": 0.0 if placement == "local" else 0.005,
            }
        )
    return rows


def evaluate(repository: Path, temp_root: Path) -> None:
    checkpoints = repository / "checkpoints" / "idqn_100episodes"
    if len(list(checkpoints.glob("agt_*.pt"))) != 8:
        raise RuntimeError("Package the completed checkpoints before evaluation")
    staged = repository / "external" / "RESCO" / "checkpoints" / checkpoints.name
    staged.mkdir(parents=True, exist_ok=True)
    for checkpoint in checkpoints.glob("agt_*.pt"):
        shutil.copy2(checkpoint, staged / checkpoint.name)
    all_rows = []
    for placement in ("local", "cloud"):
        source = evaluate_one(
            repository,
            staged,
            temp_root / f"idqn_eval_{placement}",
            placement=placement,
        )
        all_rows.extend(evaluation_rows(source, placement))
    destination = repository / "data" / "processed" / "idqn_placement_results.csv"
    destination.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(destination, index=False)
    print(json.dumps({"runs": len(all_rows), "output": str(destination)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Package and evaluate official RESCO IDQN")
    subcommands = parser.add_subparsers(dest="command", required=True)
    package_parser = subcommands.add_parser("package")
    package_parser.add_argument("--training-root", type=Path, required=True)
    package_parser.add_argument("--training-log", type=Path, required=True)
    package_parser.add_argument("--repository", type=Path, default=Path.cwd())
    evaluate_parser = subcommands.add_parser("evaluate")
    evaluate_parser.add_argument("--repository", type=Path, default=Path.cwd())
    evaluate_parser.add_argument("--temp-root", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "package":
        package(args.training_root.resolve(), args.training_log.resolve(), args.repository.resolve())
    else:
        evaluate(args.repository.resolve(), args.temp_root.resolve())


if __name__ == "__main__":
    main()
