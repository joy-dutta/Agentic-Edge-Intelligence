from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NetworkProfile:
    name: str
    rtt_ms: float
    jitter_ms: float
    loss_rate: float
    bandwidth_mbps: float
    outage_s: float = 0.0


@dataclass(frozen=True)
class Transmission:
    sent_at_s: float
    deliver_at_s: float | None
    application_bytes: int
    modeled_transport_bytes: int
    dropped: bool
    reason: str | None


class NetworkEmulator:
    """Deterministic application-level sensitivity emulator.

    This is not a replacement for tc/netem or PCAP. It produces exact application
    byte counts and separately labelled transport-overhead estimates.
    """

    def __init__(self, profile: NetworkProfile, seed: int) -> None:
        self.profile = profile
        self.rng = random.Random(seed)
        self.transmissions: list[Transmission] = []

    @staticmethod
    def encode(payload: Any) -> bytes:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode("utf-8")

    def transmit(
        self,
        payload: Any,
        sent_at_s: float,
        *,
        forced_outage: bool = False,
    ) -> Transmission:
        encoded = self.encode(payload)
        return self.transmit_size(
            len(encoded), sent_at_s, forced_outage=forced_outage
        )

    def transmit_size(
        self,
        application_bytes: int,
        sent_at_s: float,
        *,
        forced_outage: bool = False,
    ) -> Transmission:
        app_bytes = int(application_bytes)
        if app_bytes < 0:
            raise ValueError("application_bytes cannot be negative")
        dropped = forced_outage or self.rng.random() < self.profile.loss_rate
        if dropped:
            transmission = Transmission(
                sent_at_s=sent_at_s,
                deliver_at_s=None,
                application_bytes=app_bytes,
                modeled_transport_bytes=0,
                dropped=True,
                reason="outage" if forced_outage else "packet_loss",
            )
            self.transmissions.append(transmission)
            return transmission

        jitter = self.rng.gauss(0.0, self.profile.jitter_ms)
        propagation_ms = max(0.0, self.profile.rtt_ms / 2.0 + jitter)
        serialization_ms = app_bytes * 8 / max(self.profile.bandwidth_mbps * 1000, 1)
        # TLS/TCP/IP framing is modelled separately until PCAP is available.
        overhead = 97 + 24 * max(1, math.ceil(app_bytes / 1400))
        deliver_at = sent_at_s + (propagation_ms + serialization_ms) / 1000.0
        transmission = Transmission(
            sent_at_s=sent_at_s,
            deliver_at_s=deliver_at,
            application_bytes=app_bytes,
            modeled_transport_bytes=app_bytes + overhead,
            dropped=False,
            reason=None,
        )
        self.transmissions.append(transmission)
        return transmission

    def totals(self) -> dict[str, int]:
        return {
            "messages": len(self.transmissions),
            "dropped": sum(item.dropped for item in self.transmissions),
            "application_bytes": sum(item.application_bytes for item in self.transmissions),
            "modeled_transport_bytes": sum(
                item.modeled_transport_bytes for item in self.transmissions
            ),
        }
