from __future__ import annotations

import subprocess
from pathlib import Path


REMOTE = "https://github.com/Pi-Star-Lab/RESCO.git"
COMMIT = "f1ed9a174f8de41fc9d8689373b836bc882570dc"


def run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(
        command, cwd=cwd, check=True, text=True, capture_output=True
    )
    return completed.stdout.strip()


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    destination = root / "external" / "RESCO"
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", REMOTE, str(destination)], root)
    remote = run(["git", "remote", "get-url", "origin"], destination)
    if remote.rstrip("/") != REMOTE.rstrip("/"):
        raise RuntimeError(f"Unexpected RESCO origin: {remote}")
    patch = root / "patches" / "resco_v2_deterministic_seed.patch"
    head = run(["git", "rev-parse", "HEAD"], destination)
    reverse = subprocess.run(
        ["git", "apply", "--unidiff-zero", "--check", "--reverse", str(patch)],
        cwd=destination,
        check=False,
        capture_output=True,
    )
    if head == COMMIT and reverse.returncode == 0:
        print(f"RESCO ready at {COMMIT}: {destination}")
        return
    if run(["git", "status", "--porcelain"], destination):
        raise RuntimeError(
            "RESCO has unrecognized local changes; preserve or remove them manually"
        )
    run(["git", "fetch", "origin", COMMIT], destination)
    run(["git", "checkout", "--detach", COMMIT], destination)
    if run(["git", "rev-parse", "HEAD"], destination) != COMMIT:
        raise RuntimeError("RESCO commit pin failed")
    run(["git", "apply", "--unidiff-zero", "--check", str(patch)], destination)
    run(["git", "apply", "--unidiff-zero", str(patch)], destination)
    print(f"RESCO ready at {COMMIT}: {destination}")


if __name__ == "__main__":
    main()
