"""Structured review artifacts and external runner wrappers for enduser docs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ReviewStatus = Literal["pass", "fail"]
PublicationStatus = Literal["approved", "rejected"]
RunnerName = Literal["codex", "opencode"]


class ReviewScoreSet(BaseModel):
    coverage: int = Field(ge=1, le=5)
    evidence_alignment: int = Field(ge=1, le=5)
    format_compliance: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)


class JudgeReview(BaseModel):
    runner: Literal["codex"]
    status: ReviewStatus
    scores: ReviewScoreSet
    summary: str = Field(min_length=1)
    findings: list[str] = Field(default_factory=list)


class AdversarialReview(BaseModel):
    runner: Literal["opencode"]
    status: ReviewStatus
    findings: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    format_attacks: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=1)


class PublicationDecision(BaseModel):
    status: PublicationStatus
    reasons: list[str] = Field(default_factory=list)


class EnduserReviewArtifact(BaseModel):
    document_path: str = Field(min_length=1)
    catalog_path: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    judge: JudgeReview
    adversarial: AdversarialReview
    publication_decision: PublicationDecision

    @field_validator("document_path", "catalog_path", "template_id")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_publication_decision(self) -> "EnduserReviewArtifact":
        has_failed_review = self.judge.status == "fail" or self.adversarial.status == "fail"
        if has_failed_review and self.publication_decision.status != "rejected":
            raise ValueError("publication decision must reject failed reviews")
        if not has_failed_review and self.publication_decision.status != "approved":
            raise ValueError("publication decision must approve passing reviews")
        return self


def _run_external_review_command(command: list[str], input_payload: str) -> dict:
    completed = subprocess.run(
        command,
        input=input_payload,
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout)


def build_review_prompt(document_path: Path | str, catalog_path: Path | str, template_id: str) -> str:
    return json.dumps(
        {
            "document_path": str(document_path),
            "catalog_path": str(catalog_path),
            "template_id": template_id,
            "instructions": (
                "Return JSON only. Review the document against the catalog, "
                "score evidence alignment and format compliance, and list concrete findings."
            ),
        }
    )


def run_codex_judge(document_path: Path | str, catalog_path: Path | str, template_id: str) -> JudgeReview:
    payload = build_review_prompt(document_path, catalog_path, template_id)
    response = _run_external_review_command(["codex", "exec"], payload)
    return JudgeReview.model_validate(response)


def run_opencode_adversarial(
    document_path: Path | str,
    catalog_path: Path | str,
    template_id: str,
) -> AdversarialReview:
    payload = build_review_prompt(document_path, catalog_path, template_id)
    response = _run_external_review_command(["opencode", "run"], payload)
    return AdversarialReview.model_validate(response)


__all__ = [
    "AdversarialReview",
    "EnduserReviewArtifact",
    "JudgeReview",
    "PublicationDecision",
    "ReviewScoreSet",
    "build_review_prompt",
    "run_codex_judge",
    "run_opencode_adversarial",
]
