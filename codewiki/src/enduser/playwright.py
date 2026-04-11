"""Import deterministic Playwright crawl artifacts into enduser catalog records."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from codewiki.src.enduser.models import (
    EnduserCatalog,
    EvidenceRecord,
    FieldRecord,
    PageRecord,
    RelationRecord,
)


class PlaywrightFieldCapture(BaseModel):
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    role: str = Field(min_length=1)
    required: bool = False
    readonly: bool = False


class PlaywrightActionCapture(BaseModel):
    name: str = Field(min_length=1)
    label: str = Field(min_length=1)
    role: str = Field(min_length=1)
    target_route: str | None = None


class PlaywrightPageCapture(BaseModel):
    route: str = Field(min_length=1)
    title: str | None = None
    screenshot_path: str | None = None
    fields: list[PlaywrightFieldCapture] = Field(default_factory=list)
    actions: list[PlaywrightActionCapture] = Field(default_factory=list)


class PlaywrightCrawl(BaseModel):
    pages: list[PlaywrightPageCapture] = Field(default_factory=list)


class PlaywrightExtractorConfig(BaseModel):
    page_prefix: str = "page"
    field_prefix: str = "field"
    page_evidence_prefix: str = "ev.playwright.page"
    contains_relation: str = "contains"
    navigation_relation: str = "navigates_to"
    fallback_field_type: str = "text"
    field_type_by_role: dict[str, str] = Field(
        default_factory=lambda: {
            "textbox": "text",
            "searchbox": "search",
            "combobox": "select",
            "checkbox": "checkbox",
            "radio": "radio",
            "spinbutton": "number",
            "switch": "toggle",
            "button": "button",
        }
    )

    def slugify_route(self, route: str) -> str:
        cleaned = route.strip().strip("/")
        if not cleaned:
            return "root"
        return re.sub(r"[^a-z0-9]+", "_", cleaned.lower()).strip("_")

    def page_id(self, route: str) -> str:
        return f"{self.page_prefix}.{self.slugify_route(route)}"

    def field_id(self, route: str, field_name: str) -> str:
        field_slug = re.sub(r"[^a-z0-9]+", "_", field_name.lower()).strip("_")
        return f"{self.field_prefix}.{self.slugify_route(route)}.{field_slug}"

    def page_evidence_id(self, route: str) -> str:
        return f"{self.page_evidence_prefix}.{self.slugify_route(route)}"

    def field_type(self, role: str) -> str:
        return self.field_type_by_role.get(role.lower(), self.fallback_field_type)


class PlaywrightCatalogExtractor:
    """Build page and field catalog records from saved Playwright crawl data."""

    def __init__(self, config: PlaywrightExtractorConfig | None = None):
        self.config = config or PlaywrightExtractorConfig()

    def extract(self, crawl: PlaywrightCrawl) -> EnduserCatalog:
        pages: list[PageRecord] = []
        fields: list[FieldRecord] = []
        evidence: list[EvidenceRecord] = []
        relations: list[RelationRecord] = []

        route_to_page_id = {
            page.route: self.config.page_id(page.route)
            for page in crawl.pages
        }

        for page in crawl.pages:
            page_id = route_to_page_id[page.route]
            evidence_id = self.config.page_evidence_id(page.route)
            page_name = page.title.strip() if page.title else page.route
            screenshot_refs = [page.screenshot_path] if page.screenshot_path else []

            pages.append(
                PageRecord(
                    id=page_id,
                    name=page_name,
                    route=page.route,
                    screenshot_refs=screenshot_refs,
                )
            )
            evidence.append(
                EvidenceRecord(
                    id=evidence_id,
                    evidence_type="playwright",
                    source_ref=page.route,
                    summary=f"Playwright crawl evidence for {page.route}",
                )
            )

            for field in page.fields:
                field_id = self.config.field_id(page.route, field.name)
                fields.append(
                    FieldRecord(
                        id=field_id,
                        name=field.name,
                        label=field.label,
                        field_type=self.config.field_type(field.role),
                        required=field.required,
                        readonly=field.readonly,
                    )
                )
                relations.append(
                    RelationRecord(
                        source=page_id,
                        relation=self.config.contains_relation,
                        target=field_id,
                        evidence_ids=[evidence_id],
                    )
                )

            for action in page.actions:
                if not action.target_route:
                    continue
                target_page_id = route_to_page_id.get(action.target_route)
                if target_page_id is None:
                    continue
                relations.append(
                    RelationRecord(
                        source=page_id,
                        relation=self.config.navigation_relation,
                        target=target_page_id,
                        evidence_ids=[evidence_id],
                    )
                )

        return EnduserCatalog(
            pages=pages,
            fields=fields,
            evidence=evidence,
            relations=relations,
        )


def load_playwright_crawl(source: Path | str | dict) -> PlaywrightCrawl:
    """Load crawl input from a path or in-memory mapping."""

    if isinstance(source, dict):
        return PlaywrightCrawl.model_validate(source)

    path = Path(source)
    return PlaywrightCrawl.model_validate(json.loads(path.read_text(encoding="utf-8")))


__all__ = [
    "PlaywrightActionCapture",
    "PlaywrightCatalogExtractor",
    "PlaywrightCrawl",
    "PlaywrightExtractorConfig",
    "PlaywrightFieldCapture",
    "PlaywrightPageCapture",
    "load_playwright_crawl",
]
