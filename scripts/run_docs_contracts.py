#!/usr/bin/env python3
"""Run lightweight docs/contract checks when the repository exposes them."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    docs_roots = [repo_root / "docs", repo_root / "README.md"]
    if not any(path.exists() for path in docs_roots):
        print("docs/contract check skipped: no docs surface detected.")
        return 0

    # Keep this light until the repo has a dedicated docs build system.
    command = [sys.executable, "-m", "compileall", "codewiki"]
    return subprocess.run(command, cwd=str(repo_root), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
