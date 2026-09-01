from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pandas as pd
import yaml

from ojcoms_poc.config import load_config


OFFLINE = ("fixed", "local_maxwave", "coordinated_maxpressure", "cloud_maxpressure")
LIVE = ("agentic_unguarded", "agentic_governed", "agentic_governed_no_peer")


def status(condition: bool | None) -> str:
    return "PASS" if condition is True else "FAIL" if condition is False else "PENDING"


def markdown_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "No completed runs yet."
    columns = list(frame.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate the two-seed pilot gate report")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--phase", default="pilot_corrected_v4")
    args = parser.parse_args()
    root = args.root.resolve()
    config = load_config(root / "configs" / "experiment.yaml")
    seeds = [int(value) for value in config.section("simulation")["pilot_seeds"]]
    run_root = root / "artifacts" / "raw" / args.phase
    summaries = []
    for path in sorted(run_root.glob("*/summary.json")):
        row = json.loads(path.read_text(encoding="utf-8"))
        summaries.append(row)
    by_cell = {(row["controller"], int(row["seed"])): row for row in summaries}

    test = subprocess.run(
        [str(Path(__import__("sys").executable)), "-m", "pytest", "-q"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        env={**__import__("os").environ, "PYTHONPATH": "src"},
    )
    offline_complete = all((controller, seed) in by_cell for controller in OFFLINE for seed in seeds)
    live_complete = all((controller, seed) in by_cell for controller in LIVE for seed in seeds)

    inserted_equal: bool | None = None
    teleports_ok: bool | None = None
    baseline_plausible: bool | None = None
    if offline_complete:
        inserted_equal = all(
            len({int(by_cell[(controller, seed)]["inserted_vehicles"]) for controller in OFFLINE})
            == 1
            for seed in seeds
        )
        teleports_ok = all(
            int(row["teleports"]) / max(1, int(row["inserted_vehicles"])) <= 0.005
            for row in summaries
            if row["controller"] in OFFLINE
        )
        baseline_plausible = all(
            float(by_cell[(controller, seed)]["mean_time_loss_s"])
            <= 3 * float(by_cell[("fixed", seed)]["mean_time_loss_s"])
            for controller in OFFLINE
            for seed in seeds
        )

    contract_path = root / "configs" / "api_contract_gate.json"
    contract_ok = None
    if contract_path.exists():
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        contract_ok = bool(contract.get("model_exact") and contract.get("schema_valid"))
    pcap_paths = [
        root / "artifacts" / "tables" / f"pcap_reconciliation_{name}.json"
        for name in ("edge", "cloud")
    ]
    pcap_ok = None
    if all(path.exists() for path in pcap_paths):
        pcap_ok = all(
            json.loads(path.read_text(encoding="utf-8")).get(
                "all_application_counters_reconciled"
            )
            is True
            for path in pcap_paths
        )
    replay_paths = sorted(
        (root / "artifacts" / "raw" / "replay").glob("*/replay_validation.json")
    )
    replay_ok = None
    if replay_paths:
        replay_ok = any(
            json.loads(path.read_text(encoding="utf-8")).get("passed") is True
            for path in replay_paths
        )

    gates = [
        ("Policy, boundary, replay, and analysis tests", status(test.returncode == 0)),
        (
            "All eight offline paired pilot runs complete",
            status(True if offline_complete else None),
        ),
        (
            "All six live agentic paired pilot runs complete",
            status(True if live_complete else None),
        ),
        ("Equivalent inserted exogenous demand within each seed", status(inserted_equal)),
        ("Teleport rate no more than 0.5% in every offline run", status(teleports_ok)),
        ("Baseline mean delay no more than 3x fixed timing", status(baseline_plausible)),
        ("Pinned snapshot and strict schema contract", status(contract_ok)),
        ("Edge and cloud PCAP/application counters reconcile", status(pcap_ok)),
        ("One live run replays with exact scientific summary and logs", status(replay_ok)),
    ]

    table_rows = []
    for row in summaries:
        table_rows.append(
            {
                "controller": row["controller"],
                "seed": row["seed"],
                "mean_loss_s": round(float(row["mean_time_loss_s"]), 2),
                "p95_loss_s": round(float(row["p95_time_loss_s"]), 2),
                "completed": row["completed_trips"],
                "inserted": row.get("inserted_vehicles"),
                "emergency_s": row.get("emergency_trip_time_s"),
                "teleports": row.get("teleports"),
                "collisions": row.get("collisions"),
                "api_calls": row.get("api_calls", 0),
                "api_cost_usd": row.get("api_cost_usd", 0),
            }
        )
    table = pd.DataFrame(table_rows)
    amendment = yaml.safe_load(
        (root / "configs" / "protocol_amendment_001_pre_pilot.yaml").read_text(
            encoding="utf-8"
        )
    )
    budget_rows = []
    ledger = root / "artifacts" / "logs" / "api_usage.jsonl"
    if ledger.exists():
        budget_rows = [json.loads(line) for line in ledger.read_text().splitlines() if line]
    pilot_cost = sum(
        float(row["cost_usd"]) for row in budget_rows if row["phase"] == "pilot"
    )

    lines = [
        "# Corrected Two-Seed Pilot Report",
        "",
        f"Phase: `{args.phase}`. This report is an acceptance gate, not a confirmatory result.",
        "",
        "## Gate Status",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    lines.extend(f"| {name} | **{value}** |" for name, value in gates)
    lines.extend(["", "## Runs", ""])
    lines.append(markdown_table(table))
    lines.extend(
        [
            "",
            "## Budget",
            "",
            f"Recorded live pilot attempts: {sum(row['phase'] == 'pilot' for row in budget_rows)}.",
            f"Recorded live pilot cost: USD {pilot_cost:.6f} of the USD 1 phase limit.",
            "The primary and validation manifests must independently show worst-case cost within their phase limits before those phases can start.",
            "",
            "## Frozen Assumptions",
            "",
            "- Public RESCO Cologne-8 network, routes, phase programs, and one-hour morning interval.",
            "- Five-second deterministic control loop and 120-second supervisory interval.",
            "- API-hosted supervisory reasoning; no hard real-time actuation through the API.",
            "- N0-N3 profiles are controlled sensitivity assumptions, not field measurements.",
            "- SUMO microsimulation; no roadside hardware or physical signal is controlled.",
            "",
            "## Observed Pre-Test Problems And Corrections",
            "",
        ]
    )
    for change in amendment["changes"]:
        lines.append(f"- **Problem:** {change['issue']} **Correction:** {change['correction']}")
    pending_or_failed = [name for name, value in gates if value != "PASS"]
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "All pilot gates pass; the frozen full sweep may proceed."
                if not pending_or_failed
                else "Do not start the full live sweep. Unresolved gates: "
                + "; ".join(pending_or_failed)
                + "."
            ),
            "",
        ]
    )
    output = root / "artifacts" / "pilot_report.md"
    output.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"runs": len(summaries), "report": str(output)}, indent=2))


if __name__ == "__main__":
    main()
