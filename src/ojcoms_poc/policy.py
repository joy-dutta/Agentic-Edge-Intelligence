from __future__ import annotations

from dataclasses import dataclass

from .models import AgentIntent, IntentName, IntersectionState, PolicyDecision


@dataclass(frozen=True)
class PolicyLimits:
    min_green_s: int = 5
    max_green_s: int = 50
    max_approach_wait_s: int = 180
    max_intent_duration_s: int = 120
    max_peer_age_s: int = 10


class PolicyShield:
    def __init__(self, authorized_ids: set[str], limits: PolicyLimits) -> None:
        self.authorized_ids = authorized_ids
        self.limits = limits

    def evaluate(
        self,
        intent: AgentIntent,
        state: IntersectionState,
        *,
        governance_enabled: bool,
    ) -> PolicyDecision:
        reasons: list[str] = []

        if intent.intersection_id not in self.authorized_ids:
            reasons.append("unauthorized_intersection")
        if intent.intersection_id != state.intersection_id:
            reasons.append("identity_mismatch")
        if intent.valid_for_s > self.limits.max_intent_duration_s:
            reasons.append("intent_ttl_exceeded")
        if intent.requested_duration_s > self.limits.max_green_s:
            reasons.append("maximum_green_exceeded")
        if state.phase_elapsed_s < self.limits.min_green_s and intent.intent not in {
            IntentName.KEEP_LOCAL_PLAN,
            IntentName.REQUEST_FALLBACK,
        }:
            reasons.append("minimum_green_not_met")
        if state.max_wait_s >= self.limits.max_approach_wait_s and intent.intent in {
            IntentName.BIAS_CORRIDOR,
            IntentName.COORDINATE_OFFSET,
        }:
            reasons.append("maximum_approach_wait_risk")
        if state.downstream_blocked and intent.intent in {
            IntentName.BIAS_CORRIDOR,
            IntentName.COORDINATE_OFFSET,
        }:
            reasons.append("downstream_spillback")
        if intent.intent == IntentName.EMERGENCY_PRIORITY and not state.verified_emergency:
            reasons.append("unverified_emergency")
        if not state.sensor_complete and intent.intent not in {
            IntentName.KEEP_LOCAL_PLAN,
            IntentName.REQUEST_FALLBACK,
        }:
            reasons.append("incomplete_sensor_state")
        if any(not peer.authenticated for peer in state.peers) and intent.neighbor_request.value != "none":
            reasons.append("untrusted_peer")
        if any(peer.age_s > self.limits.max_peer_age_s for peer in state.peers) and intent.neighbor_request.value != "none":
            reasons.append("stale_peer")
        if any(peer.replayed for peer in state.peers) and intent.neighbor_request.value != "none":
            reasons.append("replayed_peer")

        proposed_unsafe = bool(reasons)
        accepted = not governance_enabled or not proposed_unsafe
        blocked = governance_enabled and proposed_unsafe
        return PolicyDecision(
            accepted=accepted,
            reasons=reasons,
            proposed_unsafe=proposed_unsafe,
            blocked_unsafe=blocked,
            false_block=False,
            fallback_required=blocked or intent.intent == IntentName.REQUEST_FALLBACK,
        )

