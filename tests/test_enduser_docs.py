import pytest

from codewiki.src.enduser.models import (
    EnduserCatalog,
    EvidenceRecord,
    FieldRecord,
    PageRecord,
    RelationRecord,
)


def _build_catalog() -> EnduserCatalog:
    return EnduserCatalog(
        pages=[
            PageRecord(
                id="page.customers_edit",
                name="Customer Edit",
                route="/customers/edit",
                screenshot_refs=["screens/customer-edit.png"],
            )
        ],
        fields=[
            FieldRecord(
                id="field.customers_edit.customer_name",
                name="customer_name",
                label="Customer Name",
                field_type="text",
                required=True,
                readonly=False,
            )
        ],
        evidence=[
            EvidenceRecord(
                id="ev.playwright.page.customers_edit",
                evidence_type="playwright",
                source_ref="/customers/edit",
                summary="Playwright crawl evidence for /customers/edit",
            ),
            EvidenceRecord(
                id="ev.screenshot.page.customers_edit",
                evidence_type="screenshot",
                source_ref="screens/customer-edit.png",
                summary="Screenshot for /customers/edit",
            ),
        ],
        relations=[
            RelationRecord(
                source="page.customers_edit",
                relation="contains",
                target="field.customers_edit.customer_name",
                evidence_ids=["ev.playwright.page.customers_edit"],
            ),
            RelationRecord(
                source="page.customers_edit",
                relation="validated_by",
                target="ev.screenshot.page.customers_edit",
                evidence_ids=[
                    "ev.playwright.page.customers_edit",
                    "ev.screenshot.page.customers_edit",
                ],
            ),
        ],
    )


def test_render_doc_produces_required_sections():
    from codewiki.src.enduser.docs import DEFAULT_ENDUSER_DOC_TEMPLATE, render_enduser_document

    document = render_enduser_document(_build_catalog(), template=DEFAULT_ENDUSER_DOC_TEMPLATE)

    assert document.startswith("# ")
    assert "\n## Purpose\n" in document
    assert "\n## Audience\n" in document
    assert "\n## Preconditions\n" in document
    assert "\n## Steps\n" in document
    assert "\n## Fields\n" in document
    assert "\n## Navigation\n" in document
    assert "\n## Evidence\n" in document
    assert "\n## Review Status\n" in document
    assert "1. Open `Customer Edit`" in document
    assert "| Field | Label | Type | Required | Readonly |" in document
    assert "`ev.screenshot.page.customers_edit`" in document


def test_render_doc_rejects_missing_template_sections():
    from codewiki.src.enduser.docs import EnduserDocTemplate, render_enduser_document

    with pytest.raises(ValueError, match="missing required sections"):
        render_enduser_document(
            _build_catalog(),
            template=EnduserDocTemplate(
                template_id="broken",
                title_template="Broken",
                required_sections=["Purpose", "Steps"],
            ),
        )
