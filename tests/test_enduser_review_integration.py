import json
import os
import shutil
import textwrap

import pytest
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


@pytest.mark.integration
def test_enduser_review_with_real_codex_only(tmp_path):
    if os.environ.get("ENDUSER_ENABLE_REAL_REVIEW_TEST") != "1":
        pytest.skip("set ENDUSER_ENABLE_REAL_REVIEW_TEST=1 to run real review integration")
    if shutil.which("codex") is None:
        pytest.skip("codex binary is not available")
    catalog_path = tmp_path / "catalog.yaml"
    document_path = tmp_path / "guide.md"
    review_path = tmp_path / "review.json"
    catalog_path.write_text(VALID_CATALOG, encoding="utf-8")

    runner = CliRunner()
    render_result = runner.invoke(
        cli,
        ["enduser", "render-doc", str(catalog_path), "--output", str(document_path)],
    )
    assert render_result.exit_code == 0

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

    payload = json.loads(review_path.read_text(encoding="utf-8"))
    assert payload["final_document_path"].endswith(".final.md")
    assert payload["judge"]["runner"] == "codex"
    assert payload["adversarial"]["runner"] == "codex"
    assert payload["publication_decision"]["status"] in {"approved", "rejected"}


def test_enduser_review_with_fake_binaries_on_path(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    catalog_path = tmp_path / "catalog.yaml"
    document_path = tmp_path / "guide.md"
    review_path = tmp_path / "review.json"
    review_calls_path = tmp_path / "review-calls.jsonl"
    catalog_path.write_text(VALID_CATALOG, encoding="utf-8")

    codex_script = textwrap.dedent(
        f"""\
        #!/usr/bin/env python3
        import json
        import sys
        from pathlib import Path

        prompt = sys.stdin.read()
        Path({str(review_calls_path)!r}).open("a", encoding="utf-8").write(
            json.dumps({{"runner": "codex", "argv": sys.argv[1:], "prompt": prompt}}) + "\\n"
        )
        output_path = None
        if "--output-last-message" in sys.argv:
            output_path = Path(sys.argv[sys.argv.index("--output-last-message") + 1])
        if "Perform an adversarial review of the provided markdown document." in prompt:
            output_path.write_text(json.dumps({{
                "runner": "codex",
                "status": "pass",
                "findings": ["Tighten the purpose statement."],
                "unsupported_claims": ["Claim about operators is too broad."],
                "missing_evidence": [],
                "format_attacks": [],
                "summary": "One unsupported claim found."
            }}), encoding="utf-8")
        elif "## Adversarial Review" in prompt:
            output_path.write_text("```json\\n" + json.dumps({{
                "document": "# Customer Edit User Guide\\n\\n## Purpose\\nRevised purpose.\\n\\n## Audience\\nOperators and business users.\\n\\n## Preconditions\\n- You can access the target page in the product.\\n\\n## Steps\\n1. Open `Customer Edit`.\\n\\n## Fields\\n| Field | Label | Type | Required | Readonly |\\n| --- | --- | --- | --- | --- |\\n| `customer_name` | Customer Name | `text` | yes | no |\\n\\n## Navigation\\n- No known navigation targets.\\n\\n## Evidence\\n- `ev.playwright.page.customers_edit`: Playwright crawl evidence for /customers/edit\\n- `ev.screenshot.page.customers_edit`: Screenshot for /customers/edit\\n\\n## Review Status\\nRevised after adversarial review.\\n"
            }}) + "\\n```", encoding="utf-8")
        else:
            output_path.write_text(json.dumps({{
                "runner": "codex",
                "status": "pass",
                "scores": {{
                    "coverage": 4,
                    "evidence_alignment": 5,
                    "format_compliance": 5,
                    "clarity": 4
                }},
                "summary": "Judge passed the final draft.",
                "findings": []
            }}), encoding="utf-8")
        """
    )
    codex_path = bin_dir / "codex"
    codex_path.write_text(codex_script, encoding="utf-8")
    codex_path.chmod(0o755)

    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ['PATH']}")

    runner = CliRunner()
    render_result = runner.invoke(
        cli,
        ["enduser", "render-doc", str(catalog_path), "--output", str(document_path)],
    )
    assert render_result.exit_code == 0

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

    payload = json.loads(review_path.read_text(encoding="utf-8"))
    final_document_path = document_path.with_suffix(".final.md")
    assert payload["final_document_path"] == str(final_document_path)
    assert final_document_path.exists()

    calls = [
        json.loads(line)
        for line in review_calls_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert [call["runner"] for call in calls] == ["codex", "codex", "codex"]
    assert calls[0]["argv"][:2] == ["exec", "--skip-git-repo-check"]
    assert "--output-schema" in calls[0]["argv"]
    assert "--output-last-message" in calls[0]["argv"]
    assert calls[1]["argv"][:2] == ["exec", "--skip-git-repo-check"]
    assert "--output-schema" in calls[1]["argv"]
    assert "--output-last-message" in calls[1]["argv"]
    assert calls[2]["argv"][:2] == ["exec", "--skip-git-repo-check"]
    assert "--output-schema" in calls[2]["argv"]
    assert "--output-last-message" in calls[2]["argv"]
    assert "Perform an adversarial review of the provided markdown document." in calls[0]["prompt"]
    assert str(document_path) in calls[1]["prompt"]
    assert "## Adversarial Review" in calls[1]["prompt"]
    assert "runner: codex" in calls[1]["prompt"]
    assert str(final_document_path) in calls[2]["prompt"]
