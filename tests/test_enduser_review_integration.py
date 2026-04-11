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
def test_enduser_review_with_real_codex_and_opencode(tmp_path):
    if os.environ.get("ENDUSER_ENABLE_REAL_REVIEW_TEST") != "1":
        pytest.skip("set ENDUSER_ENABLE_REAL_REVIEW_TEST=1 to run real review integration")
    if shutil.which("codex") is None:
        pytest.skip("codex binary is not available")
    if shutil.which("opencode") is None:
        pytest.skip("opencode binary is not available")

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
    assert payload["judge"]["runner"] == "codex"
    assert payload["adversarial"]["runner"] == "opencode"
    assert payload["publication_decision"]["status"] in {"approved", "rejected"}
