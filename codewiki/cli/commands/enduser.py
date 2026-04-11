"""Click commands for enduser catalog workflows."""

from __future__ import annotations

from pathlib import Path

import yaml
from click import ClickException, argument, echo, group, option, Path as ClickPath
from pydantic import ValidationError

from codewiki.src.enduser.io import (
    dump_enduser_catalog,
    load_enduser_catalog,
    save_enduser_catalog,
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
