"""Canonical YAML-first records for enduser-wiki catalogs."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


RecordType = Literal["entity", "page", "field", "transaction", "evidence"]
EvidenceType = Literal["code", "playwright", "screenshot", "network", "llm"]


class _BaseRecord(BaseModel):
    id: str = Field(min_length=3)
    name: str = Field(min_length=1)

    @field_validator("id", "name")
    @classmethod
    def _strip_required(_cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class EntityRecord(_BaseRecord):
    description: str = Field(min_length=1)


class PageRecord(_BaseRecord):
    route: str = Field(min_length=1)
    screenshot_refs: list[str] = Field(default_factory=list)


class FieldRecord(_BaseRecord):
    label: str = Field(min_length=1)
    field_type: str = Field(min_length=1)
    required: bool = False
    readonly: bool = False

    @field_validator("label", "field_type")
    @classmethod
    def _field_strings_required(_cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class TransactionRecord(_BaseRecord):
    goal: str = Field(min_length=1)


class EvidenceRecord(BaseModel):
    id: str = Field(min_length=3)
    evidence_type: EvidenceType
    source_ref: str = Field(min_length=1)
    summary: str = Field(min_length=1)

    @field_validator("id", "source_ref", "summary")
    @classmethod
    def _evidence_strings_required(_cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class RelationRecord(BaseModel):
    source: str = Field(min_length=3)
    relation: str = Field(min_length=1)
    target: str = Field(min_length=3)
    evidence_ids: list[str] = Field(default_factory=list)

    @field_validator("source", "relation", "target")
    @classmethod
    def _relation_strings_required(_cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value


class EnduserCatalog(BaseModel):
    entities: list[EntityRecord] = Field(default_factory=list)
    pages: list[PageRecord] = Field(default_factory=list)
    fields: list[FieldRecord] = Field(default_factory=list)
    transactions: list[TransactionRecord] = Field(default_factory=list)
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    relations: list[RelationRecord] = Field(default_factory=list)

    def index_ids(self) -> dict[str, RecordType]:
        record_types: dict[str, RecordType] = {}
        for record in self.entities:
            record_types[record.id] = "entity"
        for record in self.pages:
            record_types[record.id] = "page"
        for record in self.fields:
            record_types[record.id] = "field"
        for record in self.transactions:
            record_types[record.id] = "transaction"
        for record in self.evidence:
            record_types[record.id] = "evidence"
        return record_types

    @model_validator(mode="after")
    def _validate_relations(self) -> "EnduserCatalog":
        known_ids = self.index_ids()
        for relation in self.relations:
            if relation.source not in known_ids:
                raise ValueError(f"unknown relation source: {relation.source}")
            if relation.target not in known_ids:
                raise ValueError(f"unknown relation target: {relation.target}")
            for evidence_id in relation.evidence_ids:
                if evidence_id not in known_ids or known_ids[evidence_id] != "evidence":
                    raise ValueError(f"unknown relation evidence: {evidence_id}")
        return self
