#!/usr/bin/env python3
"""Verify that requirements.txt mirrors the direct runtime dependencies in pyproject.toml."""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


SPECIFIER_SPLIT = re.compile(r"[<>=!~;\[]")


def _normalize(requirement: str) -> str:
    name = SPECIFIER_SPLIT.split(requirement.strip(), maxsplit=1)[0]
    return name.strip().lower().replace("_", "-")


def _load_pyproject_dependencies(repo_root: Path) -> set[str]:
    data = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies = data["project"]["dependencies"]
    return {_normalize(item) for item in dependencies}


def _load_requirements_dependencies(repo_root: Path) -> set[str]:
    requirements_path = repo_root / "requirements.txt"
    requirements: set[str] = set()
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        requirements.add(_normalize(stripped))
    return requirements


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    pyproject_dependencies = _load_pyproject_dependencies(repo_root)
    requirements_dependencies = _load_requirements_dependencies(repo_root)

    missing_from_requirements = sorted(pyproject_dependencies - requirements_dependencies)
    extra_in_requirements = sorted(requirements_dependencies - pyproject_dependencies)

    if not missing_from_requirements and not extra_in_requirements:
        print("Dependency manifests are aligned.")
        return 0

    if missing_from_requirements:
        print("Missing from requirements.txt:")
        for item in missing_from_requirements:
            print(f"  - {item}")

    if extra_in_requirements:
        print("Extra entries in requirements.txt:")
        for item in extra_in_requirements:
            print(f"  - {item}")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
