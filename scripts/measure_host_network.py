from __future__ import annotations

import argparse
import json
import socket
import ssl
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure the unshaped OpenAI host path")
    parser.add_argument("--host", default="api.openai.com")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--repetitions", type=int, default=20)
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/preflight/host_network.json")
    )
    args = parser.parse_args()
    context = ssl.create_default_context()
    rows = []
    for index in range(args.repetitions):
        dns_start = time.perf_counter()
        addresses = socket.getaddrinfo(args.host, args.port, type=socket.SOCK_STREAM)
        dns_s = time.perf_counter() - dns_start
        family, socket_type, protocol, _, address = addresses[0]
        tcp_start = time.perf_counter()
        raw = socket.socket(family, socket_type, protocol)
        raw.settimeout(10)
        raw.connect(address)
        tcp_s = time.perf_counter() - tcp_start
        tls_start = time.perf_counter()
        wrapped = context.wrap_socket(raw, server_hostname=args.host)
        tls_s = time.perf_counter() - tls_start
        cipher = wrapped.cipher()
        tls_version = wrapped.version()
        wrapped.close()
        rows.append(
            {
                "repetition": index,
                "dns_s": dns_s,
                "tcp_connect_s": tcp_s,
                "tls_handshake_s": tls_s,
                "tcp_plus_tls_s": tcp_s + tls_s,
            }
        )
        time.sleep(0.1)
    values = np.asarray([row["tcp_plus_tls_s"] for row in rows])
    result = {
        "measured_utc": datetime.now(UTC).isoformat(),
        "host": args.host,
        "port": args.port,
        "repetitions": len(rows),
        "tls_version": tls_version,
        "cipher": cipher[0] if cipher else None,
        "tcp_plus_tls_p50_s": float(np.quantile(values, 0.50)),
        "tcp_plus_tls_p95_s": float(np.quantile(values, 0.95)),
        "rows": rows,
        "api_requests": 0,
        "credentials_sent": False,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(
        json.dumps(
            {
                "p50_s": result["tcp_plus_tls_p50_s"],
                "p95_s": result["tcp_plus_tls_p95_s"],
                "output": str(output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
