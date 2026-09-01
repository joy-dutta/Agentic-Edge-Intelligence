from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path


PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(
        r"OPENAI_API_KEY\s*[=:]\s*['\"]?(?!<|your[_-]|\$\{|$)[^\s'\"]{12,}"
    ),
)


def tracked_files(root: Path) -> set[Path]:
    completed = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return {root / value for value in completed.stdout.splitlines() if value.strip()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan repository paths without echoing matches")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    root = args.root.resolve()
    candidates = tracked_files(root)
    for relative in ("artifacts", "data/processed", "checkpoints"):
        directory = root / relative
        if directory.exists():
            candidates.update(path for path in directory.rglob("*") if path.is_file())
    findings = []
    for path in sorted(candidates):
        if "network_tls" in path.parts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(pattern.search(content) for pattern in PATTERNS):
            findings.append(path.relative_to(root).as_posix())
    if findings:
        for path in findings:
            print(f"potential secret: {path}")
        raise SystemExit(1)
    print(f"Secret scan passed for {len(candidates)} files")


if __name__ == "__main__":
    main()
