#!/usr/bin/env python3
"""Run pip-audit only when dependency manifests changed relative to upstream."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


LOCKFILES = ("pyproject.toml", "requirements.txt", "requirements-dev.txt", "poetry.lock", "uv.lock")


def _changed_files(repo_root: Path) -> set[str]:
    diff_commands = [
        ["git", "diff", "--name-only", "@{upstream}...HEAD"],
        ["git", "diff", "--name-only", "HEAD~1..HEAD"],
    ]
    for command in diff_commands:
        completed = subprocess.run(
            command,
            cwd=str(repo_root),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode == 0:
            return {line.strip() for line in completed.stdout.splitlines() if line.strip()}
    return set()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    changed_files = _changed_files(repo_root)
    if not changed_files.intersection(LOCKFILES):
        print("pip-audit skipped: no dependency manifest changes detected.")
        return 0

    requirements_file = repo_root / "requirements.txt"
    command = [sys.executable, "-m", "pip_audit"]
    if requirements_file.exists():
        command.extend(["-r", str(requirements_file)])
    return subprocess.run(command, cwd=str(repo_root), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
