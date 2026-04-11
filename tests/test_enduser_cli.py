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
