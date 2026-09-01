from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "release_manifest.json"

FORBIDDEN_SUFFIXES = {".jpeg", ".jpg", ".pdf", ".png", ".tex"}
FORBIDDEN_NAMES = {
    "api_contract_gate.json",
    "platform_budget_gate.json",
    "run_with_existing_key.py",
}
FORBIDDEN_NAME_PARTS = {"handoff", "manuscript"}
SKIP_PARTS = {
    ".git",
    ".pytest_cache",
    ".release-venv",
    ".venv",
    "__pycache__",
    "external",
}
SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"OPENAI_API_KEY\s*[=:]\s*['\"]?(?!<|your[_-]|Read-Host|\$|os\.|$)[^\s'\"]{12,}"
    ),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repository_files() -> list[Path]:
    return [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and not any(part in SKIP_PARTS for part in path.parts)
        and not any(part.endswith(".egg-info") for part in path.parts)
    ]


def verify_assets_and_secrets() -> tuple[int, list[str]]:
    checked = 0
    problems: list[str] = []
    for path in repository_files():
        relative = path.relative_to(ROOT).as_posix()
        lower_name = path.name.lower()
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            problems.append(f"forbidden release asset: {relative}")
        if lower_name in FORBIDDEN_NAMES or any(
            part in lower_name for part in FORBIDDEN_NAME_PARTS
        ):
            problems.append(f"forbidden private file: {relative}")
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        checked += 1
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            problems.append(f"potential credential value: {relative}")
    return checked, problems


def verify_manifest() -> tuple[int, list[str]]:
    if not MANIFEST.is_file():
        return 0, ["release manifest is missing"]
    data = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if data.get("algorithm") != "SHA-256" or data.get("schema_version") != 1:
        return 0, ["release manifest metadata is invalid"]
    problems: list[str] = []
    entries = data.get("files", [])
    paths = [entry.get("path") for entry in entries]
    if len(paths) != len(set(paths)):
        problems.append("release manifest contains duplicate paths")
    for entry in entries:
        relative = str(entry["path"])
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"manifest file missing: {relative}")
            continue
        if path.stat().st_size != int(entry["bytes"]):
            problems.append(f"manifest size mismatch: {relative}")
        if sha256(path) != entry["sha256"]:
            problems.append(f"manifest hash mismatch: {relative}")
    return len(entries), problems


def main() -> None:
    text_files, problems = verify_assets_and_secrets()
    manifest_files, manifest_problems = verify_manifest()
    problems.extend(manifest_problems)
    if problems:
        for problem in sorted(set(problems)):
            print(f"FAIL: {problem}")
        raise SystemExit(1)
    print(
        "Release verification passed: "
        f"{manifest_files} manifested files, {text_files} text files scanned, "
        "no credentials or forbidden private/publication assets detected."
    )


if __name__ == "__main__":
    main()
