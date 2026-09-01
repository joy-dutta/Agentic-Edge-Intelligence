from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd
from openai import APIConnectionError, APITimeoutError, InternalServerError

from ojcoms_poc.agents import InvalidSupervisorResponseError, OpenAISupervisor
from ojcoms_poc.budget import BudgetLedger
from ojcoms_poc.config import load_config
from ojcoms_poc.orchestration import RunSpec, planned_calls, run_matrix, verify_live_gate


CONTROLLERS = ("agentic_unguarded", "agentic_governed")


def validation_specs(config, model: str) -> list[RunSpec]:
    seeds = [int(seed) for seed in config.section("simulation")["validation_seeds"]]
    return [
        RunSpec(controller, "S2", seed, model=model)
        for controller in CONTROLLERS
        for seed in seeds
    ]


def source_calls(root: Path, model: str, validation_seeds: set[int]) -> list[dict]:
    rows = []
    for path in sorted((root / "artifacts" / "raw" / "primary").glob("*/api_calls.jsonl")):
        summary_path = path.parent / "summary.json"
        if not summary_path.exists():
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        if summary.get("api_model") != model or int(summary["seed"]) not in validation_seeds:
            continue
        for call_index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
            call = json.loads(line)
            if call.get("schema_valid") is not True or "payload" not in call:
                continue
            identity = f"{summary['run_id']}|{call_index}|{call['payload_sha256']}"
            rows.append(
                {
                    "identity": identity,
                    "selection_hash": hashlib.sha256(identity.encode()).hexdigest(),
                    "stratum": f"{summary['controller']}|{call['request_kind']}",
                    "controller": summary["controller"],
                    "seed": int(summary["seed"]),
                    "request_kind": call["request_kind"],
                    "payload": call["payload"],
                    "nano_intents": call["intents"]["intents"],
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
    raise RuntimeError(f"Only {len(selected)} eligible validation states were available")


def intent_signature(intent: dict) -> tuple:
    return (
        intent["intersection_id"],
        intent["intent"],
        intent["strength"],
        intent["requested_duration_s"],
        intent["neighbor_request"],
        intent["reason_code"],
    )


def run_sweep(config, *, model: str, phase: str, shuffle_seed: int) -> None:
    specs = validation_specs(config, model)
    calls = sum(planned_calls(spec) for spec in specs)
    results = run_matrix(config, specs, phase=phase, shuffle_seed=shuffle_seed)
    print(
        json.dumps(
            {"phase": phase, "model": model, "runs": len(results), "planned_calls": calls},
            indent=2,
        )
    )


def run_state_subset(config, count: int) -> None:
    verify_live_gate(config, "validation")
    root = config.root
    openai_config = config.section("openai")
    budget = config.section("budget")
    primary_model = str(openai_config["primary_model"])
    validation_model = str(openai_config["validation_model"])
    validation_seeds = {
        int(seed) for seed in config.section("simulation")["validation_seeds"]
    }
    chosen = select_stratified(
        source_calls(root, primary_model, validation_seeds), count
    )
    artifacts = config.resolve(config.section("paths")["artifacts"])
    ledger = BudgetLedger(
        artifacts / "logs" / "api_usage.jsonl",
        openai_config["prices_per_million"],
        float(budget["local_limit_usd"]),
        budget["phase_limits_usd"],
        int(budget["max_request_attempts"]),
        budget["phase_call_limits"],
    )
    supervisor = OpenAISupervisor(
        model=validation_model,
        prompt_path=config.resolve(config.section("paths")["supervisor_prompt"]),
        ledger=ledger,
        phase="validation",
        max_output_tokens=int(openai_config["max_output_tokens"]),
        max_estimated_input_tokens=int(openai_config["max_estimated_input_tokens"]),
        worst_case_billed_input_tokens=int(
            openai_config["worst_case_billed_input_tokens"]
        ),
        reasoning_effort=str(openai_config["reasoning_effort"]),
        store=bool(openai_config["store"]),
        max_retries=int(budget["max_retries"]),
        audit_path=artifacts / "raw" / "audits" / "model_validation_api_calls.jsonl",
    )
    rows = []
    for state_index, source in enumerate(chosen):
        observation_time = int(source["payload"]["observation_sim_time_s"])
        base_row = {
            "state_index": state_index,
            "source_identity": source["identity"],
            "controller": source["controller"],
            "seed": source["seed"],
            "request_kind": source["request_kind"],
        }
        try:
            result = supervisor.decide(
                source["payload"],
                observation_sim_time_s=observation_time,
                request_kind=f"model_validation:{source['request_kind']}",
            )
            mini_intents = result.intents.model_dump(mode="json")["intents"]
            nano_by_id = {
                intent["intersection_id"]: intent for intent in source["nano_intents"]
            }
            agreements = [
                intent_signature(intent)
                == intent_signature(nano_by_id[intent["intersection_id"]])
                for intent in mini_intents
            ]
            row = {
                **base_row,
                "status": "ok",
                "agent_exact_agreement_rate": sum(agreements) / len(agreements),
                "all_eight_exact_agreement": all(agreements),
                "mini_latency_s": result.latency_s,
                "mini_input_tokens": result.input_tokens,
                "mini_cached_input_tokens": result.cached_input_tokens,
                "mini_output_tokens": result.output_tokens,
                "mini_estimated_input_tokens": result.estimated_input_tokens,
            }
        except InvalidSupervisorResponseError as exc:
            row = {
                **base_row,
                "status": type(exc).__name__,
                "agent_exact_agreement_rate": 0.0,
                "all_eight_exact_agreement": False,
                "mini_latency_s": exc.latency_s,
                "mini_input_tokens": exc.input_tokens,
                "mini_cached_input_tokens": exc.cached_input_tokens,
                "mini_output_tokens": exc.output_tokens,
                "mini_estimated_input_tokens": None,
            }
        except (APIConnectionError, APITimeoutError, InternalServerError) as exc:
            row = {
                **base_row,
                "status": type(exc).__name__,
                "agent_exact_agreement_rate": 0.0,
                "all_eight_exact_agreement": False,
                "mini_latency_s": None,
                "mini_input_tokens": 0,
                "mini_cached_input_tokens": 0,
                "mini_output_tokens": 0,
                "mini_estimated_input_tokens": None,
            }
        rows.append(row)
    table = pd.DataFrame(rows)
    table_path = artifacts / "tables" / "model_validation_state_agreement.csv"
    table_path.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(table_path, index=False)
    summary = {
        "states": len(table),
        "logical_agent_outputs": len(table) * 8,
        "valid_calls": int((table["status"] == "ok").sum()),
        "failed_calls": int((table["status"] != "ok").sum()),
        "mean_agent_exact_agreement_rate": float(table["agent_exact_agreement_rate"].mean()),
        "all_eight_exact_agreement_states": int(table["all_eight_exact_agreement"].sum()),
        "mini_latency_p50_s": float(table["mini_latency_s"].quantile(0.50)),
        "mini_latency_p95_s": float(table["mini_latency_s"].quantile(0.95)),
        "api_cost_usd": float(
            sum(
                ledger.estimate_cost(
                    validation_model,
                    int(row.mini_input_tokens),
                    int(row.mini_output_tokens),
                    int(row.mini_cached_input_tokens),
                )
                for row in table.itertuples()
            )
        ),
    }
    (artifacts / "tables" / "model_validation_state_agreement_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run paired nano/mini validation")
    parser.add_argument("--config", default="configs/experiment.yaml")
    parser.add_argument(
        "--stage", choices=("nano-sweep", "mini-sweep", "mini-states"), required=True
    )
    parser.add_argument("--states", type=int, default=50)
    args = parser.parse_args()
    config = load_config(args.config)
    models = config.section("openai")
    if args.stage == "nano-sweep":
        run_sweep(
            config,
            model=str(models["primary_model"]),
            phase="primary",
            shuffle_seed=20260903,
        )
    elif args.stage == "mini-sweep":
        run_sweep(
            config,
            model=str(models["validation_model"]),
            phase="validation",
            shuffle_seed=20260904,
        )
    else:
        if args.states > 50:
            raise RuntimeError("Model state validation exceeds the registered 50-call ceiling")
        run_state_subset(config, args.states)


if __name__ == "__main__":
    main()
