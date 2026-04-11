"""Click commands for enduser catalog workflows."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click import ClickException, argument, echo, group, option, Path as ClickPath
from pydantic import ValidationError

from codewiki.src.enduser.docs import DEFAULT_ENDUSER_DOC_TEMPLATE, render_enduser_document
from codewiki.src.enduser.io import (
    dump_enduser_catalog,
    load_enduser_catalog,
    save_enduser_catalog,
)
from codewiki.src.enduser.playwright import (
    PlaywrightCatalogExtractor,
    load_playwright_crawl,
)
from codewiki.src.enduser.review import (
    EnduserReviewArtifact,
    PublicationDecision,
    run_codex_judge,
    run_opencode_adversarial,
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


@enduser_group.command(name="render-doc")
@argument("source", type=ClickPath(exists=True, dir_okay=False, path_type=Path))
@option(
    "--output",
    "-o",
    type=ClickPath(dir_okay=False, path_type=Path),
    required=True,
    help="Write rendered Markdown to this path.",
)
def render_doc(source: Path, output: Path):
    """Render a fixed-format Markdown document from an enduser catalog."""

    try:
        catalog = _load_catalog(source)
        document = render_enduser_document(catalog, template=DEFAULT_ENDUSER_DOC_TEMPLATE)
        output.write_text(document, encoding="utf-8")
        echo(f"Document written to {output}")
    except (ValueError, ValidationError, yaml.YAMLError) as exc:
        raise ClickException(f"Failed to render enduser document '{source}': {exc}")


@enduser_group.command(name="review-doc")
@argument("source", type=ClickPath(exists=True, dir_okay=False, path_type=Path))
@option(
    "--catalog",
    type=ClickPath(exists=True, dir_okay=False, path_type=Path),
    required=True,
    help="Validated enduser catalog used as review evidence.",
)
@option(
    "--output",
    "-o",
    type=ClickPath(dir_okay=False, path_type=Path),
    required=True,
    help="Write normalized review JSON to this path.",
)
def review_doc(source: Path, catalog: Path, output: Path):
    """Review a rendered enduser document with codex first and opencode second."""

    try:
        _load_catalog(catalog)
        judge = run_codex_judge(source, catalog, DEFAULT_ENDUSER_DOC_TEMPLATE.template_id)
        adversarial = run_opencode_adversarial(source, catalog, DEFAULT_ENDUSER_DOC_TEMPLATE.template_id)
        failed = judge.status == "fail" or adversarial.status == "fail"
        artifact = EnduserReviewArtifact(
            document_path=str(source),
            catalog_path=str(catalog),
            template_id=DEFAULT_ENDUSER_DOC_TEMPLATE.template_id,
            judge=judge,
            adversarial=adversarial,
            publication_decision=PublicationDecision(
                status="rejected" if failed else "approved",
                reasons=judge.findings + adversarial.findings,
            ),
        )
        output.write_text(json.dumps(artifact.model_dump(), indent=2), encoding="utf-8")
        echo(f"Review written to {output}")
    except (ValueError, ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ClickException(f"Failed to review enduser document '{source}': {exc}")
