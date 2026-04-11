import json

from codewiki.src.enduser.playwright import (
    PlaywrightCatalogExtractor,
    load_playwright_crawl,
)


def test_extractor_builds_catalog_from_playwright_crawl(tmp_path):
    crawl_path = tmp_path / "crawl.json"
    crawl_path.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "route": "/customers/edit",
                        "title": "Customer Edit",
                        "screenshot_path": "screens/customer-edit.png",
                        "network_requests": [
                            {
                                "method": "POST",
                                "url": "/api/customers/123",
                                "resource_type": "fetch",
                            }
                        ],
                        "fields": [
                            {
                                "name": "customer_name",
                                "label": "Customer Name",
                                "role": "textbox",
                                "required": True,
                            },
                            {
                                "name": "status",
                                "label": "Status",
                                "role": "combobox",
                            },
                        ],
                        "actions": [
                            {
                                "name": "save",
                                "label": "Save",
                                "role": "button",
                                "target_route": "/customers/view",
                            }
                        ],
                    },
                    {
                        "route": "/customers/view",
                        "title": "Customer View",
                        "fields": [],
                        "actions": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    crawl = load_playwright_crawl(crawl_path)
    catalog = PlaywrightCatalogExtractor().extract(crawl)

    page_ids = {page.id for page in catalog.pages}
    field_ids = {field.id for field in catalog.fields}
    evidence_ids = {evidence.id for evidence in catalog.evidence}
    relations = {(rel.source, rel.relation, rel.target) for rel in catalog.relations}

    assert "page.customers_edit" in page_ids
    assert "page.customers_view" in page_ids
    assert "field.customers_edit.customer_name" in field_ids
    assert "field.customers_edit.status" in field_ids
    assert "ev.playwright.page.customers_edit" in evidence_ids
    assert "ev.screenshot.page.customers_edit" in evidence_ids
    assert "ev.network.page.customers_edit.1" in evidence_ids
    assert ("page.customers_edit", "contains", "field.customers_edit.customer_name") in relations
    assert ("page.customers_edit", "contains", "field.customers_edit.status") in relations
    assert ("page.customers_edit", "navigates_to", "page.customers_view") in relations
    assert ("page.customers_edit", "validated_by", "ev.screenshot.page.customers_edit") in relations
    assert ("page.customers_edit", "invokes", "ev.network.page.customers_edit.1") in relations

    customer_name = next(field for field in catalog.fields if field.id == "field.customers_edit.customer_name")
    status = next(field for field in catalog.fields if field.id == "field.customers_edit.status")
    customer_edit = next(page for page in catalog.pages if page.id == "page.customers_edit")

    assert customer_name.field_type == "text"
    assert status.field_type == "select"
    assert customer_edit.screenshot_refs == ["screens/customer-edit.png"]

    screenshot_evidence = next(
        item for item in catalog.evidence if item.id == "ev.screenshot.page.customers_edit"
    )
    network_evidence = next(
        item for item in catalog.evidence if item.id == "ev.network.page.customers_edit.1"
    )

    assert screenshot_evidence.evidence_type == "screenshot"
    assert screenshot_evidence.source_ref == "screens/customer-edit.png"
    assert network_evidence.evidence_type == "network"
    assert network_evidence.source_ref == "POST /api/customers/123"

    screenshot_relation = next(
        item
        for item in catalog.relations
        if item.relation == "validated_by" and item.target == "ev.screenshot.page.customers_edit"
    )
    network_relation = next(
        item
        for item in catalog.relations
        if item.relation == "invokes" and item.target == "ev.network.page.customers_edit.1"
    )

    assert screenshot_relation.evidence_ids == [
        "ev.playwright.page.customers_edit",
        "ev.screenshot.page.customers_edit",
    ]
    assert network_relation.evidence_ids == [
        "ev.playwright.page.customers_edit",
        "ev.network.page.customers_edit.1",
    ]


def test_extractor_ignores_transitions_to_unknown_routes():
    crawl = load_playwright_crawl(
        {
            "pages": [
                {
                    "route": "/customers/edit",
                    "title": "Customer Edit",
                    "fields": [],
                    "actions": [
                        {
                            "name": "save",
                            "label": "Save",
                            "role": "button",
                            "target_route": "/customers/missing",
                        }
                    ],
                }
            ]
        }
    )

    catalog = PlaywrightCatalogExtractor().extract(crawl)

    assert {relation.relation for relation in catalog.relations} == set()
