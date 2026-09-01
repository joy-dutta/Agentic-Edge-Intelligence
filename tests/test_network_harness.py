import json

from scripts.network_harness import encoded, telemetry


def test_network_harness_payload_is_versioned_and_deterministic():
    first = encoded(telemetry(7))
    second = encoded(telemetry(7))
    assert first == second
    decoded = json.loads(first)
    assert decoded["schema"] == "ojcoms.detector.v1"
    assert decoded["sequence"] == 7
    assert len(decoded["intersections"]) == 8
    assert [row["id"] for row in decoded["intersections"]] == [
        f"tls-{index}" for index in range(8)
    ]
