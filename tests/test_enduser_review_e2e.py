import json
import textwrap
from pathlib import Path

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
        def __init__(self, stdout: str, stderr: str = ""):
            self.stdout = stdout
            self.stderr = stderr

    def fake_run(command, *args, **kwargs):
        if command == ["git", "rev-parse", "--show-toplevel"]:
            return CompletedProcess(f"{Path.cwd().resolve()}\n")

        input = kwargs["input"]
        text = kwargs["text"]
        capture_output = kwargs["capture_output"]
        check = kwargs["check"]
        cwd = kwargs["cwd"]
        timeout = kwargs["timeout"]

        assert text is True
        assert capture_output is True
        assert check is True
        assert cwd == str(Path.cwd().resolve())
        assert timeout == 120
        calls.append(command)
        if command[:2] == ["codex", "exec"]:
            output_path = Path(command[command.index("--output-last-message") + 1])
            assert command[2] == "--skip-git-repo-check"
            assert "--output-schema" in command
            assert command[-1] == "-"
            schema_path = Path(command[command.index("--output-schema") + 1])
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            if "Perform an adversarial review of the provided markdown document." in input:
                assert schema["additionalProperties"] is False
                assert schema["properties"]["findings"]["items"]["type"] == "string"
                assert schema["properties"]["unsupported_claims"]["items"]["type"] == "string"
                assert schema["properties"]["missing_evidence"]["items"]["type"] == "string"
                assert schema["properties"]["format_attacks"]["items"]["type"] == "string"
                assert "## Repository Context" in input
                assert "execution_model: codex-cli" in input
                assert "## Rewrite Context" in input
                output_path.write_text(
                    json.dumps(
                        {
                            "runner": "codex",
                            "status": "pass",
                            "findings": ["Tighten the purpose statement."],
                            "unsupported_claims": ["Claim about operators is too broad."],
                            "missing_evidence": [],
                            "format_attacks": [],
                            "summary": "One unsupported claim found.",
                        }
                    ),
                    encoding="utf-8",
                )
                return CompletedProcess("")
            if "## Adversarial Review" in input:
                assert schema["required"] == ["document"]
                assert schema["additionalProperties"] is False
                assert f"## Document Path\n```text\n{document_path}" in input
                assert f"## Catalog Path\n```text\n{catalog_path}" in input
                assert "## Rewrite Context" in input
                assert "document_focus:" in input
                assert "page_workflow_context:" in input
                assert "runner: codex" in input
                output_path.write_text(
                    "```json\n"
                    + json.dumps(
                        {
                            "document": (
                                "# Customer Edit User Guide\n\n"
                                "## Purpose\nRevised purpose.\n\n"
                                "## Audience\nOperators and business users.\n\n"
                                "## Preconditions\n- You can access the target page in the product.\n\n"
                                "## Steps\n1. Open `Customer Edit`.\n\n"
                                "## Fields\n| Field | Label | Type | Required | Readonly |\n"
                                "| --- | --- | --- | --- | --- |\n"
                                "| `customer_name` | Customer Name | `text` | yes | no |\n\n"
                                "## Navigation\n- No known navigation targets.\n\n"
                                "## Evidence\n"
                                "- `ev.playwright.page.customers_edit`: Playwright crawl evidence for /customers/edit\n"
                                "- `ev.screenshot.page.customers_edit`: Screenshot for /customers/edit\n\n"
                                "## Review Status\nRevised after adversarial review.\n"
                            )
                        }
                    )
                    + "\n```",
                    encoding="utf-8",
                )
                return CompletedProcess("")
            assert "Review the provided markdown document against the catalog and template contract." in input
            assert schema["required"] == ["runner", "status", "scores", "summary", "findings"]
            assert schema["additionalProperties"] is False
            assert schema["properties"]["scores"]["additionalProperties"] is False
            assert schema["properties"]["findings"]["items"]["type"] == "string"
            assert str(document_path.with_suffix(".final.md")) in input
            assert str(catalog_path) in input
            output_path.write_text(
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
                        "summary": "Judge passed the final draft.",
                        "findings": [],
                    }
                ),
                encoding="utf-8",
            )
            return CompletedProcess("")
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
    assert [call[:2] for call in calls] == [["codex", "exec"], ["codex", "exec"], ["codex", "exec"]]

    payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert payload["template_id"] == "page-default"
    assert payload["final_document_path"].endswith(".final.md")
    assert document_path.with_suffix(".final.md").read_text(encoding="utf-8").startswith("# Customer Edit User Guide")
    assert payload["judge"]["runner"] == "codex"
    assert payload["adversarial"]["runner"] == "codex"
    assert payload["publication_decision"]["status"] == "approved"
