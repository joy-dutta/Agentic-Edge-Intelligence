from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

import tiktoken
from openai import APIConnectionError, APITimeoutError, InternalServerError, OpenAI
from pydantic import ValidationError

from .budget import BudgetLedger
from .models import CorridorResponse


@dataclass(frozen=True)
class SupervisorResult:
    observation_sim_time_s: int
    request_kind: str
    model: str
    response_id: str
    latency_s: float
    attempts: int
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    estimated_input_tokens: int
    request_application_bytes: int
    response_application_bytes: int
    intents: CorridorResponse


class InvalidSupervisorResponseError(RuntimeError):
    """A billed response that cannot safely enter the control path."""

    def __init__(
        self,
        message: str,
        *,
        response_id: str,
        latency_s: float,
        input_tokens: int,
        cached_input_tokens: int,
        output_tokens: int,
        request_application_bytes: int,
        response_application_bytes: int,
    ) -> None:
        super().__init__(message)
        self.response_id = response_id
        self.latency_s = latency_s
        self.input_tokens = input_tokens
        self.cached_input_tokens = cached_input_tokens
        self.output_tokens = output_tokens
        self.request_application_bytes = request_application_bytes
        self.response_application_bytes = response_application_bytes


class OpenAISupervisor:
    def __init__(
        self,
        *,
        model: str,
        prompt_path: Path,
        ledger: BudgetLedger,
        phase: str,
        max_output_tokens: int,
        reasoning_effort: str,
        store: bool,
        max_retries: int,
        audit_path: Path,
        max_estimated_input_tokens: int = 5_000,
        worst_case_billed_input_tokens: int = 5_000,
        timeout_s: float = 30.0,
        client: OpenAI | None = None,
    ) -> None:
        self.model = model
        self.prompt = prompt_path.read_text(encoding="utf-8").strip()
        self.ledger = ledger
        self.phase = phase
        self.max_output_tokens = int(max_output_tokens)
        self.reasoning_effort = reasoning_effort
        self.store = bool(store)
        self.max_retries = int(max_retries)
        self.audit_path = audit_path
        self.max_estimated_input_tokens = int(max_estimated_input_tokens)
        self.worst_case_billed_input_tokens = int(worst_case_billed_input_tokens)
        self.encoding = tiktoken.get_encoding("o200k_base")
        self._audit_lock = Lock()
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self.client = client or OpenAI(timeout=timeout_s, max_retries=0)

    def _append_audit(self, row: dict[str, Any]) -> None:
        with self._audit_lock:
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, sort_keys=True) + "\n")

    def decide(
        self,
        payload: dict[str, Any],
        *,
        observation_sim_time_s: int,
        request_kind: str,
    ) -> SupervisorResult:
        input_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        format_spec = {
            "type": "json_schema",
            "name": "corridor_supervisory_intents",
            "schema": CorridorResponse.model_json_schema(),
            "strict": True,
        }
        request_body = {
            "model": self.model,
            "instructions": self.prompt,
            "input": input_json,
            "reasoning": {"effort": self.reasoning_effort},
            "max_output_tokens": self.max_output_tokens,
            "store": self.store,
            "text": {"format": format_spec, "verbosity": "low"},
        }
        request_bytes = len(
            json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        estimated_input_tokens = len(
            self.encoding.encode(
                json.dumps(request_body, sort_keys=True, separators=(",", ":"))
            )
        )
        if estimated_input_tokens > self.max_estimated_input_tokens:
            raise ValueError(
                f"Estimated input token count {estimated_input_tokens} exceeds "
                f"the frozen limit {self.max_estimated_input_tokens}"
            )
        worst_cost = self.ledger.estimate_cost(
            self.model, self.worst_case_billed_input_tokens, self.max_output_tokens
        )
        started_utc = datetime.now(UTC).isoformat()
        start = time.perf_counter()
        attempts = 0

        while True:
            attempts += 1
            response = None
            usage_recorded = False
            input_tokens = 0
            cached = 0
            output_tokens = 0
            reservation_id = self.ledger.authorize(self.phase, worst_cost)
            try:
                response = self.client.responses.create(
                    model=self.model,
                    instructions=self.prompt,
                    input=input_json,
                    reasoning={"effort": self.reasoning_effort},
                    max_output_tokens=self.max_output_tokens,
                    store=self.store,
                    text={
                        "format": format_spec,
                        "verbosity": "low",
                    },
                )
                latency_s = time.perf_counter() - start
                usage = response.usage
                input_tokens = int(usage.input_tokens)
                cached = int(
                    getattr(
                        getattr(usage, "input_tokens_details", None),
                        "cached_tokens",
                        0,
                    )
                    or 0
                )
                output_tokens = int(usage.output_tokens)
                if response.model != self.model:
                    raise ValueError(
                        f"Returned model {response.model!r} does not match pinned model"
                    )
                response_text = response.output_text
                invalid_kwargs = {
                    "response_id": response.id,
                    "latency_s": latency_s,
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached,
                    "output_tokens": output_tokens,
                    "request_application_bytes": request_bytes,
                    "response_application_bytes": len(response_text.encode("utf-8")),
                }
                if getattr(response, "status", None) == "incomplete":
                    raise InvalidSupervisorResponseError(
                        "The Responses API returned an incomplete structured output",
                        **invalid_kwargs,
                    )
                try:
                    parsed = CorridorResponse.model_validate_json(response_text)
                except ValidationError as exc:
                    raise InvalidSupervisorResponseError(
                        "The Responses API output failed strict schema validation",
                        **invalid_kwargs,
                    ) from exc
                expected_ids = [str(agent["intersection_id"]) for agent in payload["agents"]]
                returned_ids = [intent.intersection_id for intent in parsed.intents]
                if returned_ids != expected_ids:
                    raise InvalidSupervisorResponseError(
                        "Response intersection identities or order do not match the request",
                        **invalid_kwargs,
                    )
                self.ledger.append(
                    self.phase,
                    self.model,
                    "ok",
                    input_tokens,
                    output_tokens,
                    cached,
                    response.id,
                    reservation_id,
                )
                usage_recorded = True
                response_bytes = len(response_text.encode("utf-8"))
                result = SupervisorResult(
                    observation_sim_time_s=observation_sim_time_s,
                    request_kind=request_kind,
                    model=response.model,
                    response_id=response.id,
                    latency_s=latency_s,
                    attempts=attempts,
                    input_tokens=input_tokens,
                    cached_input_tokens=cached,
                    output_tokens=output_tokens,
                    estimated_input_tokens=estimated_input_tokens,
                    request_application_bytes=request_bytes,
                    response_application_bytes=response_bytes,
                    intents=parsed,
                )
                self._append_audit(
                    {
                        **asdict(result),
                        "started_utc": started_utc,
                        "completed_utc": datetime.now(UTC).isoformat(),
                        "schema_valid": True,
                        "payload_sha256": hashlib.sha256(
                            input_json.encode("utf-8")
                        ).hexdigest(),
                        "payload": payload,
                        "estimated_input_tokens": estimated_input_tokens,
                        "intents": parsed.model_dump(mode="json"),
                    }
                )
                return result
            except (APIConnectionError, APITimeoutError, InternalServerError) as exc:
                self.ledger.append(
                    self.phase,
                    self.model,
                    type(exc).__name__,
                    0,
                    0,
                    request_id=None,
                    reservation_id=reservation_id,
                )
                self._append_audit(
                    {
                        "started_utc": started_utc,
                        "completed_utc": datetime.now(UTC).isoformat(),
                        "observation_sim_time_s": observation_sim_time_s,
                        "request_kind": request_kind,
                        "model": self.model,
                        "status": type(exc).__name__,
                        "failure_reason": (
                            str(exc)
                            if isinstance(exc, InvalidSupervisorResponseError)
                            else None
                        ),
                        "attempt": attempts,
                        "schema_valid": False,
                    }
                )
                if attempts > self.max_retries:
                    raise
                time.sleep(min(2 ** (attempts - 1), 4))
            except Exception as exc:
                if not usage_recorded:
                    self.ledger.append(
                        self.phase,
                        self.model,
                        type(exc).__name__,
                        input_tokens,
                        output_tokens,
                        cached,
                        getattr(response, "id", None),
                        reservation_id,
                    )
                self._append_audit(
                    {
                        "started_utc": started_utc,
                        "completed_utc": datetime.now(UTC).isoformat(),
                        "observation_sim_time_s": observation_sim_time_s,
                        "request_kind": request_kind,
                        "model": self.model,
                        "status": type(exc).__name__,
                        "attempt": attempts,
                        "schema_valid": False,
                        "payload_sha256": hashlib.sha256(
                            input_json.encode("utf-8")
                        ).hexdigest(),
                        "payload": payload,
                        "response_id": getattr(response, "id", None),
                        "input_tokens": input_tokens,
                        "cached_input_tokens": cached,
                        "output_tokens": output_tokens,
                        "estimated_input_tokens": estimated_input_tokens,
                    }
                )
                raise


class ReplaySupervisor:
    """Strictly replay redacted, recorded live Responses API decisions."""

    def __init__(
        self,
        source: Path,
        audit_path: Path | None = None,
        expected_model: str | None = None,
    ) -> None:
        self.source = source
        self.audit_path = audit_path
        source_bytes = source.read_bytes()
        self.source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        parsed_rows = [
            json.loads(line)
            for line in source_bytes.decode("utf-8").splitlines()
            if line.strip()
        ]
        self.rows = [row for row in parsed_rows if row.get("schema_valid") is True]
        if not self.rows:
            raise ValueError("Replay source contains no schema-valid calls")
        if expected_model is not None:
            unexpected = {
                str(row.get("model"))
                for row in self.rows
                if row.get("model") != expected_model
            }
            if unexpected:
                raise ValueError(
                    f"Replay source contains models other than {expected_model!r}: "
                    f"{sorted(unexpected)!r}"
                )
        self.index = 0

    def decide(
        self,
        payload: dict[str, Any],
        *,
        observation_sim_time_s: int,
        request_kind: str,
    ) -> SupervisorResult:
        if self.index >= len(self.rows):
            raise RuntimeError("Replay exhausted before the simulation ended")
        row = self.rows[self.index]
        input_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        payload_hash = hashlib.sha256(input_json.encode("utf-8")).hexdigest()
        expected = (
            int(row["observation_sim_time_s"]),
            str(row["request_kind"]),
            str(row["payload_sha256"]),
        )
        observed = (observation_sim_time_s, request_kind, payload_hash)
        if observed != expected:
            raise ValueError(
                "Replay request does not match recorded time, kind, or payload"
            )
        self.index += 1
        result = SupervisorResult(
            observation_sim_time_s=observation_sim_time_s,
            request_kind=request_kind,
            model=str(row["model"]),
            response_id=str(row["response_id"]),
            latency_s=float(row["latency_s"]),
            attempts=int(row["attempts"]),
            input_tokens=int(row["input_tokens"]),
            cached_input_tokens=int(row["cached_input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            estimated_input_tokens=int(row.get("estimated_input_tokens", 0)),
            request_application_bytes=int(row["request_application_bytes"]),
            response_application_bytes=int(row["response_application_bytes"]),
            intents=CorridorResponse.model_validate(row["intents"]),
        )
        if self.audit_path is not None:
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "replay_index": self.index - 1,
                            "source": self.source.name,
                            "source_sha256": self.source_sha256,
                            "observation_sim_time_s": observation_sim_time_s,
                            "request_kind": request_kind,
                            "payload_sha256": payload_hash,
                            "response_id": result.response_id,
                        },
                        sort_keys=True,
                    )
                    + "\n"
                )
        return result

    def assert_consumed(self) -> None:
        if self.index != len(self.rows):
            raise RuntimeError(
                f"Replay consumed {self.index} of {len(self.rows)} recorded calls"
            )
