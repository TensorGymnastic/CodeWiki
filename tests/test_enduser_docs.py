import pytest

from codewiki.src.enduser.models import (
    EnduserCatalog,
    EntityRecord,
    EvidenceRecord,
    FieldRecord,
    PageRecord,
    RelationRecord,
    TransactionRecord,
)


def _build_catalog() -> EnduserCatalog:
    return EnduserCatalog(
        entities=[
            EntityRecord(
                id="entity.customer",
                name="Customer",
                description="Customer master record",
            )
        ],
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
            ),
            FieldRecord(
                id="field.customers_edit.last_updated_at",
                name="last_updated_at",
                label="Last Updated At",
                field_type="datetime",
                required=False,
                readonly=True,
            ),
        ],
        transactions=[
            TransactionRecord(
                id="txn.customer_update",
                name="Update Customer",
                goal="Update customer record details",
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
            EvidenceRecord(
                id="ev.network.customer_update",
                evidence_type="network",
                source_ref="PUT /api/customers/:id",
                summary="Network trace for customer update",
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
                relation="contains",
                target="field.customers_edit.last_updated_at",
                evidence_ids=["ev.playwright.page.customers_edit"],
            ),
            RelationRecord(
                source="page.customers_edit",
                relation="participates_in",
                target="txn.customer_update",
                evidence_ids=["ev.playwright.page.customers_edit", "ev.network.customer_update"],
            ),
            RelationRecord(
                source="txn.customer_update",
                relation="updates",
                target="entity.customer",
                evidence_ids=["ev.network.customer_update"],
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


def _build_multi_page_catalog() -> EnduserCatalog:
    catalog = _build_catalog()
    catalog.pages.append(
        PageRecord(
            id="page.customers_search",
            name="Customer Search",
            route="/customers/search",
            screenshot_refs=["screens/customer-search.png"],
        )
    )
    catalog.fields.append(
        FieldRecord(
            id="field.customers_search.customer_status",
            name="customer_status",
            label="Customer Status",
            field_type="select",
            required=False,
            readonly=False,
        )
    )
    catalog.evidence.append(
        EvidenceRecord(
            id="ev.playwright.page.customers_search",
            evidence_type="playwright",
            source_ref="/customers/search",
            summary="Playwright crawl evidence for /customers/search",
        )
    )
    catalog.relations.append(
        RelationRecord(
            source="page.customers_search",
            relation="contains",
            target="field.customers_search.customer_status",
            evidence_ids=["ev.playwright.page.customers_search"],
        )
    )
    return catalog


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
    assert "1. Open the cataloged page scope `Customer Edit`." in document
    assert "Review `Customer Name` as an editable `text` field that is required" in document
    assert "Do not assume any additional page transitions" in document
    assert "| Field | Label | Type | Required | Readonly |" in document
    assert "`ev.screenshot.page.customers_edit`" in document
    assert "`customer_status`" not in document


def test_render_doc_requires_page_selection_for_multi_page_catalogs():
    from codewiki.src.enduser.docs import DEFAULT_ENDUSER_DOC_TEMPLATE, render_enduser_document

    with pytest.raises(ValueError, match="catalog contains multiple pages; select one with --page"):
        render_enduser_document(_build_multi_page_catalog(), template=DEFAULT_ENDUSER_DOC_TEMPLATE)


def test_render_doc_supports_page_scoped_selection():
    from codewiki.src.enduser.docs import DEFAULT_ENDUSER_DOC_TEMPLATE, render_enduser_document

    document = render_enduser_document(
        _build_multi_page_catalog(),
        template=DEFAULT_ENDUSER_DOC_TEMPLATE,
        page_id="page.customers_search",
    )

    assert document.startswith("# Customer Search User Guide")
    assert "`customer_status`" in document
    assert "`customer_name`" not in document
    assert "`ev.playwright.page.customers_search`" in document
    assert "`ev.network.customer_update`" not in document


def test_load_enduser_doc_template_reads_packaged_markdown():
    from codewiki.src.enduser.docs import load_enduser_doc_template

    template = load_enduser_doc_template("page-default")

    assert template.template_id == "page-default"
    assert template.body_template.startswith("# {title}")
    assert "## Purpose" in template.body_template
    assert "## Review Status" in template.body_template


def test_load_enduser_doc_template_reads_packaged_metadata():
    from codewiki.src.enduser.docs import load_enduser_doc_template

    template = load_enduser_doc_template("page-ops-checklist")

    assert template.template_id == "page-ops-checklist"
    assert template.title_template == "{page_name} Operations Checklist"
    assert template.steps_must_be_numbered is True
    assert template.fields_must_be_table is True
    assert template.evidence_requires_ids is True
    assert template.document_kind == "ops-checklist"
    assert template.emphasize_verification is True


def test_ops_checklist_template_changes_rendering_strategy():
    from codewiki.src.enduser.docs import load_enduser_doc_template, render_enduser_document

    document = render_enduser_document(_build_catalog(), template=load_enduser_doc_template("page-ops-checklist"))

    assert document.startswith("# Customer Edit Operations Checklist")
    assert "Use this checklist to verify the cataloged operator-facing behavior" in document
    assert "Treat any uncataloged buttons, results, save actions, or navigation as unsupported" in document
    assert "Verify `Customer Name` as a `text` field that is required, editable." in document
    assert "Checklist draft ready for review." in document


def test_build_scope_includes_direct_page_entities():
    from codewiki.src.enduser.docs import build_enduser_doc_scope

    catalog = EnduserCatalog(
        entities=[
            EntityRecord(
                id="entity.customer",
                name="Customer",
                description="Customer master record",
            )
        ],
        pages=[
            PageRecord(
                id="page.customers_edit",
                name="Customer Edit",
                route="/customers/edit",
                screenshot_refs=[],
            )
        ],
        fields=[],
        transactions=[],
        evidence=[
            EvidenceRecord(
                id="ev.page",
                evidence_type="playwright",
                source_ref="/customers/edit",
                summary="Page evidence",
            )
        ],
        relations=[
            RelationRecord(
                source="entity.customer",
                relation="appears_on",
                target="page.customers_edit",
                evidence_ids=["ev.page"],
            )
        ],
    )

    scope = build_enduser_doc_scope(catalog)

    assert [entity.id for entity in scope.entities] == ["entity.customer"]
    assert scope.relations[0].relation == "appears_on"


def test_render_evidence_lists_only_records_linked_by_each_evidence_item():
    from codewiki.src.enduser.docs import _render_evidence, build_enduser_doc_scope

    catalog = EnduserCatalog(
        entities=[],
        pages=[
            PageRecord(
                id="page.search",
                name="Customer Search",
                route="/customers/search",
                screenshot_refs=[],
            )
        ],
        fields=[
            FieldRecord(
                id="field.search.customer_name",
                name="customer_name",
                label="Customer Name",
                field_type="text",
                required=False,
                readonly=False,
            ),
            FieldRecord(
                id="field.search.customer_status",
                name="customer_status",
                label="Customer Status",
                field_type="select",
                required=False,
                readonly=False,
            ),
        ],
        transactions=[],
        evidence=[
            EvidenceRecord(
                id="ev.name",
                evidence_type="playwright",
                source_ref="/customers/search",
                summary="Customer name evidence",
            ),
            EvidenceRecord(
                id="ev.status",
                evidence_type="playwright",
                source_ref="/customers/search",
                summary="Customer status evidence",
            ),
        ],
        relations=[
            RelationRecord(
                source="page.search",
                relation="contains",
                target="field.search.customer_name",
                evidence_ids=["ev.name"],
            ),
            RelationRecord(
                source="page.search",
                relation="contains",
                target="field.search.customer_status",
                evidence_ids=["ev.status"],
            ),
        ],
    )

    evidence_lines = _render_evidence(build_enduser_doc_scope(catalog))

    assert evidence_lines[0] == (
        "- `ev.name`: Customer name evidence Supports the page scope `Customer Search`, "
        "the page fields `Customer Name`."
    )
    assert evidence_lines[1] == (
        "- `ev.status`: Customer status evidence Supports the page scope `Customer Search`, "
        "the page fields `Customer Status`."
    )


def test_render_doc_does_not_invent_search_behavior_from_field_name():
    from codewiki.src.enduser.docs import DEFAULT_ENDUSER_DOC_TEMPLATE, render_enduser_document

    catalog = EnduserCatalog(
        entities=[],
        pages=[
            PageRecord(
                id="page.search",
                name="Customer Search",
                route="/customers/search",
                screenshot_refs=[],
            )
        ],
        fields=[
            FieldRecord(
                id="field.search.customer_name",
                name="customer_name",
                label="Customer Name",
                field_type="text",
                required=False,
                readonly=False,
            )
        ],
        transactions=[
            TransactionRecord(
                id="txn.search",
                name="Search Customer",
                goal="Search customer records",
            )
        ],
        evidence=[
            EvidenceRecord(
                id="ev.page",
                evidence_type="playwright",
                source_ref="/customers/search",
                summary="Page evidence",
            )
        ],
        relations=[
            RelationRecord(
                source="page.search",
                relation="contains",
                target="field.search.customer_name",
                evidence_ids=["ev.page"],
            ),
            RelationRecord(
                source="page.search",
                relation="participates_in",
                target="txn.search",
                evidence_ids=["ev.page"],
            ),
        ],
    )

    document = render_enduser_document(catalog, template=DEFAULT_ENDUSER_DOC_TEMPLATE)

    assert "narrow the workflow by name" not in document
    assert (
        "Review `Customer Name` as an editable `text` field that is optional for the cataloged "
        "`Search Customer` goal: Search customer records."
    ) in document


def test_load_enduser_doc_template_rejects_unknown_template():
    from codewiki.src.enduser.docs import load_enduser_doc_template

    with pytest.raises(ValueError, match="unknown enduser template"):
        load_enduser_doc_template("missing-template")


def test_render_doc_rejects_missing_template_sections():
    from codewiki.src.enduser.docs import EnduserDocTemplate, render_enduser_document

    with pytest.raises(ValueError, match="missing required sections"):
        render_enduser_document(
            _build_catalog(),
            template=EnduserDocTemplate(
                template_id="broken",
                title_template="Broken",
                body_template="# Broken\n\n## Purpose\nHello.\n\n## Steps\n1. Do thing.\n",
                required_sections=["Purpose", "Steps"],
            ),
        )


def test_validate_rendered_doc_rejects_missing_evidence_ids():
    from codewiki.src.enduser.docs import (
        DEFAULT_ENDUSER_DOC_TEMPLATE,
        render_enduser_document,
        validate_rendered_enduser_document,
    )

    document = render_enduser_document(_build_catalog(), template=DEFAULT_ENDUSER_DOC_TEMPLATE)
    broken_document = document.replace(
        "- `ev.playwright.page.customers_edit`: Playwright crawl evidence for /customers/edit",
        "- Playwright crawl evidence for /customers/edit",
    )

    with pytest.raises(ValueError, match="Evidence section must contain bullet entries with evidence ids"):
        validate_rendered_enduser_document(broken_document, template=DEFAULT_ENDUSER_DOC_TEMPLATE)
