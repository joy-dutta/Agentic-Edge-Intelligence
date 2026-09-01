from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd
from openai import APIConnectionError, APITimeoutError, InternalServerError

from ojcoms_poc.agents import InvalidSupervisorResponseError, OpenAISupervisor
from ojcoms_poc.budget import BudgetLedger
from ojcoms_poc.config import load_config
from ojcoms_poc.orchestration import verify_live_gate


def source_calls(root: Path, phase: str) -> list[dict]:
    candidates = []
    for path in sorted((root / "artifacts" / "raw" / phase).glob("*/api_calls.jsonl")):
        summary = json.loads((path.parent / "summary.json").read_text(encoding="utf-8"))
        if summary["controller"] != "agentic_governed":
            continue
        for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            row = json.loads(line)
            if row.get("schema_valid") is not True or "payload" not in row:
                continue
            identity = f"{summary['run_id']}|{index}|{row['payload_sha256']}"
            candidates.append(
                {
                    "identity": identity,
                    "selection_hash": hashlib.sha256(identity.encode()).hexdigest(),
                    "stratum": f"{summary['scenario']}|{row['request_kind']}",
                    "scenario": summary["scenario"],
                    "seed": summary["seed"],
                    "payload": row["payload"],
                    "request_kind": row["request_kind"],
                }
            )
    return candidates


def select(candidates: list[dict], count: int) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in candidates:
        groups.setdefault(row["stratum"], []).append(row)
    for values in groups.values():
        values.sort(key=lambda row: row["selection_hash"])
    selected = []
    depth = 0
    while len(selected) < count:
        progressed = False
        for key in sorted(groups):
            if depth < len(groups[key]):
                selected.append(groups[key][depth])
                progressed = True
                if len(selected) == count:
                    return selected
        if not progressed:
            break
        depth += 1
    raise RuntimeError(f"Only {len(selected)} eligible states were available")


def intent_signature(intent: dict) -> tuple:
    return (
        intent["intent"],
        intent["strength"],
        intent["requested_duration_s"],
        intent["neighbor_request"],
        intent["reason_code"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure pinned-model output repeatability")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--phase", default="primary")
    parser.add_argument("--states", type=int, default=50)
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    if args.states * args.repetitions > 250:
        raise RuntimeError("Repeatability audit exceeds the registered 250-call ceiling")
    root = args.root.resolve()
    config = load_config(root / "configs" / "experiment.yaml")
    verify_live_gate(config, "primary")
    if not (root / "configs" / "api_contract_gate.json").exists():
        raise RuntimeError("The pinned-model contract probe has not passed")
    chosen = select(source_calls(root, args.phase), args.states)
    openai_config = config.section("openai")
    budget = config.section("budget")
    artifacts = root / "artifacts"
    ledger = BudgetLedger(
        artifacts / "logs" / "api_usage.jsonl",
        openai_config["prices_per_million"],
        float(budget["local_limit_usd"]),
        budget["phase_limits_usd"],
        int(budget["max_request_attempts"]),
        budget["phase_call_limits"],
    )
    supervisor = OpenAISupervisor(
        model=str(openai_config["primary_model"]),
        prompt_path=config.resolve(config.section("paths")["supervisor_prompt"]),
        ledger=ledger,
        phase="primary",
        max_output_tokens=int(openai_config["max_output_tokens"]),
        max_estimated_input_tokens=int(openai_config["max_estimated_input_tokens"]),
        worst_case_billed_input_tokens=int(
            openai_config["worst_case_billed_input_tokens"]
        ),
        reasoning_effort=str(openai_config["reasoning_effort"]),
        store=bool(openai_config["store"]),
        max_retries=int(budget["max_retries"]),
        audit_path=artifacts / "raw" / "audits" / "repeatability_api_calls.jsonl",
    )
    rows = []
    for state_index, source in enumerate(chosen):
        outputs = []
        state_rows = []
        for repetition in range(args.repetitions):
            base_row = {
                "state_index": state_index,
                "repetition": repetition,
                "source_identity": source["identity"],
                "scenario": source["scenario"],
                "seed": source["seed"],
            }
            try:
                result = supervisor.decide(
                    source["payload"],
                    observation_sim_time_s=int(
                        source["payload"]["observation_sim_time_s"]
                    ),
                    request_kind=f"repeatability:{source['request_kind']}",
                )
                intents = result.intents.model_dump(mode="json")["intents"]
                outputs.append(intents)
                row = {
                    **base_row,
                    "status": "ok",
                    "latency_s": result.latency_s,
                    "input_tokens": result.input_tokens,
                    "cached_input_tokens": result.cached_input_tokens,
                    "output_tokens": result.output_tokens,
                    "estimated_input_tokens": result.estimated_input_tokens,
                    "output_sha256": hashlib.sha256(
                        json.dumps(
                            intents, sort_keys=True, separators=(",", ":")
                        ).encode()
                    ).hexdigest(),
                }
            except InvalidSupervisorResponseError as exc:
                outputs.append(None)
                row = {
                    **base_row,
                    "status": type(exc).__name__,
                    "latency_s": exc.latency_s,
                    "input_tokens": exc.input_tokens,
                    "cached_input_tokens": exc.cached_input_tokens,
                    "output_tokens": exc.output_tokens,
                    "estimated_input_tokens": None,
                    "output_sha256": None,
                }
            except (APIConnectionError, APITimeoutError, InternalServerError) as exc:
                outputs.append(None)
                row = {
                    **base_row,
                    "status": type(exc).__name__,
                    "latency_s": None,
                    "input_tokens": 0,
                    "cached_input_tokens": 0,
                    "output_tokens": 0,
                    "estimated_input_tokens": None,
                    "output_sha256": None,
                }
            rows.append(row)
            state_rows.append(row)
        agreement = []
        for agent_index in range(8):
            signatures = [
                intent_signature(output[agent_index])
                for output in outputs
                if output is not None
            ]
            modal_count = Counter(signatures).most_common(1)[0][1] if signatures else 0
            agreement.append(modal_count / args.repetitions)
        valid_outputs = [output for output in outputs if output is not None]
        unique_valid_outputs = len(
            {
                hashlib.sha256(
                    json.dumps(output, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                for output in valid_outputs
            }
        )
        for row in state_rows:
            row["state_mean_agent_modal_agreement"] = sum(agreement) / len(agreement)
            row["state_unique_exact_outputs"] = unique_valid_outputs
            row["state_valid_repetitions"] = len(valid_outputs)
            row["state_all_repetitions_valid"] = (
                len(valid_outputs) == args.repetitions
            )
    table = pd.DataFrame(rows)
    output = artifacts / "tables" / "repeatability_audit.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    summary = {
        "states": args.states,
        "repetitions": args.repetitions,
        "calls": len(table),
        "valid_calls": int((table["status"] == "ok").sum()),
        "failed_calls": int((table["status"] != "ok").sum()),
        "mean_agent_modal_agreement": float(
            table.groupby("state_index")["state_mean_agent_modal_agreement"].first().mean()
        ),
        "states_all_repetitions_valid": int(
            table.groupby("state_index")["state_all_repetitions_valid"].first().sum()
        ),
        "states_with_exactly_one_output": int(
            (
                table.groupby("state_index")
                .first()
                .eval("state_all_repetitions_valid and state_unique_exact_outputs == 1")
            ).sum()
        ),
        "api_cost_usd": float(
            sum(
                ledger.estimate_cost(
                    str(openai_config["primary_model"]),
                    int(row.input_tokens),
                    int(row.output_tokens),
                    int(row.cached_input_tokens),
                )
                for row in table.itertuples()
            )
        ),
    }
    (artifacts / "tables" / "repeatability_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
