"""Render fixed-format enduser documentation from validated catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
import re
from typing import TypeVar, cast

from pydantic import BaseModel, Field, field_validator
import yaml

from codewiki.src.enduser.models import (
    EnduserCatalog,
    EntityRecord,
    EvidenceRecord,
    FieldRecord,
    PageRecord,
    RelationRecord,
    TransactionRecord,
)


REQUIRED_DOC_SECTIONS = [
    "Purpose",
    "Audience",
    "Preconditions",
    "Steps",
    "Fields",
    "Navigation",
    "Evidence",
    "Review Status",
]


class EnduserDocTemplate(BaseModel):
    template_id: str = Field(min_length=1)
    title_template: str = Field(min_length=1)
    body_template: str = Field(min_length=1)
    required_sections: list[str] = Field(default_factory=lambda: list(REQUIRED_DOC_SECTIONS))
    steps_must_be_numbered: bool = True
    fields_must_be_table: bool = True
    evidence_requires_ids: bool = True
    document_kind: str = Field(default="page-guide", min_length=1)
    emphasize_verification: bool = False
    mention_scope_limits: bool = True

    @field_validator("template_id", "title_template", "body_template", "document_kind")
    @classmethod
    def _strip_required(_cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


@dataclass(frozen=True)
class EnduserDocScope:
    page: PageRecord
    related_pages: tuple[PageRecord, ...]
    fields: tuple[FieldRecord, ...]
    transactions: tuple[TransactionRecord, ...]
    entities: tuple[EntityRecord, ...]
    evidence: tuple[EvidenceRecord, ...]
    relations: tuple[RelationRecord, ...]


AVAILABLE_ENDUSER_DOC_TEMPLATES = {
    "page-default": "page-default.md",
    "page-ops-checklist": "page-ops-checklist.md",
}


def _load_packaged_template_body(filename: str) -> str:
    return files("codewiki").joinpath("templates", "enduser", filename).read_text(encoding="utf-8")


def _load_packaged_template_metadata(filename: str) -> dict:
    raw = files("codewiki").joinpath("templates", "enduser", filename).read_text(encoding="utf-8")
    parsed = yaml.safe_load(raw)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ValueError(f"template metadata '{filename}' must be a mapping")
    return parsed


def _extract_markdown_sections(markdown: str) -> set[str]:
    sections: set[str] = set()
    for line in markdown.splitlines():
        if line.startswith("## "):
            sections.add(line[3:].strip())
    return sections


def _extract_markdown_section_bodies(markdown: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current_section: str | None = None
    for line in markdown.splitlines():
        if line.startswith("## "):
            current_section = line[3:].strip()
            sections[current_section] = []
            continue
        if current_section is not None:
            sections[current_section].append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items()}


def load_enduser_doc_template(template_id: str) -> EnduserDocTemplate:
    try:
        filename = AVAILABLE_ENDUSER_DOC_TEMPLATES[template_id]
    except KeyError as exc:
        available = ", ".join(sorted(AVAILABLE_ENDUSER_DOC_TEMPLATES))
        raise ValueError(
            f"unknown enduser template '{template_id}'; available templates: {available}"
        ) from exc

    metadata_filename = filename.removesuffix(".md") + ".yaml"
    metadata = _load_packaged_template_metadata(metadata_filename)
    if metadata.get("template_id") and metadata["template_id"] != template_id:
        raise ValueError(
            f"template metadata '{metadata_filename}' has mismatched template_id '{metadata['template_id']}'"
        )

    return cast(
        EnduserDocTemplate,
        EnduserDocTemplate.model_validate(
            {
                "template_id": template_id,
                "title_template": metadata.get("title_template", "{page_name} User Guide"),
                "body_template": _load_packaged_template_body(filename),
                "required_sections": metadata.get("required_sections", REQUIRED_DOC_SECTIONS),
                "steps_must_be_numbered": metadata.get("rules", {}).get(
                    "steps_must_be_numbered", True
                ),
                "fields_must_be_table": metadata.get("rules", {}).get("fields_must_be_table", True),
                "evidence_requires_ids": metadata.get("rules", {}).get(
                    "evidence_requires_ids", True
                ),
                "document_kind": metadata.get("strategy", {}).get("document_kind", "page-guide"),
                "emphasize_verification": metadata.get("strategy", {}).get(
                    "emphasize_verification", False
                ),
                "mention_scope_limits": metadata.get("strategy", {}).get(
                    "mention_scope_limits", True
                ),
            }
        ),
    )


DEFAULT_ENDUSER_DOC_TEMPLATE = load_enduser_doc_template("page-default")

RecordT = TypeVar("RecordT")


def _sorted_records(records: list[RecordT], included_ids: set[str]) -> tuple[RecordT, ...]:
    return tuple(record for record in records if getattr(record, "id") in included_ids)


def _select_render_page(catalog: EnduserCatalog, page_id: str | None) -> PageRecord:
    if page_id:
        for page in catalog.pages:
            if page.id == page_id:
                return page
        available = ", ".join(page.id for page in catalog.pages) or "<none>"
        raise ValueError(f"unknown page '{page_id}'; available pages: {available}")

    if not catalog.pages:
        raise ValueError("catalog does not contain any pages")
    if len(catalog.pages) > 1:
        available = ", ".join(page.id for page in catalog.pages)
        raise ValueError(f"catalog contains multiple pages; select one with --page ({available})")
    return catalog.pages[0]


def infer_enduser_document_page_id(markdown: str, catalog: EnduserCatalog) -> str | None:
    title_line = next(
        (line[2:].strip() for line in markdown.splitlines() if line.startswith("# ")), ""
    )
    if title_line:
        for page in sorted(catalog.pages, key=lambda item: len(item.name), reverse=True):
            if page.name in title_line:
                return page.id

    for page in sorted(catalog.pages, key=lambda item: len(item.name), reverse=True):
        if f"`{page.name}`" in markdown or page.route in markdown:
            return page.id
    return None


def build_enduser_doc_scope(catalog: EnduserCatalog, page_id: str | None = None) -> EnduserDocScope:
    page = _select_render_page(catalog, page_id)
    record_types = catalog.index_ids()
    screenshot_refs = set(page.screenshot_refs)

    field_ids: set[str] = set()
    transaction_ids: set[str] = set()
    entity_ids: set[str] = set()
    related_page_ids: set[str] = {page.id}
    evidence_ids: set[str] = set()

    for relation in catalog.relations:
        if relation.source != page.id and relation.target != page.id:
            continue

        other_id = relation.target if relation.source == page.id else relation.source
        other_type = record_types.get(other_id)
        if other_type == "field":
            field_ids.add(other_id)
        elif other_type == "transaction":
            transaction_ids.add(other_id)
        elif other_type == "entity":
            entity_ids.add(other_id)
        elif other_type == "page":
            related_page_ids.add(other_id)
        elif other_type == "evidence":
            evidence_ids.add(other_id)
        evidence_ids.update(relation.evidence_ids)

    for relation in catalog.relations:
        if relation.source in transaction_ids and record_types.get(relation.target) == "entity":
            entity_ids.add(relation.target)
            evidence_ids.update(relation.evidence_ids)
        if relation.target in transaction_ids and record_types.get(relation.source) == "entity":
            entity_ids.add(relation.source)
            evidence_ids.update(relation.evidence_ids)

    for evidence in catalog.evidence:
        if evidence.source_ref == page.route or evidence.source_ref in screenshot_refs:
            evidence_ids.add(evidence.id)

    included_ids = related_page_ids | field_ids | transaction_ids | entity_ids | evidence_ids
    relations = tuple(
        relation
        for relation in catalog.relations
        if relation.source in included_ids and relation.target in included_ids
    )

    return EnduserDocScope(
        page=page,
        related_pages=_sorted_records(catalog.pages, related_page_ids),
        fields=_sorted_records(catalog.fields, field_ids),
        transactions=_sorted_records(catalog.transactions, transaction_ids),
        entities=_sorted_records(catalog.entities, entity_ids),
        evidence=_sorted_records(catalog.evidence, evidence_ids),
        relations=relations,
    )


def _render_fields_table(scope: EnduserDocScope) -> list[str]:
    lines = [
        "| Field | Label | Type | Required | Readonly |",
        "| --- | --- | --- | --- | --- |",
    ]
    for field in scope.fields:
        lines.append(
            f"| `{field.name}` | {field.label} | `{field.field_type}` | "
            f"{'yes' if field.required else 'no'} | {'yes' if field.readonly else 'no'} |"
        )
    if len(lines) == 2:
        lines.append("| _none_ | No page-scoped fields are cataloged | - | - | - |")
    return lines


def _render_navigation(scope: EnduserDocScope) -> list[str]:
    lines = [f"- Route: `{scope.page.route}`"]
    for relation in scope.relations:
        if relation.source != scope.page.id or relation.relation != "navigates_to":
            continue
        target_page = next(
            (page for page in scope.related_pages if page.id == relation.target), None
        )
        if target_page is not None:
            lines.append(f"- `{scope.page.name}` -> `{target_page.name}` (`{target_page.route}`)")
    if len(lines) == 1:
        lines.append("- No cataloged navigation targets are linked from this page.")
    return lines


def _render_evidence(scope: EnduserDocScope) -> list[str]:
    if not scope.evidence:
        return ["- `evidence.none`: No page-scoped evidence is linked in the catalog."]

    lines: list[str] = []
    field_by_id = {field.id: field for field in scope.fields}
    transaction_by_id = {transaction.id: transaction for transaction in scope.transactions}
    entity_by_id = {entity.id: entity for entity in scope.entities}
    for item in scope.evidence:
        field_labels: list[str] = []
        transaction_names: list[str] = []
        entity_names: list[str] = []
        supports_page_scope = False
        for relation in scope.relations:
            if item.id not in relation.evidence_ids:
                continue
            if relation.source == scope.page.id or relation.target == scope.page.id:
                supports_page_scope = True
            if relation.source in field_by_id:
                field_labels.append(field_by_id[relation.source].label)
            if relation.target in field_by_id:
                field_labels.append(field_by_id[relation.target].label)
            if relation.source in transaction_by_id:
                transaction_names.append(transaction_by_id[relation.source].name)
            if relation.target in transaction_by_id:
                transaction_names.append(transaction_by_id[relation.target].name)
            if relation.source in entity_by_id:
                entity_names.append(entity_by_id[relation.source].name)
            if relation.target in entity_by_id:
                entity_names.append(entity_by_id[relation.target].name)
        if item.evidence_type == "screenshot":
            lines.append(
                f"- `{item.id}`: {item.summary} Supports visual confirmation of `{scope.page.name}`."
            )
            continue

        support_parts: list[str] = []
        if supports_page_scope:
            support_parts.append(f"the page scope `{scope.page.name}`")
        if field_labels:
            field_names = ", ".join(f"`{label}`" for label in dict.fromkeys(field_labels))
            support_parts.append(f"the page fields {field_names}")
        if transaction_names:
            names = ", ".join(f"`{name}`" for name in dict.fromkeys(transaction_names))
            support_parts.append(f"the linked transaction scope {names}")
        if entity_names:
            names = ", ".join(f"`{name}`" for name in dict.fromkeys(entity_names))
            support_parts.append(f"the linked entities {names}")

        if support_parts:
            lines.append(f"- `{item.id}`: {item.summary} Supports {', '.join(support_parts)}.")
        else:
            lines.append(f"- `{item.id}`: {item.summary}")
    return lines


def _format_field_instruction(field: FieldRecord, *, verification_mode: bool) -> str:
    if verification_mode:
        qualifiers = [
            "required" if field.required else "optional",
            "readonly" if field.readonly else "editable",
        ]
        return f"Verify `{field.label}` as a `{field.field_type}` field that is {', '.join(qualifiers)}."

    if field.readonly:
        return f"Review `{field.label}` as a readonly `{field.field_type}` field on the page."
    action = "Provide a value for" if field.required else "Use"
    return f"{action} `{field.label}` as an available `{field.field_type}` field within the cataloged page scope."


def _page_scope_summary(scope: EnduserDocScope) -> str:
    components = ["page-scoped fields"]
    if scope.transactions:
        components.append("linked transactions")
    if scope.entities:
        components.append("linked entities")
    components.extend(["navigation", "cited evidence"])
    return ", ".join(components)


def _field_step_for_scope(
    field: FieldRecord, scope: EnduserDocScope, *, verification_mode: bool
) -> str:
    if verification_mode:
        return _format_field_instruction(field, verification_mode=True)

    primary_transaction = scope.transactions[0] if scope.transactions else None
    if primary_transaction is None:
        state = "readonly" if field.readonly else "editable"
        required = "required" if field.required else "optional"
        return (
            f"Review `{field.label}` as an {state} `{field.field_type}` field that is "
            f"{required} on the cataloged page."
        )

    if field.readonly:
        return (
            f"Review `{field.label}` as a readonly `{field.field_type}` field linked to the "
            f"cataloged `{primary_transaction.name}` goal: {primary_transaction.goal}."
        )

    requirement = "required" if field.required else "optional"
    return (
        f"Review `{field.label}` as an editable `{field.field_type}` field that is {requirement} "
        f"for the cataloged `{primary_transaction.name}` goal: {primary_transaction.goal}."
    )


def _render_purpose(scope: EnduserDocScope, template: EnduserDocTemplate) -> str:
    route_text = f" at `{scope.page.route}`" if scope.page.route else ""
    transaction_text = ""
    if scope.transactions:
        transaction_names = ", ".join(f"`{transaction.name}`" for transaction in scope.transactions)
        transaction_text = f" It is linked to {transaction_names}."
    field_text = ""
    if scope.fields and scope.transactions and template.document_kind != "ops-checklist":
        field_names = ", ".join(f"`{field.label}`" for field in scope.fields)
        field_text = f" Within this page scope, users can work with {field_names} to support the documented workflow."
    entity_text = ""
    if scope.entities:
        entity_names = ", ".join(f"`{entity.name}`" for entity in scope.entities)
        entity_text = f" The linked business records are {entity_names}."
    scope_limit = ""
    if template.mention_scope_limits:
        scope_limit = f" This draft is limited to {_page_scope_summary(scope)}."

    if template.document_kind == "ops-checklist":
        return (
            f"Use this checklist to verify the cataloged operator-facing behavior for `{scope.page.name}`{route_text}."
            f"{transaction_text}{entity_text}{scope_limit}"
        )
    return (
        f"Use `{scope.page.name}`{route_text} as documented in the catalog."
        f"{transaction_text}{field_text}{entity_text}{scope_limit}"
    )


def _render_audience(scope: EnduserDocScope, template: EnduserDocTemplate) -> str:
    if template.document_kind == "ops-checklist":
        return f"Operators or reviewers confirming the supported behavior for `{scope.page.name}`."
    if scope.transactions:
        return (
            f"Users working on the `{scope.page.name}` page to support the cataloged "
            f"`{scope.transactions[0].name}` goal: {scope.transactions[0].goal}."
        )
    return f"Users who need a page-scoped guide for `{scope.page.name}`."


def _render_preconditions(scope: EnduserDocScope, template: EnduserDocTemplate) -> str:
    lines = [f"- Use this document only for the cataloged page scope `{scope.page.name}`."]
    if scope.page.route:
        lines.append(f"- Treat `{scope.page.route}` as catalog metadata for this page scope.")
    if template.document_kind == "ops-checklist":
        lines.append(
            "- Treat any uncataloged buttons, results, save actions, or navigation as unsupported until separately evidenced."
        )
    elif template.mention_scope_limits:
        lines.append(
            "- Use only the page-scoped fields, relations, and evidence listed in this document when describing the workflow."
        )
    if scope.evidence:
        lines.append(
            "- Refer to the cited evidence ids when you need to confirm a page or workflow claim."
        )
    return "\n".join(lines)


def _render_steps(scope: EnduserDocScope, template: EnduserDocTemplate) -> str:
    steps: list[str] = [f"Open the cataloged page scope `{scope.page.name}`."]
    for field in scope.fields:
        steps.append(
            _field_step_for_scope(field, scope, verification_mode=template.emphasize_verification)
        )

    if scope.transactions and template.document_kind == "ops-checklist":
        transaction_summaries = "; ".join(
            f"`{transaction.name}`: {transaction.goal}" for transaction in scope.transactions
        )
        steps.append(
            f"Confirm that the page is linked to these cataloged transactions: {transaction_summaries}."
        )

    if scope.entities and template.document_kind == "ops-checklist":
        entity_names = ", ".join(f"`{entity.name}`" for entity in scope.entities)
        steps.append(
            f"Verify that the page workflow is tied to these business records: {entity_names}."
        )

    navigation_targets = [item for item in scope.related_pages if item.id != scope.page.id]
    if navigation_targets:
        target_text = ", ".join(f"`{item.name}` (`{item.route}`)" for item in navigation_targets)
        steps.append(f"Only continue to catalog-linked destinations when needed: {target_text}.")
    else:
        steps.append(
            "Do not assume any additional page transitions because no navigation targets are evidenced for this page."
        )

    return "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))


def render_enduser_document(
    catalog: EnduserCatalog,
    template: EnduserDocTemplate = DEFAULT_ENDUSER_DOC_TEMPLATE,
    page_id: str | None = None,
) -> str:
    template_sections = _extract_markdown_sections(template.body_template)
    missing_sections = [
        section
        for section in REQUIRED_DOC_SECTIONS
        if section not in template.required_sections or section not in template_sections
    ]
    if missing_sections:
        raise ValueError(f"missing required sections: {', '.join(missing_sections)}")

    scope = build_enduser_doc_scope(catalog, page_id=page_id)
    page_name = scope.page.name
    title = template.title_template.format(page_name=page_name)
    return template.body_template.format(
        title=title,
        page_name=page_name,
        purpose=_render_purpose(scope, template),
        audience=_render_audience(scope, template),
        preconditions=_render_preconditions(scope, template),
        steps=_render_steps(scope, template),
        fields_table="\n".join(_render_fields_table(scope)),
        navigation="\n".join(_render_navigation(scope)),
        evidence="\n".join(_render_evidence(scope)),
        review_status=(
            "Checklist draft ready for review."
            if template.document_kind == "ops-checklist"
            else "Catalog-scoped draft ready for review."
        ),
    )


def validate_rendered_enduser_document(
    markdown: str,
    template: EnduserDocTemplate = DEFAULT_ENDUSER_DOC_TEMPLATE,
) -> None:
    if not markdown.lstrip().startswith("# "):
        raise ValueError("document must start with a level-1 markdown title")

    section_bodies = _extract_markdown_section_bodies(markdown)
    missing_sections = [
        section for section in template.required_sections if section not in section_bodies
    ]
    if missing_sections:
        raise ValueError(f"document is missing required sections: {', '.join(missing_sections)}")

    steps_body = section_bodies["Steps"]
    if template.steps_must_be_numbered and not re.search(r"(?m)^\d+\.\s", steps_body):
        raise ValueError("document Steps section must contain a numbered list")

    fields_body = section_bodies["Fields"]
    if template.fields_must_be_table:
        fields_lines = [line.strip() for line in fields_body.splitlines() if line.strip()]
        if (
            len(fields_lines) < 2
            or not fields_lines[0].startswith("|")
            or not fields_lines[1].startswith("|")
        ):
            raise ValueError("document Fields section must contain a markdown table")

    evidence_body = section_bodies["Evidence"]
    if template.evidence_requires_ids:
        evidence_lines = [line.strip() for line in evidence_body.splitlines() if line.strip()]
        if not evidence_lines:
            raise ValueError("document Evidence section must contain evidence entries")
        invalid_evidence = [
            line for line in evidence_lines if not re.match(r"^[-*]\s+`[^`]+`:\s+\S+", line)
        ]
        if invalid_evidence:
            raise ValueError(
                "document Evidence section must contain bullet entries with evidence ids"
            )


__all__ = [
    "AVAILABLE_ENDUSER_DOC_TEMPLATES",
    "build_enduser_doc_scope",
    "DEFAULT_ENDUSER_DOC_TEMPLATE",
    "EnduserDocScope",
    "EnduserDocTemplate",
    "infer_enduser_document_page_id",
    "REQUIRED_DOC_SECTIONS",
    "load_enduser_doc_template",
    "render_enduser_document",
    "validate_rendered_enduser_document",
]
