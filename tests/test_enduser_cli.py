import json
import textwrap

from click.testing import CliRunner

from codewiki.cli.main import cli

VALID_CATALOG = textwrap.dedent(
    """\
    entities:
      - id: entity-one
        name: Entity One
        description: First entity description
    pages:
      - id: page-one
        name: Page One
        route: /page-one
        screenshot_refs: []
    fields:
      - id: field-one
        name: Field One
        label: Field One
        field_type: text
        required: true
        readonly: false
    transactions:
      - id: transaction-one
        name: Transaction One
        goal: Process something
    evidence:
      - id: evidence-one
        evidence_type: code
        source_ref: src/code.py
        summary: Sample evidence
    relations:
      - source: entity-one
        relation: maps-to
        target: transaction-one
        evidence_ids:
          - evidence-one
    """
)

INVALID_CATALOG = textwrap.dedent(
    """\
    entities:
      - id: entity-one
        name: Entity One
        description: First entity description
    pages: []
    fields: []
    transactions:
      - id: transaction-one
        name: Transaction One
        goal: Process something
    evidence:
      - id: evidence-one
        evidence_type: code
        source_ref: src/code.py
        summary: Sample evidence
    relations:
      - source: transaction-one
        relation: links
        target: missing-target
        evidence_ids:
          - missing-evidence
    """
)

MULTI_PAGE_CATALOG = textwrap.dedent(
    """\
    entities: []
    pages:
      - id: page.search
        name: Customer Search
        route: /customers/search
        screenshot_refs: []
      - id: page.edit
        name: Customer Edit
        route: /customers/edit
        screenshot_refs: []
    fields:
      - id: field.search.customer_name
        name: customer_name
        label: Customer Name
        field_type: text
        required: false
        readonly: false
      - id: field.edit.status
        name: status
        label: Status
        field_type: select
        required: true
        readonly: false
    transactions: []
    evidence:
      - id: ev.search
        evidence_type: playwright
        source_ref: /customers/search
        summary: Search page evidence
      - id: ev.edit
        evidence_type: playwright
        source_ref: /customers/edit
        summary: Edit page evidence
    relations:
      - source: page.search
        relation: contains
        target: field.search.customer_name
        evidence_ids:
          - ev.search
      - source: page.edit
        relation: contains
        target: field.edit.status
        evidence_ids:
          - ev.edit
    """
)


def _write_sample(tmp_path, content):
    path = tmp_path / "catalog.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_enduser_validate_success(tmp_path):
    path = _write_sample(tmp_path, VALID_CATALOG)
    runner = CliRunner()
    result = runner.invoke(cli, ["enduser", "validate", str(path)])

    assert result.exit_code == 0
    assert "valid" in result.output.lower()


def test_enduser_validate_failure(tmp_path):
    path = _write_sample(tmp_path, INVALID_CATALOG)
    runner = CliRunner()
    result = runner.invoke(cli, ["enduser", "validate", str(path)])

    assert result.exit_code != 0
    assert (
        "invalid" in result.output.lower()
        or "failed" in result.output.lower()
        or "unknown relation target" in result.output.lower()
    )


def test_enduser_render_doc_writes_markdown(tmp_path):
    path = _write_sample(tmp_path, VALID_CATALOG)
    output_path = tmp_path / "guide.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["enduser", "render-doc", str(path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    document = output_path.read_text(encoding="utf-8")
    assert document.startswith("# ")
    assert "\n## Purpose\n" in document
    assert "\n## Review Status\n" in document


def test_enduser_render_doc_supports_packaged_template_selection(tmp_path):
    path = _write_sample(tmp_path, VALID_CATALOG)
    output_path = tmp_path / "guide.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enduser",
            "render-doc",
            str(path),
            "--template",
            "page-ops-checklist",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "Operations Checklist" in output_path.read_text(encoding="utf-8")


def test_enduser_render_doc_requires_page_for_multi_page_catalog(tmp_path):
    path = _write_sample(tmp_path, MULTI_PAGE_CATALOG)
    output_path = tmp_path / "guide.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["enduser", "render-doc", str(path), "--output", str(output_path)],
    )

    assert result.exit_code != 0
    assert "select one with --page" in result.output


def test_enduser_render_doc_supports_page_selection(tmp_path):
    path = _write_sample(tmp_path, MULTI_PAGE_CATALOG)
    output_path = tmp_path / "guide.md"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["enduser", "render-doc", str(path), "--page", "page.search", "--output", str(output_path)],
    )

    assert result.exit_code == 0
    document = output_path.read_text(encoding="utf-8")
    assert document.startswith("# Customer Search User Guide")
    assert "`customer_name`" in document
    assert "`status`" not in document


def test_enduser_review_doc_writes_review_artifact(tmp_path, monkeypatch):
    catalog_path = _write_sample(tmp_path, VALID_CATALOG)
    doc_path = tmp_path / "guide.md"
    doc_path.write_text(
        textwrap.dedent(
            """\
            # Page One User Guide

            ## Purpose
            Explain the page.

            ## Audience
            Operators.

            ## Preconditions
            - Access granted.

            ## Steps
            1. Open `Page One`.

            ## Fields
            | Field | Label | Type | Required | Readonly |
            | --- | --- | --- | --- | --- |
            | `field_one` | Field One | `text` | yes | no |

            ## Navigation
            - No known navigation targets.

            ## Evidence
            - `evidence-one`: Sample evidence

            ## Review Status
            Catalog-scoped draft ready for review.
            """
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "review.json"

    from codewiki.src.enduser.review import AdversarialReview, JudgeReview, ReviewScoreSet

    monkeypatch.setattr(
        "codewiki.cli.commands.enduser.run_codex_adversarial",
        lambda document_path, catalog_path, template: AdversarialReview(
            runner="codex",
            status="pass",
            findings=["Tighten the purpose statement."],
            unsupported_claims=["Claim about operators is too broad."],
            missing_evidence=[],
            format_attacks=[],
            summary="One unsupported claim found.",
        ),
    )
    monkeypatch.setattr(
        "codewiki.cli.commands.enduser.run_codex_final_draft",
        lambda document_path, catalog_path, template, adversarial_review: (
            "# Page One User Guide\n\n"
            "## Purpose\nRevised purpose.\n\n"
            "## Audience\nOperators.\n\n"
            "## Preconditions\n- Access granted.\n\n"
            "## Steps\n1. Open `Page One`.\n\n"
            "## Fields\n| Field | Label | Type | Required | Readonly |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| `field_one` | Field One | `text` | yes | no |\n\n"
            "## Navigation\n- No known navigation targets.\n\n"
            "## Evidence\n- `evidence-one`: Sample evidence\n\n"
            "## Review Status\nRevised after adversarial review.\n"
        ),
    )
    monkeypatch.setattr(
        "codewiki.cli.commands.enduser.run_codex_judge",
        lambda document_path, catalog_path, template: JudgeReview(
            runner="codex",
            status="pass",
            scores=ReviewScoreSet(
                coverage=4,
                evidence_alignment=5,
                format_compliance=5,
                clarity=4,
            ),
            summary="Judge passed the final draft.",
            findings=[],
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enduser",
            "review-doc",
            str(doc_path),
            "--catalog",
            str(catalog_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["final_document_path"].endswith(".final.md")
    assert doc_path.with_suffix(".final.md").exists()
    assert payload["judge"]["runner"] == "codex"
    assert payload["adversarial"]["runner"] == "codex"
    assert payload["publication_decision"]["status"] == "approved"


def test_enduser_review_doc_rejects_invalid_markdown_before_runner(tmp_path, monkeypatch):
    catalog_path = _write_sample(tmp_path, VALID_CATALOG)
    doc_path = tmp_path / "guide.md"
    doc_path.write_text("# Broken\n\n## Purpose\nNo evidence block\n", encoding="utf-8")
    output_path = tmp_path / "review.json"

    monkeypatch.setattr(
        "codewiki.cli.commands.enduser.run_codex_adversarial",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("runner should not execute")
        ),
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "enduser",
            "review-doc",
            str(doc_path),
            "--catalog",
            str(catalog_path),
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code != 0
    assert "missing required sections" in result.output.lower()
