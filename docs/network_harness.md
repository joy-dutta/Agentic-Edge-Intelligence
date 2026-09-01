# Network And Packet-Capture Harness

The Docker Compose harness is a controlled communication calibration, not a field
measurement. It places the simulator/controller, edge agent, cloud controller,
MQTT broker, and packet capture in separate processes and network namespaces.
MQTT messages use versioned JSON and TLS 1.3. Edge and cloud egress are shaped with
`tc netem`; the broker namespace is captured with `tcpdump`. Declared RTT,
jitter, and packet loss are divided across both endpoint egress paths.

Run it under Linux or WSL2 with Docker Compose:

```bash
ARCHITECTURE=edge docker compose up --build -d
docker wait "$(docker compose ps -q simulator-controller)"
docker compose stop pcap
python scripts/reconcile_pcap.py --architecture edge
docker compose down
```

Repeat with `ARCHITECTURE=cloud`, moving the first PCAP and result files to a
distinct architecture-labelled directory before the second run. For N3 edge
sensitivity, override `EDGE_DELAY_MS=100`, `EDGE_JITTER_MS=25`,
`EDGE_LOSS_PERCENT=1`, and `EDGE_RATE_MBIT=5` on both endpoint services. These
half-path values produce the declared 200 ms nominal RTT and 2 percent aggregate
loss sensitivity.

Application counters must match exactly between publishers and subscribers. The
captured transport-to-application byte ratio must lie in `[1.0, 3.0]`; this broad
predeclared tolerance covers Ethernet/IP/TCP/MQTT/TLS framing, acknowledgements,
and retransmissions. Both endpoint application bytes and PCAP transport bytes are
reported, so serialized JSON size is not presented as measured wire traffic.

The test CA and private keys are disposable, expire after two days, live only
under ignored `artifacts/network_tls`, and are excluded from the Docker context.
The broker certificate mount is writable only so the official Mosquitto entrypoint
can assign its private key to the unprivileged broker user; endpoint containers
receive the same material read-only.
