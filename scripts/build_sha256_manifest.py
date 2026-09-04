from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


INCLUDED = (
    "artifacts",
    "data/processed",
    "checkpoints",
    "configs",
    "docker",
    "patches",
    "requirements",
    "src",
    "scripts",
    "tests",
)

TOP_LEVEL = (
    "README.md",
    "CITATION.cff",
    "pyproject.toml",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze evidence and source file hashes")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    output = root / "artifacts" / "manifests" / "sha256_manifest.json"
    files = []
    candidates = [root / value for value in TOP_LEVEL if (root / value).is_file()]
    for relative in INCLUDED:
        directory = root / relative
        if not directory.exists():
            continue
        candidates.extend(item for item in directory.rglob("*") if item.is_file())
    for path in sorted(set(candidates)):
        if path == output or "network_tls" in path.parts:
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    manifest = {
        "created_utc": datetime.now(UTC).isoformat(),
        "algorithm": "SHA-256",
        "files": files,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"files": len(files), "output": str(output)}, indent=2))


if __name__ == "__main__":
    main()
