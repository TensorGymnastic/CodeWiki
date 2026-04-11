import textwrap

import pytest
from pydantic import ValidationError

from codewiki.src.enduser.io import (
    dump_enduser_catalog,
    load_enduser_catalog,
    load_enduser_catalog_from_string,
)


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

INVALID_RELATIONS = textwrap.dedent(
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


def test_catalog_round_trip(tmp_path):
    path = tmp_path / "catalog.yaml"
    path.write_text(VALID_CATALOG, encoding="utf-8")

    catalog = load_enduser_catalog(path)
    canonical = dump_enduser_catalog(catalog)
    reloaded = load_enduser_catalog_from_string(canonical)

    assert catalog.model_dump() == reloaded.model_dump()


def test_validation_rejects_invalid_relations():
    with pytest.raises(ValidationError):
        load_enduser_catalog_from_string(INVALID_RELATIONS)
