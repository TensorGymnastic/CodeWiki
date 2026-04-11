import json
import textwrap

from click.testing import CliRunner

from codewiki.cli.main import cli


VALID_CATALOG = textwrap.dedent(
    """\
    entities: []
    pages:
      - id: page.customers_edit
        name: Customer Edit
        route: /customers/edit
        screenshot_refs:
          - screens/customer-edit.png
    fields:
      - id: field.customers_edit.customer_name
        name: customer_name
        label: Customer Name
        field_type: text
        required: true
        readonly: false
    transactions: []
    evidence:
      - id: ev.playwright.page.customers_edit
        evidence_type: playwright
        source_ref: /customers/edit
        summary: Playwright crawl evidence for /customers/edit
      - id: ev.screenshot.page.customers_edit
        evidence_type: screenshot
        source_ref: screens/customer-edit.png
        summary: Screenshot for /customers/edit
    relations:
      - source: page.customers_edit
        relation: contains
        target: field.customers_edit.customer_name
        evidence_ids:
          - ev.playwright.page.customers_edit
      - source: page.customers_edit
        relation: validated_by
        target: ev.screenshot.page.customers_edit
        evidence_ids:
          - ev.playwright.page.customers_edit
          - ev.screenshot.page.customers_edit
    """
)


def test_enduser_review_e2e_generates_doc_and_review_artifact(tmp_path, monkeypatch):
    catalog_path = tmp_path / "catalog.yaml"
    document_path = tmp_path / "guide.md"
    review_path = tmp_path / "review.json"
    catalog_path.write_text(VALID_CATALOG, encoding="utf-8")

    calls = []

    class CompletedProcess:
        def __init__(self, stdout: str):
            self.stdout = stdout

    def fake_run(command, input, text, capture_output, check):
        assert text is True
        assert capture_output is True
        assert check is True
        calls.append(command)
        if command == ["codex", "exec"]:
            return CompletedProcess(
                json.dumps(
                    {
                        "runner": "codex",
                        "status": "pass",
                        "scores": {
                            "coverage": 4,
                            "evidence_alignment": 5,
                            "format_compliance": 5,
                            "clarity": 4,
                        },
                        "summary": "Judge passed the document.",
                        "findings": [],
                    }
                )
            )
        if command == ["opencode", "run"]:
            return CompletedProcess(
                json.dumps(
                    {
                        "runner": "opencode",
                        "status": "pass",
                        "findings": [],
                        "unsupported_claims": [],
                        "missing_evidence": [],
                        "format_attacks": [],
                        "summary": "No adversarial issues found.",
                    }
                )
            )
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr("codewiki.src.enduser.review.subprocess.run", fake_run)

    runner = CliRunner()
    render_result = runner.invoke(
        cli,
        ["enduser", "render-doc", str(catalog_path), "--output", str(document_path)],
    )
    assert render_result.exit_code == 0
    assert document_path.exists()

    review_result = runner.invoke(
        cli,
        [
            "enduser",
            "review-doc",
            str(document_path),
            "--catalog",
            str(catalog_path),
            "--output",
            str(review_path),
        ],
    )
    assert review_result.exit_code == 0
    assert calls == [["codex", "exec"], ["opencode", "run"]]

    payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert payload["template_id"] == "page-default"
    assert payload["judge"]["runner"] == "codex"
    assert payload["adversarial"]["runner"] == "opencode"
    assert payload["publication_decision"]["status"] == "approved"
