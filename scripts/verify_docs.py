from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def main() -> None:
    checked = 0
    missing: list[str] = []
    for document in sorted(ROOT.rglob("*.md")):
        if any(part in {".git", ".release-venv", ".venv"} for part in document.parts):
            continue
        content = document.read_text(encoding="utf-8")
        for target in LINK.findall(content):
            target = target.strip().split("#", 1)[0]
            if not target or target.startswith(("http://", "https://", "mailto:")):
                continue
            checked += 1
            resolved = (document.parent / target).resolve()
            if not resolved.exists():
                missing.append(
                    f"{document.relative_to(ROOT).as_posix()} -> {target}"
                )
    if missing:
        for item in missing:
            print(f"FAIL: missing documentation target: {item}")
        raise SystemExit(1)
    print(f"Documentation link verification passed: {checked} local links checked.")


if __name__ == "__main__":
    main()

