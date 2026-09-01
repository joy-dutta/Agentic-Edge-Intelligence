from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class IntentName(StrEnum):
    KEEP_LOCAL_PLAN = "keep_local_plan"
    BIAS_CORRIDOR = "bias_corridor"
    BIAS_CROSS_STREET = "bias_cross_street"
    COORDINATE_OFFSET = "coordinate_offset"
    EMERGENCY_PRIORITY = "emergency_priority"
    REQUEST_FALLBACK = "request_fallback"


class NeighborRequest(StrEnum):
    NONE = "none"
    SEND_QUEUE_SUMMARY = "send_queue_summary"
    PREPARE_PROGRESSION = "prepare_progression"
    YIELD_FOR_EMERGENCY = "yield_for_emergency"


class ReasonCode(StrEnum):
    BALANCED = "balanced"
    CONGESTION = "congestion"
    SPILLBACK = "spillback"
    EMERGENCY = "emergency"
    STALE_DATA = "stale_data"
    UNCERTAINTY = "uncertainty"


class AgentIntent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intersection_id: str
    valid_for_s: Annotated[int, Field(ge=1, le=120)]
    intent: IntentName
    strength: Annotated[int, Field(ge=0, le=3)]
    requested_duration_s: Annotated[int, Field(ge=0, le=120)]
    neighbor_request: NeighborRequest
    reason_code: ReasonCode
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]


class CorridorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intents: Annotated[list[AgentIntent], Field(min_length=1, max_length=8)]


class PeerSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender_id: str
    age_s: Annotated[float, Field(ge=0.0)]
    authenticated: bool
    queue_total: Annotated[float, Field(ge=0.0)]
    occupancy_max: Annotated[float, Field(ge=0.0, le=1.0)]
    emergency_claim: bool = False
    replayed: bool = False
    untrusted_text_present: bool = False


class IntersectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intersection_id: str
    sim_time_s: int
    current_phase: int
    phase_elapsed_s: Annotated[int, Field(ge=0)]
    lane_queues: list[int]
    lane_occupancies: list[float]
    max_wait_s: Annotated[float, Field(ge=0.0)]
    downstream_blocked: bool
    verified_emergency: bool
    emergency_phase: int | None = None
    sensor_complete: bool
    peers: list[PeerSummary]


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    reasons: list[str]
    proposed_unsafe: bool
    blocked_unsafe: bool
    false_block: bool
    fallback_required: bool
