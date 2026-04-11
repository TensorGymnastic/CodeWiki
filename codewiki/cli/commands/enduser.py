"""Click commands for enduser catalog workflows."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click import ClickException, argument, echo, group, option, Path as ClickPath
from pydantic import ValidationError

from codewiki.src.enduser.io import (
    dump_enduser_catalog,
    load_enduser_catalog,
    save_enduser_catalog,
)
from codewiki.src.enduser.playwright import (
    PlaywrightCatalogExtractor,
    load_playwright_crawl,
)


@group(name="enduser")
def enduser_group():
    """Commands for validating and formatting enduser catalogs."""


def _load_catalog(path: Path):
    try:
        return load_enduser_catalog(path)
    except (ValidationError, ValueError, yaml.YAMLError) as exc:
        raise ClickException(f"Failed to load catalog '{path}': {exc}")


@enduser_group.command(name="validate")
@argument("path", type=ClickPath(exists=True, dir_okay=False, path_type=Path))
def validate(path: Path):
    """Validate an enduser catalog YAML file."""

    _load_catalog(path)
    echo(f"Catalog '{path}' is valid.")


@enduser_group.command(name="format")
@argument("source", type=ClickPath(exists=True, dir_okay=False, path_type=Path))
@option(
    "--output",
    "-o",
    type=ClickPath(dir_okay=False, path_type=Path),
    help="Write canonical YAML to this path instead of stdout.",
)
def format(source: Path, output: Path | None):
    """Format an enduser catalog into canonical YAML."""

    catalog = _load_catalog(source)
    canonical = dump_enduser_catalog(catalog)
    if output:
        save_enduser_catalog(catalog, output)
        echo(f"Catalog written to {output}")
    else:
        echo(canonical, nl=False)


@enduser_group.command(name="extract-playwright")
@argument("source", type=ClickPath(exists=True, dir_okay=False, path_type=Path))
@option(
    "--output",
    "-o",
    type=ClickPath(dir_okay=False, path_type=Path),
    required=True,
    help="Write extracted catalog YAML to this path.",
)
def extract_playwright(source: Path, output: Path):
    """Extract page, field, and navigation records from saved Playwright crawl JSON."""

    try:
        crawl = load_playwright_crawl(source)
        catalog = PlaywrightCatalogExtractor().extract(crawl)
        save_enduser_catalog(catalog, output)
        echo(f"Catalog written to {output}")
    except (ValueError, ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ClickException(f"Failed to extract Playwright crawl '{source}': {exc}")
