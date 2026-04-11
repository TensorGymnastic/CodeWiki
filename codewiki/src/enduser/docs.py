"""Render fixed-format enduser documentation from validated catalogs."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from codewiki.src.enduser.models import EnduserCatalog


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
    required_sections: list[str] = Field(default_factory=lambda: list(REQUIRED_DOC_SECTIONS))

    @field_validator("template_id", "title_template")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


DEFAULT_ENDUSER_DOC_TEMPLATE = EnduserDocTemplate(
    template_id="page-default",
    title_template="{page_name} User Guide",
)


def _render_fields_table(catalog: EnduserCatalog) -> list[str]:
    lines = [
        "| Field | Label | Type | Required | Readonly |",
        "| --- | --- | --- | --- | --- |",
    ]
    for field in catalog.fields:
        lines.append(
            f"| `{field.name}` | {field.label} | `{field.field_type}` | "
            f"{'yes' if field.required else 'no'} | {'yes' if field.readonly else 'no'} |"
        )
    return lines


def _render_navigation(catalog: EnduserCatalog) -> list[str]:
    navigation_lines = []
    for relation in catalog.relations:
        if relation.relation != "navigates_to":
            continue
        navigation_lines.append(f"- `{relation.source}` -> `{relation.target}`")
    return navigation_lines or ["- No known navigation targets."]


def _render_evidence(catalog: EnduserCatalog) -> list[str]:
    return [f"- `{item.id}`: {item.summary}" for item in catalog.evidence]


def render_enduser_document(
    catalog: EnduserCatalog,
    template: EnduserDocTemplate = DEFAULT_ENDUSER_DOC_TEMPLATE,
) -> str:
    missing_sections = [section for section in REQUIRED_DOC_SECTIONS if section not in template.required_sections]
    if missing_sections:
        raise ValueError(f"missing required sections: {', '.join(missing_sections)}")

    first_page = catalog.pages[0] if catalog.pages else None
    page_name = first_page.name if first_page else "Enduser Page"
    title = template.title_template.format(page_name=page_name)

    lines = [
        f"# {title}",
        "",
        "## Purpose",
        f"Guide the user through `{page_name}` using the validated catalog.",
        "",
        "## Audience",
        "Operators and business users who need a stable workflow description.",
        "",
        "## Preconditions",
        "- You can access the target page in the product.",
        "",
        "## Steps",
        f"1. Open `{page_name}`.",
        "2. Review the visible fields before making changes.",
        "3. Complete the workflow using the fields and navigation described below.",
        "",
        "## Fields",
    ]
    lines.extend(_render_fields_table(catalog))
    lines.extend(
        [
            "",
            "## Navigation",
        ]
    )
    lines.extend(_render_navigation(catalog))
    lines.extend(
        [
            "",
            "## Evidence",
        ]
    )
    lines.extend(_render_evidence(catalog))
    lines.extend(
        [
            "",
            "## Review Status",
            "Pending external review.",
        ]
    )
    return "\n".join(lines) + "\n"


__all__ = [
    "DEFAULT_ENDUSER_DOC_TEMPLATE",
    "EnduserDocTemplate",
    "REQUIRED_DOC_SECTIONS",
    "render_enduser_document",
]
