from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

import paho.mqtt.client as mqtt


def encoded(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def client(client_id: str) -> mqtt.Client:
    instance = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    instance.tls_set(ca_certs=os.environ["MQTT_CA"])
    return instance


def write_result(role: str, architecture: str, counters: dict) -> None:
    output = Path(os.environ.get("HARNESS_OUTPUT", "artifacts/network"))
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{role}_{architecture}.json").write_text(
        json.dumps(counters, indent=2, sort_keys=True), encoding="utf-8"
    )


def telemetry(sequence: int) -> dict:
    return {
        "schema": "ojcoms.detector.v1",
        "sequence": sequence,
        "sim_time_s": 25200 + sequence,
        "intersections": [
            {
                "id": f"tls-{index}",
                "phase": sequence % 4,
                "queues": [sequence % 17, 4, 9, 2],
                "occupancies": [0.31, 0.18, 0.62, 0.09],
                "max_wait_s": 12 + sequence % 23,
            }
            for index in range(8)
        ],
    }


def run_simulator(architecture: str, messages: int) -> None:
    ready = threading.Event()
    responses: dict[int, float] = {}
    sent_at: dict[int, float] = {}
    counters = {
        "role": "simulator",
        "architecture": architecture,
        "published_messages": 0,
        "published_application_bytes": 0,
        "received_messages": 0,
        "received_application_bytes": 0,
    }
    instance = client(f"simulator-{architecture}")

    def on_connect(client_, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            raise RuntimeError(f"MQTT connect failed: {reason_code}")
        client_.subscribe(f"v1/action/{architecture}", qos=1)
        ready.set()

    def on_message(_client, _userdata, message):
        payload = json.loads(message.payload)
        sequence = int(payload["sequence"])
        counters["received_messages"] += 1
        counters["received_application_bytes"] += len(message.payload)
        responses[sequence] = time.perf_counter() - sent_at[sequence]

    instance.on_connect = on_connect
    instance.on_message = on_message
    instance.connect(os.environ.get("MQTT_BROKER", "broker"), 8883, 30)
    instance.loop_start()
    if not ready.wait(15):
        raise TimeoutError("Simulator did not connect to MQTT")
    time.sleep(2)
    started = time.perf_counter()
    for sequence in range(messages):
        payload = encoded(telemetry(sequence))
        sent_at[sequence] = time.perf_counter()
        info = instance.publish(f"v1/telemetry/{architecture}", payload, qos=1)
        info.wait_for_publish(10)
        counters["published_messages"] += 1
        counters["published_application_bytes"] += len(payload)
        time.sleep(0.02)
    deadline = time.monotonic() + 60
    while len(responses) < messages and time.monotonic() < deadline:
        time.sleep(0.05)
    stop_payload = encoded({"schema": "ojcoms.control.v1", "command": "stop"})
    instance.publish("v1/control/stop", stop_payload, qos=1).wait_for_publish(10)
    counters["stop_application_bytes"] = len(stop_payload)
    counters["wall_latency_s"] = time.perf_counter() - started
    counters["complete_responses"] = len(responses)
    ordered = sorted(responses.values())
    counters["response_latency_p50_s"] = ordered[len(ordered) // 2] if ordered else None
    counters["response_latency_p95_s"] = (
        ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))] if ordered else None
    )
    instance.loop_stop()
    instance.disconnect()
    write_result("simulator", architecture, counters)
    if len(responses) != messages:
        raise RuntimeError(f"Received {len(responses)} of {messages} action responses")


def run_controller(role: str, architecture: str) -> None:
    active = role == architecture
    stopped = threading.Event()
    ready = threading.Event()
    counters = {
        "role": role,
        "architecture": architecture,
        "active": active,
        "received_messages": 0,
        "received_application_bytes": 0,
        "published_messages": 0,
        "published_application_bytes": 0,
        "action_published_messages": 0,
        "action_published_application_bytes": 0,
        "peer_published_messages": 0,
        "peer_published_application_bytes": 0,
        "peer_received_messages": 0,
        "peer_received_application_bytes": 0,
    }
    instance = client(f"{role}-{architecture}")

    def on_connect(client_, _userdata, _flags, reason_code, _properties):
        if reason_code != 0:
            raise RuntimeError(f"MQTT connect failed: {reason_code}")
        client_.subscribe("v1/control/stop", qos=1)
        if active:
            client_.subscribe(f"v1/telemetry/{architecture}", qos=1)
            if role == "edge":
                client_.subscribe("v1/peer/+", qos=1)
        ready.set()

    def on_message(client_, _userdata, message):
        if message.topic == "v1/control/stop":
            stopped.set()
            return
        if message.topic.startswith("v1/peer/"):
            counters["peer_received_messages"] += 1
            counters["peer_received_application_bytes"] += len(message.payload)
            return
        incoming = json.loads(message.payload)
        counters["received_messages"] += 1
        counters["received_application_bytes"] += len(message.payload)
        sequence = int(incoming["sequence"])
        if role == "edge":
            for index in range(8):
                peer = encoded(
                    {
                        "schema": "ojcoms.peer.v1",
                        "sequence": sequence,
                        "intersection_id": f"tls-{index}",
                        "queue_total": int(sum(incoming["intersections"][index]["queues"])),
                        "authenticated": True,
                    }
                )
                client_.publish(f"v1/peer/{index}", peer, qos=1)
                counters["published_messages"] += 1
                counters["published_application_bytes"] += len(peer)
                counters["peer_published_messages"] += 1
                counters["peer_published_application_bytes"] += len(peer)
        action = encoded(
            {
                "schema": "ojcoms.action.v1",
                "sequence": sequence,
                "architecture": architecture,
                "actions": [
                    {"intersection_id": f"tls-{index}", "phase": sequence % 4}
                    for index in range(8)
                ],
            }
        )
        client_.publish(f"v1/action/{architecture}", action, qos=1)
        counters["published_messages"] += 1
        counters["published_application_bytes"] += len(action)
        counters["action_published_messages"] += 1
        counters["action_published_application_bytes"] += len(action)

    instance.on_connect = on_connect
    instance.on_message = on_message
    instance.connect(os.environ.get("MQTT_BROKER", "broker"), 8883, 30)
    instance.loop_start()
    if not ready.wait(15):
        raise TimeoutError(f"{role} did not connect to MQTT")
    if not stopped.wait(90):
        raise TimeoutError(f"{role} did not receive the stop message")
    time.sleep(1)
    instance.loop_stop()
    instance.disconnect()
    write_result(role, architecture, counters)


def main() -> None:
    parser = argparse.ArgumentParser(description="Versioned MQTT network measurement harness")
    parser.add_argument("role", choices=("simulator", "edge", "cloud"))
    parser.add_argument("--architecture", choices=("edge", "cloud"), required=True)
    parser.add_argument("--messages", type=int, default=100)
    args = parser.parse_args()
    if args.role == "simulator":
        run_simulator(args.architecture, args.messages)
    else:
        run_controller(args.role, args.architecture)


if __name__ == "__main__":
    main()
