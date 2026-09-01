from __future__ import annotations

import argparse
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        summary_path = path.parent / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary["controller"] != "agentic_governed":
            continue
        for call_index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            call = json.loads(line)
            if call.get("schema_valid") is not True or "payload" not in call:
                continue
            identity = f"{summary['run_id']}|{call_index}|{call['payload_sha256']}"
            candidates.append(
                {
                    "identity": identity,
                    "selection_hash": hashlib.sha256(identity.encode()).hexdigest(),
                    "stratum": f"{summary['scenario']}|{call['request_kind']}",
                    "scenario": summary["scenario"],
                    "seed": summary["seed"],
                    "request_kind": call["request_kind"],
                    "payload": call["payload"],
                    "batched_intents": {
                        intent["intersection_id"]: intent
                        for intent in call["intents"]["intents"]
                    },
                }
            )
    return candidates


def select_stratified(candidates: list[dict], count: int) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in candidates:
        groups.setdefault(row["stratum"], []).append(row)
    for values in groups.values():
        values.sort(key=lambda row: row["selection_hash"])
    selected = []
    depth = 0
    while len(selected) < count:
        progressed = False
        for name in sorted(groups):
            if depth < len(groups[name]):
                selected.append(groups[name][depth])
                progressed = True
                if len(selected) == count:
                    return selected
        if not progressed:
            break
        depth += 1
    raise RuntimeError(f"Only {len(selected)} eligible corridor states were available")


def signature(intent: dict) -> tuple:
    return (
        intent["intent"],
        intent["strength"],
        intent["requested_duration_s"],
        intent["neighbor_request"],
        intent["reason_code"],
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure eight independent logical-agent calls in parallel"
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--phase", default="primary")
    parser.add_argument("--states", type=int, default=25)
    args = parser.parse_args()
    if args.states * 8 > 200:
        raise RuntimeError("Independent-agent audit exceeds the registered 200-call ceiling")

    root = args.root.resolve()
    config = load_config(root / "configs" / "experiment.yaml")
    verify_live_gate(config, "primary")
    if not (root / "configs" / "api_contract_gate.json").exists():
        raise RuntimeError("The pinned-model contract probe has not passed")
    chosen = select_stratified(source_calls(root, args.phase), args.states)
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
        audit_path=artifacts / "raw" / "audits" / "independent_agent_api_calls.jsonl",
    )

    rows = []
    for state_index, source in enumerate(chosen):
        observation_time = int(source["payload"]["observation_sim_time_s"])
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {}
            for agent_index, agent in enumerate(source["payload"]["agents"]):
                payload = {**source["payload"], "agents": [agent]}
                future = executor.submit(
                    supervisor.decide,
                    payload,
                    observation_sim_time_s=observation_time,
                    request_kind=f"independent:{source['request_kind']}",
                )
                futures[future] = (agent_index, agent)
            completed = []
            for future in as_completed(futures):
                agent_index, agent = futures[future]
                try:
                    completed.append((agent_index, agent, future.result(), None))
                except (
                    InvalidSupervisorResponseError,
                    APIConnectionError,
                    APITimeoutError,
                    InternalServerError,
                ) as exc:
                    completed.append((agent_index, agent, None, exc))
        batch_wall_latency_s = time.perf_counter() - start
        for agent_index, agent, result, error in sorted(completed):
            intersection_id = str(agent["intersection_id"])
            batched_intent = source["batched_intents"][intersection_id]
            if result is not None:
                intent = result.intents.model_dump(mode="json")["intents"][0]
                status = "ok"
                call_latency_s = result.latency_s
                input_tokens = result.input_tokens
                cached_input_tokens = result.cached_input_tokens
                output_tokens = result.output_tokens
                estimated_input_tokens = result.estimated_input_tokens
                exact_agreement = signature(intent) == signature(batched_intent)
                independent_intent = intent["intent"]
            elif isinstance(error, InvalidSupervisorResponseError):
                status = type(error).__name__
                call_latency_s = error.latency_s
                input_tokens = error.input_tokens
                cached_input_tokens = error.cached_input_tokens
                output_tokens = error.output_tokens
                estimated_input_tokens = None
                exact_agreement = False
                independent_intent = None
            else:
                status = type(error).__name__
                call_latency_s = None
                input_tokens = 0
                cached_input_tokens = 0
                output_tokens = 0
                estimated_input_tokens = None
                exact_agreement = False
                independent_intent = None
            rows.append(
                {
                    "state_index": state_index,
                    "agent_index": agent_index,
                    "source_identity": source["identity"],
                    "scenario": source["scenario"],
                    "seed": source["seed"],
                    "intersection_id": intersection_id,
                    "request_kind": source["request_kind"],
                    "status": status,
                    "call_latency_s": call_latency_s,
                    "parallel_batch_wall_latency_s": batch_wall_latency_s,
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached_input_tokens,
                    "output_tokens": output_tokens,
                    "estimated_input_tokens": estimated_input_tokens,
                    "exact_intent_agreement_with_batched": exact_agreement,
                    "independent_intent": independent_intent,
                    "batched_intent": batched_intent["intent"],
                }
            )

    table = pd.DataFrame(rows)
    table_path = artifacts / "tables" / "independent_agent_latency.csv"
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(table_path, index=False)
    state_wall = table.groupby("state_index")["parallel_batch_wall_latency_s"].first()
    summary = {
        "corridor_states": args.states,
        "logical_agents_per_state": 8,
        "calls": len(table),
        "valid_calls": int((table["status"] == "ok").sum()),
        "failed_calls": int((table["status"] != "ok").sum()),
        "call_latency_p50_s": float(table["call_latency_s"].quantile(0.50)),
        "call_latency_p95_s": float(table["call_latency_s"].quantile(0.95)),
        "parallel_batch_wall_latency_p50_s": float(state_wall.quantile(0.50)),
        "parallel_batch_wall_latency_p95_s": float(state_wall.quantile(0.95)),
        "exact_intent_agreement_with_batched": float(
            table["exact_intent_agreement_with_batched"].mean()
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
    summary_path = artifacts / "tables" / "independent_agent_latency_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
