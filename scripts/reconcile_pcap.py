from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Reconcile MQTT app counters and PCAP bytes")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--architecture", choices=("edge", "cloud"), required=True)
    parser.add_argument("--pcap", type=Path, default=Path("artifacts/pcap/network_harness.pcap"))
    parser.add_argument("--max-transport-ratio", type=float, default=3.0)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()
    root = args.root.resolve()
    result_dir = root / "artifacts" / "network"
    rows = {
        role: json.loads(
            (result_dir / f"{role}_{args.architecture}.json").read_text(encoding="utf-8")
        )
        for role in ("simulator", "edge", "cloud")
    }
    active = rows[args.architecture]
    simulator = rows["simulator"]
    if simulator["published_messages"] != active["received_messages"]:
        raise RuntimeError("Telemetry message counters do not reconcile")
    if simulator["published_application_bytes"] != active["received_application_bytes"]:
        raise RuntimeError("Telemetry application bytes do not reconcile")
    if simulator["received_messages"] != active["action_published_messages"]:
        raise RuntimeError("Action message counters do not reconcile")
    if (
        simulator["received_application_bytes"]
        != active["action_published_application_bytes"]
    ):
        raise RuntimeError("Action application bytes do not reconcile")
    if args.architecture == "edge":
        if active["peer_published_messages"] != active["peer_received_messages"]:
            raise RuntimeError("Peer message counters do not reconcile")
        if (
            active["peer_published_application_bytes"]
            != active["peer_received_application_bytes"]
        ):
            raise RuntimeError("Peer application bytes do not reconcile")
    display_filter = ["-Y", "tcp.port == 8883", "-T", "fields", "-e", "frame.len"]
    if shutil.which("tshark"):
        command = [
            "tshark",
            "-r",
            str((root / args.pcap).resolve()),
            *display_filter,
        ]
    else:
        command = [
            args.docker,
            "compose",
            "run",
            "--rm",
            "--no-deps",
            "pcap",
            "tshark",
            "-r",
            f"/pcap/{args.pcap.name}",
            *display_filter,
        ]
    completed = subprocess.run(command, check=True, text=True, capture_output=True)
    lengths = [int(value) for value in completed.stdout.splitlines() if value.strip()]
    pcap_bytes = sum(lengths)
    app_endpoint_bytes = sum(
        int(row["published_application_bytes"])
        + int(row["received_application_bytes"])
        + int(row.get("peer_received_application_bytes", 0))
        for row in rows.values()
    )
    ratio = pcap_bytes / app_endpoint_bytes
    if not 1.0 <= ratio <= args.max_transport_ratio:
        raise RuntimeError(f"PCAP/application byte ratio {ratio:.3f} is outside tolerance")
    summary = {
        "architecture": args.architecture,
        "pcap_frames_tls_mqtt": len(lengths),
        "pcap_transport_bytes": pcap_bytes,
        "application_endpoint_bytes": app_endpoint_bytes,
        "pcap_to_application_ratio": ratio,
        "accepted_ratio": [1.0, args.max_transport_ratio],
        "telemetry_messages": simulator["published_messages"],
        "action_messages": simulator["received_messages"],
        "all_application_counters_reconciled": True,
    }
    output = root / "artifacts" / "tables" / f"pcap_reconciliation_{args.architecture}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
