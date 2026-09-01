from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from ojcoms_poc.config import load_config
from ojcoms_poc.models import AgentIntent, IntersectionState, PeerSummary
from ojcoms_poc.policy import PolicyLimits, PolicyShield


def state_from_payload(agent: dict) -> IntersectionState:
    return IntersectionState(
        intersection_id=str(agent["intersection_id"]),
        sim_time_s=int(agent["sim_time_s"]),
        current_phase=int(agent["current_phase"]),
        phase_elapsed_s=int(agent["phase_elapsed_s"]),
        lane_queues=[int(value) for value in agent["phase_queues"]],
        lane_occupancies=[float(value) for value in agent["phase_occupancies"]],
        max_wait_s=float(agent["max_wait_s"]),
        downstream_blocked=bool(agent["downstream_blocked"]),
        verified_emergency=bool(agent["verified_emergency"]),
        emergency_phase=agent.get("emergency_phase"),
        sensor_complete=bool(agent["sensor_complete"]),
        peers=[PeerSummary.model_validate(peer) for peer in agent["peers"]],
    )


def strata(state: IntersectionState, request_kind: str, scenario: str) -> str:
    flags = []
    if state.verified_emergency:
        flags.append("emergency")
    if state.downstream_blocked:
        flags.append("spillback")
    if not state.sensor_complete:
        flags.append("sensor_incomplete")
    if any(not peer.authenticated for peer in state.peers):
        flags.append("untrusted_peer")
    if any(peer.replayed or peer.age_s > 10 for peer in state.peers):
        flags.append("stale_or_replayed")
    if state.max_wait_s >= 170:
        flags.append("max_wait_boundary")
    return "|".join([scenario, request_kind, "+".join(flags) or "ordinary"])


def candidates(root: Path, phase: str) -> list[dict]:
    rows = []
    for path in sorted((root / "artifacts" / "raw" / phase).glob("*/api_calls.jsonl")):
        summary = json.loads((path.parent / "summary.json").read_text(encoding="utf-8"))
        for call_index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            call = json.loads(line)
            if call.get("schema_valid") is not True or "payload" not in call:
                continue
            intents = {
                row["intersection_id"]: row for row in call["intents"]["intents"]
            }
            for agent in call["payload"]["agents"]:
                intersection_id = str(agent["intersection_id"])
                if intersection_id not in intents:
                    raise ValueError("Recorded payload and intent identities differ")
                state = state_from_payload(agent)
                identity = (
                    f"{summary['run_id']}|{call_index}|{call['observation_sim_time_s']}|"
                    f"{intersection_id}"
                )
                rows.append(
                    {
                        "identity": identity,
                        "selection_hash": hashlib.sha256(identity.encode()).hexdigest(),
                        "stratum": strata(
                            state, str(call["request_kind"]), str(summary["scenario"])
                        ),
                        "run_id": summary["run_id"],
                        "controller": summary["controller"],
                        "scenario": summary["scenario"],
                        "seed": summary["seed"],
                        "call_index": call_index,
                        "request_kind": call["request_kind"],
                        "state": state,
                        "intent": AgentIntent.model_validate(intents[intersection_id]),
                    }
                )
    return rows


def select_stratified(rows: list[dict], count: int) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        groups.setdefault(row["stratum"], []).append(row)
    for values in groups.values():
        values.sort(key=lambda row: row["selection_hash"])
    selected = []
    depth = 0
    while len(selected) < count:
        added = False
        for name in sorted(groups):
            if depth < len(groups[name]):
                selected.append(groups[name][depth])
                added = True
                if len(selected) == count:
                    break
        if not added:
            break
        depth += 1
    if len(selected) != count:
        raise RuntimeError(f"Needed {count} proposals but selected {len(selected)}")
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed-state shield causal audit")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--phase", default="primary")
    parser.add_argument("--count", type=int, default=200)
    args = parser.parse_args()
    root = args.root.resolve()
    config = load_config(root / "configs" / "experiment.yaml")
    raw_limits = config.section("policy")
    shield = PolicyShield(
        {str(value) for value in config.section("simulation")["tls_ids"]},
        PolicyLimits(
            min_green_s=int(raw_limits["min_green_s"]),
            max_green_s=int(raw_limits["max_green_s"]),
            max_approach_wait_s=int(raw_limits["max_approach_wait_s"]),
            max_intent_duration_s=int(raw_limits["max_intent_duration_s"]),
            max_peer_age_s=int(raw_limits["max_peer_age_s"]),
        ),
    )
    selected = select_stratified(candidates(root, args.phase), args.count)
    output_rows = []
    corpus_path = root / "data" / "processed" / "shield_audit_corpus.jsonl"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with corpus_path.open("w", encoding="utf-8") as corpus:
        for index, row in enumerate(selected):
            off = shield.evaluate(row["intent"], row["state"], governance_enabled=False)
            on = shield.evaluate(row["intent"], row["state"], governance_enabled=True)
            corpus.write(
                json.dumps(
                    {
                        "audit_index": index,
                        "identity": row["identity"],
                        "selection_hash": row["selection_hash"],
                        "stratum": row["stratum"],
                        "state": row["state"].model_dump(mode="json"),
                        "proposal": row["intent"].model_dump(mode="json"),
                    },
                    sort_keys=True,
                )
                + "\n"
            )
            output_rows.append(
                {
                    "audit_index": index,
                    "identity": row["identity"],
                    "stratum": row["stratum"],
                    "scenario": row["scenario"],
                    "seed": row["seed"],
                    "controller_source": row["controller"],
                    "request_kind": row["request_kind"],
                    "intent": row["intent"].intent.value,
                    "proposed_unsafe": on.proposed_unsafe,
                    "rule_reasons": ";".join(on.reasons),
                    "shield_off_accepted": off.accepted,
                    "shield_off_executed_unsafe": off.proposed_unsafe and off.accepted,
                    "shield_on_accepted": on.accepted,
                    "shield_on_blocked_unsafe": on.blocked_unsafe,
                    "shield_on_executed_unsafe": on.proposed_unsafe and on.accepted,
                }
            )
    table = pd.DataFrame(output_rows)
    table_path = root / "artifacts" / "tables" / "shield_audit.csv"
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(table_path, index=False)
    summary = {
        "proposals": len(table),
        "proposed_unsafe": int(table["proposed_unsafe"].sum()),
        "shield_off_executed_unsafe": int(table["shield_off_executed_unsafe"].sum()),
        "shield_on_blocked_unsafe": int(table["shield_on_blocked_unsafe"].sum()),
        "shield_on_executed_unsafe": int(table["shield_on_executed_unsafe"].sum()),
        "selection": "round-robin across declared scenario/request/boundary strata, SHA-256 order",
        "false_block_interpretation": "not independently estimable because rule labels define unsafe",
    }
    summary_path = root / "artifacts" / "tables" / "shield_audit_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
