from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "configs" / "release_manifest.json"

PUBLIC_ROOTS = (
    ".github",
    "artifacts",
    "checkpoints",
    "configs",
    "data",
    "docs",
    "docker",
    "network",
    "patches",
    "requirements",
    "scenarios",
    "scripts",
    "src",
    "tests",
)

TOP_LEVEL = (
    ".dockerignore",
    ".env.example",
    ".gitattributes",
    ".gitignore",
    "CITATION.cff",
    "LICENSE",
    "README.md",
    "pyproject.toml",
)

EXCLUDED = {
    "configs/api_contract_gate.json",
    "configs/platform_budget_gate.json",
    "configs/release_manifest.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def public_files() -> list[Path]:
    if (ROOT / ".git").exists():
        completed = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        candidates = [
            ROOT / value.decode("utf-8")
            for value in completed.stdout.split(b"\0")
            if value
        ]
    else:
        candidates = [ROOT / name for name in TOP_LEVEL if (ROOT / name).is_file()]
        for relative in PUBLIC_ROOTS:
            directory = ROOT / relative
            if directory.exists():
                candidates.extend(path for path in directory.rglob("*") if path.is_file())
    output: list[Path] = []
    for path in sorted(set(candidates)):
        relative = path.relative_to(ROOT).as_posix()
        if (
            relative in EXCLUDED
            or "__pycache__" in path.parts
            or any(part.endswith(".egg-info") for part in path.parts)
        ):
            continue
        output.append(path)
    return output


def main() -> None:
    files = [
        {
            "path": path.relative_to(ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in public_files()
    ]
    manifest = {
        "schema_version": 1,
        "created_utc": datetime.now(UTC).isoformat(),
        "algorithm": "SHA-256",
        "files": files,
    }
    OUTPUT.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"files": len(files), "output": str(OUTPUT)}, indent=2))


if __name__ == "__main__":
    main()
