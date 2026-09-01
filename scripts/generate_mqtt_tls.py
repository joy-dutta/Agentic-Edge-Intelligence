from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def run(command: list[str]) -> None:
    subprocess.run(command, check=True, capture_output=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate disposable MQTT test TLS material")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    ca_key = output / "ca.key"
    ca_cert = output / "ca.crt"
    broker_key = output / "broker.key"
    broker_csr = output / "broker.csr"
    broker_cert = output / "broker.crt"
    extensions = output / "broker.ext"
    if ca_cert.exists() and broker_cert.exists() and broker_key.exists():
        return
    run(["openssl", "genrsa", "-out", str(ca_key), "2048"])
    run(
        [
            "openssl",
            "req",
            "-x509",
            "-new",
            "-nodes",
            "-key",
            str(ca_key),
            "-sha256",
            "-days",
            "2",
            "-subj",
            "/CN=OJCOMS-PoC-Test-CA",
            "-out",
            str(ca_cert),
        ]
    )
    run(["openssl", "genrsa", "-out", str(broker_key), "2048"])
    run(
        [
            "openssl",
            "req",
            "-new",
            "-key",
            str(broker_key),
            "-subj",
            "/CN=broker",
            "-out",
            str(broker_csr),
        ]
    )
    extensions.write_text("subjectAltName=DNS:broker\n", encoding="ascii")
    run(
        [
            "openssl",
            "x509",
            "-req",
            "-in",
            str(broker_csr),
            "-CA",
            str(ca_cert),
            "-CAkey",
            str(ca_key),
            "-CAcreateserial",
            "-out",
            str(broker_cert),
            "-days",
            "2",
            "-sha256",
            "-extfile",
            str(extensions),
        ]
    )


if __name__ == "__main__":
    main()
