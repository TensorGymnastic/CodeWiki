from pydantic import ValidationError

from codewiki.src.enduser.models import (
    EnduserCatalog,
    EntityRecord,
    EvidenceRecord,
    FieldRecord,
    PageRecord,
    RelationRecord,
    TransactionRecord,
)


def test_catalog_accepts_cross_linked_records():
    catalog = EnduserCatalog(
        entities=[
            EntityRecord(
                id="entity.customer",
                name="Customer",
                description="Customer business object",
            )
        ],
        pages=[
            PageRecord(
                id="page.customer_edit",
                name="Customer Edit",
                route="/customers/{id}/edit",
            )
        ],
        fields=[
            FieldRecord(
                id="field.customer.name",
                name="Customer Name",
                label="Customer Name",
                field_type="text",
            )
        ],
        transactions=[
            TransactionRecord(
                id="txn.customer.update",
                name="Update Customer",
                goal="Edit and save a customer record",
            )
        ],
        evidence=[
            EvidenceRecord(
                id="ev.code.route.customer_edit",
                evidence_type="code",
                source_ref="src/routes/customer.py:42",
                summary="Customer edit route definition",
            )
        ],
        relations=[
            RelationRecord(
                source="entity.customer",
                relation="appears_on",
                target="page.customer_edit",
                evidence_ids=["ev.code.route.customer_edit"],
            ),
            RelationRecord(
                source="page.customer_edit",
                relation="contains",
                target="field.customer.name",
                evidence_ids=["ev.code.route.customer_edit"],
            ),
            RelationRecord(
                source="txn.customer.update",
                relation="starts_on",
                target="page.customer_edit",
                evidence_ids=["ev.code.route.customer_edit"],
            ),
        ],
    )

    assert catalog.index_ids()["entity.customer"] == "entity"
    assert catalog.index_ids()["page.customer_edit"] == "page"
    assert len(catalog.relations) == 3


def test_catalog_rejects_relation_to_unknown_target():
    try:
        EnduserCatalog(
            entities=[
                EntityRecord(
                    id="entity.customer",
                    name="Customer",
                    description="Customer business object",
                )
            ],
            relations=[
                RelationRecord(
                    source="entity.customer",
                    relation="appears_on",
                    target="page.missing",
                )
            ],
        )
    except ValidationError as exc:
        assert "unknown relation target" in str(exc)
    else:
        raise AssertionError("Expected validation error for missing relation target")


def test_field_requires_label_and_type():
    try:
        FieldRecord(
            id="field.customer.name",
            name="Customer Name",
            label="",
            field_type="",
        )
    except ValidationError as exc:
        assert "label" in str(exc)
        assert "field_type" in str(exc)
    else:
        raise AssertionError("Expected validation error for invalid field metadata")
