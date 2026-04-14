"""Click commands for enduser catalog workflows."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click import ClickException, argument, echo, group, option, Path as ClickPath
from pydantic import ValidationError

from codewiki.src.enduser.docs import (
    DEFAULT_ENDUSER_DOC_TEMPLATE,
    load_enduser_doc_template,
    render_enduser_document,
    validate_rendered_enduser_document,
)
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
    run_codex_adversarial,
    run_codex_final_draft,
    run_codex_judge,
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
@option(
    "--template",
    "template_id",
    default=DEFAULT_ENDUSER_DOC_TEMPLATE.template_id,
    show_default=True,
    help="Packaged enduser markdown template to render.",
)
@option(
    "--page",
    "page_id",
    help="Render a specific page id from a multi-page catalog.",
)
def render_doc(source: Path, output: Path, template_id: str, page_id: str | None):
    """Render a fixed-format Markdown document from an enduser catalog."""

    try:
        catalog = _load_catalog(source)
        template = load_enduser_doc_template(template_id)
        document = render_enduser_document(catalog, template=template, page_id=page_id)
        validate_rendered_enduser_document(document, template=template)
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
@option(
    "--template",
    "template_id",
    default=DEFAULT_ENDUSER_DOC_TEMPLATE.template_id,
    show_default=True,
    help="Packaged enduser markdown template that the document must satisfy.",
)
def review_doc(source: Path, catalog: Path, output: Path, template_id: str):
    """Run Codex adversarial review, produce a final draft, then judge the final draft."""

    try:
        template = load_enduser_doc_template(template_id)
        _load_catalog(catalog)
        validate_rendered_enduser_document(source.read_text(encoding="utf-8"), template=template)
        adversarial = run_codex_adversarial(source, catalog, template)
        final_document = run_codex_final_draft(
            source,
            catalog,
            template,
            adversarial,
        )
        final_document_path = source.with_suffix(".final.md")
        validate_rendered_enduser_document(final_document, template=template)
        final_document_path.write_text(final_document, encoding="utf-8")
        judge = run_codex_judge(final_document_path, catalog, template)
        artifact = EnduserReviewArtifact(
            document_path=str(source),
            final_document_path=str(final_document_path),
            catalog_path=str(catalog),
            template_id=template.template_id,
            judge=judge,
            adversarial=adversarial,
            publication_decision=PublicationDecision(
                status="rejected" if judge.status == "fail" else "approved",
                reasons=judge.findings if judge.status == "fail" else [],
            ),
        )
        output.write_text(json.dumps(artifact.model_dump(), indent=2), encoding="utf-8")
        echo(f"Review written to {output}")
    except (ValueError, ValidationError, yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ClickException(f"Failed to review enduser document '{source}': {exc}")
