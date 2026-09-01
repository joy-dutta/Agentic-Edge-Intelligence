from __future__ import annotations

import json
from datetime import UTC, datetime

from ojcoms_poc.agents import OpenAISupervisor
from ojcoms_poc.budget import BudgetLedger
from ojcoms_poc.config import load_config
from ojcoms_poc.orchestration import verify_live_gate


def main() -> None:
    config = load_config()
    verify_live_gate(config, "pilot")
    openai_config = config.section("openai")
    budget_config = config.section("budget")
    model = str(openai_config["primary_model"])
    artifacts = config.resolve(config.section("paths")["artifacts"])
    ledger = BudgetLedger(
        artifacts / "logs" / "api_usage.jsonl",
        openai_config["prices_per_million"],
        float(budget_config["local_limit_usd"]),
        budget_config["phase_limits_usd"],
        int(budget_config["max_request_attempts"]),
        budget_config["phase_call_limits"],
    )
    supervisor = OpenAISupervisor(
        model=model,
        prompt_path=config.resolve(config.section("paths")["supervisor_prompt"]),
        ledger=ledger,
        phase="pilot",
        max_output_tokens=int(openai_config["max_output_tokens"]),
        max_estimated_input_tokens=int(openai_config["max_estimated_input_tokens"]),
        worst_case_billed_input_tokens=int(
            openai_config["worst_case_billed_input_tokens"]
        ),
        reasoning_effort=str(openai_config["reasoning_effort"]),
        store=bool(openai_config["store"]),
        max_retries=0,
        audit_path=artifacts / "preflight" / "api_contract_calls.jsonl",
    )
    payload = {
        "protocol_version": "1.0",
        "observation_sim_time_s": 25200,
        "request_kind": "contract_probe",
        "agents": [
            {
                "intersection_id": str(tls_id),
                "sim_time_s": 25200,
                "current_phase": 0,
                "phase_elapsed_s": 20,
                "phase_queues": [0, 0],
                "phase_occupancies": [0.0, 0.0],
                "max_wait_s": 0.0,
                "downstream_blocked": False,
                "verified_emergency": False,
                "emergency_phase": None,
                "sensor_complete": True,
                "peers": [],
                "memory": [],
                "allowed_neighbors": [],
            }
            for tls_id in config.section("simulation")["tls_ids"]
        ],
    }
    result = supervisor.decide(
        payload,
        observation_sim_time_s=25200,
        request_kind="contract_probe",
    )
    evidence = {
        "verified_utc": datetime.now(UTC).isoformat(),
        "model_requested": model,
        "model_returned": result.model,
        "model_exact": result.model == model,
        "schema_valid": len(result.intents.intents) == 8,
        "store": bool(openai_config["store"]),
        "reasoning_effort": str(openai_config["reasoning_effort"]),
        "max_output_tokens": int(openai_config["max_output_tokens"]),
        "attempts": result.attempts,
        "input_tokens": result.input_tokens,
        "cached_input_tokens": result.cached_input_tokens,
        "output_tokens": result.output_tokens,
        "estimated_input_tokens": result.estimated_input_tokens,
        "cost_usd": ledger.estimate_cost(
            model,
            result.input_tokens,
            result.output_tokens,
            result.cached_input_tokens,
        ),
    }
    gate_path = config.root / "configs" / "api_contract_gate.json"
    gate_path.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
