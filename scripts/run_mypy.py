#!/usr/bin/env python3
"""Run the fast local mypy gate for the maintained enduser surfaces."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    command = [
        sys.executable,
        "-m",
        "mypy",
        "--config-file",
        str(repo_root / "pyproject.toml"),
        "--follow-imports=skip",
        "--ignore-missing-imports",
        "codewiki/src/enduser",
        "codewiki/cli/commands/enduser.py",
    ]
    return subprocess.run(command, cwd=str(repo_root), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
