"""Helpers for reading and writing YAML-first enduser catalogs."""

from __future__ import annotations

from pathlib import Path
from typing import TextIO

import yaml

from codewiki.src.enduser.models import EnduserCatalog


def load_enduser_catalog(path: Path | str) -> EnduserCatalog:
    """Load a catalog from a filesystem path and validate via the Pydantic models."""

    text = Path(path).read_text(encoding="utf-8")
    return load_enduser_catalog_from_string(text)


def load_enduser_catalog_from_string(source: str) -> EnduserCatalog:
    """Load a catalog from a YAML string and return a validated model."""

    parsed = yaml.safe_load(source)
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise ValueError("catalog root must be a mapping")
    return EnduserCatalog.model_validate(parsed)


def load_enduser_catalog_from_stream(stream: TextIO) -> EnduserCatalog:
    """Load a catalog from a text stream."""

    return load_enduser_catalog_from_string(stream.read())


def dump_enduser_catalog(catalog: EnduserCatalog) -> str:
    """Return a canonical YAML representation of the catalog."""

    payload = catalog.model_dump()
    return yaml.safe_dump(payload, sort_keys=True, indent=2)


def save_enduser_catalog(catalog: EnduserCatalog, path: Path | str) -> Path:
    """Write the canonical YAML catalog to `path` and return the path."""

    canonical = dump_enduser_catalog(catalog)
    destination = Path(path)
    destination.write_text(canonical, encoding="utf-8")
    return destination


__all__ = [
    "load_enduser_catalog",
    "load_enduser_catalog_from_string",
    "load_enduser_catalog_from_stream",
    "dump_enduser_catalog",
    "save_enduser_catalog",
]
