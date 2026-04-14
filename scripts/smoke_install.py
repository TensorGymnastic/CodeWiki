#!/usr/bin/env python3
"""Install the built wheel into a clean venv and smoke-test the CLI entrypoint."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    dist_dir = repo_root / "dist"
    wheels = sorted(dist_dir.glob("*.whl"))
    if not wheels:
        raise SystemExit("no wheel found under dist/")

    with tempfile.TemporaryDirectory(prefix="codewiki-smoke-") as tmpdir:
        venv_dir = Path(tmpdir) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        python = venv_dir / "bin" / "python"
        subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True)
        subprocess.run([str(python), "-m", "pip", "install", str(wheels[-1])], check=True)
        completed = subprocess.run(
            [str(python), "-m", "codewiki.cli.main", "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        print(completed.stdout)
        if completed.returncode != 0:
            print(completed.stderr, file=sys.stderr)
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
