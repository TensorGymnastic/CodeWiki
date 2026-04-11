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
            Pending external review.
            """
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "review.json"

    from codewiki.src.enduser.review import AdversarialReview, JudgeReview, ReviewScoreSet

    monkeypatch.setattr(
        "codewiki.cli.commands.enduser.run_codex_judge",
        lambda document_path, catalog_path, template_id: JudgeReview(
            runner="codex",
            status="pass",
            scores=ReviewScoreSet(
                coverage=4,
                evidence_alignment=5,
                format_compliance=5,
                clarity=4,
            ),
            summary="Judge passed the document.",
            findings=[],
        ),
    )
    monkeypatch.setattr(
        "codewiki.cli.commands.enduser.run_opencode_adversarial",
        lambda document_path, catalog_path, template_id: AdversarialReview(
            runner="opencode",
            status="pass",
            findings=[],
            unsupported_claims=[],
            missing_evidence=[],
            format_attacks=[],
            summary="No adversarial issues found.",
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
    assert payload["judge"]["runner"] == "codex"
    assert payload["adversarial"]["runner"] == "opencode"
    assert payload["publication_decision"]["status"] == "approved"
