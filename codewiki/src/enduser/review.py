"""Structured review artifacts and external runner wrappers for enduser docs."""

from __future__ import annotations

import json
import tempfile
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from codewiki.src.enduser.docs import DEFAULT_ENDUSER_DOC_TEMPLATE, EnduserDocTemplate
from codewiki.src.enduser.prompting import (
    build_codex_adversarial_prompt,
    build_codex_final_draft_prompt,
    build_codex_judge_prompt,
    resolve_repository_root,
)


ReviewStatus = Literal["pass", "fail"]
PublicationStatus = Literal["approved", "rejected"]
RunnerName = Literal["codex"]
DEFAULT_REVIEW_TIMEOUT_SECONDS = 120
STRING_ARRAY_SCHEMA = {"type": "array", "items": {"type": "string"}}


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
    runner: Literal["codex"]
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
    final_document_path: str = Field(min_length=1)
    catalog_path: str = Field(min_length=1)
    template_id: str = Field(min_length=1)
    judge: JudgeReview
    adversarial: AdversarialReview
    publication_decision: PublicationDecision

    @field_validator("document_path", "final_document_path", "catalog_path", "template_id")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be empty")
        return value

    @model_validator(mode="after")
    def _validate_publication_decision(self) -> "EnduserReviewArtifact":
        judge_failed = self.judge.status == "fail"
        if judge_failed and self.publication_decision.status != "rejected":
            raise ValueError("publication decision must reject failed final judge reviews")
        if not judge_failed and self.publication_decision.status != "approved":
            raise ValueError("publication decision must approve passing final judge reviews")
        return self


def _strip_markdown_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped
    if lines[-1].strip() != "```":
        return stripped
    return "\n".join(lines[1:-1]).strip()


def _extract_json_object(text: str) -> dict:
    stripped = _strip_markdown_code_fences(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise
        return json.loads(stripped[start : end + 1])


def _coerce_status(value: object, *, default: ReviewStatus | None = None) -> ReviewStatus | None:
    if not isinstance(value, str):
        return default
    normalized = value.strip().lower()
    if normalized in {"pass", "passed", "approve", "approved"} or normalized.startswith("pass"):
        return "pass"
    if normalized in {"fail", "failed", "reject", "rejected"} or normalized.startswith("fail"):
        return "fail"
    return default


def _stringify_items(items: object) -> list[str]:
    if not isinstance(items, list):
        return []
    normalized: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("message") or item.get("detail") or item.get("text") or "").strip()
        else:
            text = str(item).strip()
        if text:
            normalized.append(text)
    return normalized


def _normalize_adversarial_response(response: dict) -> dict:
    if "runner" in response and "status" in response and "summary" in response:
        normalized = dict(response)
        status = _coerce_status(normalized.get("status"))
        normalized["findings"] = _stringify_items(response.get("findings", []))
        normalized["unsupported_claims"] = _stringify_items(response.get("unsupported_claims", []))
        normalized["missing_evidence"] = _stringify_items(response.get("missing_evidence", []))
        normalized["format_attacks"] = _stringify_items(response.get("format_attacks", []))
        if status is None:
            has_issues = any(
                [
                    normalized["findings"],
                    normalized["unsupported_claims"],
                    normalized["missing_evidence"],
                    normalized["format_attacks"],
                ]
            )
            status = "fail" if has_issues else "pass"
        normalized["status"] = status
        return normalized

    raise ValueError("unrecognized codex adversarial response shape")


def _normalize_score(value: object) -> int:
    if not isinstance(value, (int, float)):
        raise ValueError("missing or invalid score value")
    numeric = float(value)
    if numeric <= 1:
        return max(1, min(5, round(1 + numeric * 4)))
    if numeric <= 5:
        return max(1, min(5, round(numeric)))
    return max(1, min(5, round(numeric / 20)))


def _normalize_judge_response(response: dict) -> dict:
    if "runner" in response and "status" in response and "summary" in response:
        normalized = dict(response)
        status = _coerce_status(normalized.get("status"))
        if status is None:
            raise ValueError("unrecognized codex status")
        normalized["status"] = status
        scores = normalized.get("scores", {})
        if not isinstance(scores, dict):
            raise ValueError("missing or invalid scores object")
        normalized["scores"] = {
            "coverage": _normalize_score(scores.get("coverage")),
            "evidence_alignment": _normalize_score(scores.get("evidence_alignment")),
            "format_compliance": _normalize_score(scores.get("format_compliance")),
            "clarity": _normalize_score(scores.get("clarity")),
        }
        normalized["findings"] = _stringify_items(response.get("findings", []))
        return normalized

    if "result" not in response:
        raise ValueError("unrecognized codex response shape")
    scores = response.get("scores", {}) if isinstance(response.get("scores"), dict) else {}
    findings = _stringify_items(response.get("findings", []))
    result = response.get("status") or response.get("result")
    status = _coerce_status(result)
    if status is None:
        raise ValueError("unrecognized codex review status")
    return {
        "runner": "codex",
        "status": status,
        "scores": {
            "coverage": _normalize_score(scores.get("coverage", scores.get("catalog_coverage", scores.get("overall")))),
            "evidence_alignment": _normalize_score(scores.get("evidence_alignment", scores.get("overall"))),
            "format_compliance": _normalize_score(scores.get("format_compliance", scores.get("overall"))),
            "clarity": _normalize_score(scores.get("clarity", scores.get("overall"))),
        },
        "summary": (
            str(response.get("summary")).strip()
            if isinstance(response.get("summary"), str) and str(response.get("summary")).strip()
            else (findings[0] if findings else "Judge completed review.")
        ),
        "findings": findings,
    }


def _write_output_schema(schema: dict) -> tempfile.NamedTemporaryFile:
    schema_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".json", encoding="utf-8")
    json.dump(schema, schema_file)
    schema_file.flush()
    return schema_file


def _run_codex_command(
    input_payload: str,
    *,
    cwd: Path,
    output_schema: dict | None = None,
    timeout_seconds: int = DEFAULT_REVIEW_TIMEOUT_SECONDS,
) -> dict:
    with tempfile.NamedTemporaryFile(mode="r+", suffix=".json", encoding="utf-8") as output_file:
        command = [
            "codex",
            "exec",
            "--skip-git-repo-check",
        ]
        schema_file = _write_output_schema(output_schema) if output_schema else None
        if schema_file is not None:
            command.extend(["--output-schema", schema_file.name])
        command.extend(["--output-last-message", output_file.name, "-"])
        try:
            completed = subprocess.run(
                command,
                input=input_payload,
                text=True,
                capture_output=True,
                check=True,
                cwd=str(cwd),
                timeout=timeout_seconds,
            )
            raw_output = Path(output_file.name).read_text(encoding="utf-8")
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"codex timed out after {timeout_seconds}s") from exc
        except subprocess.CalledProcessError as exc:
            raise ValueError(f"codex failed: {exc.stderr.strip() or exc.stdout.strip()}") from exc
        finally:
            if schema_file is not None:
                schema_file.close()
    try:
        return _extract_json_object(raw_output)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"codex returned non-JSON output: {exc}. stderr={completed.stderr.strip()}"
        ) from exc


def build_review_prompt(
    document_path: Path | str,
    catalog_path: Path | str,
    template: EnduserDocTemplate = DEFAULT_ENDUSER_DOC_TEMPLATE,
) -> str:
    return build_codex_judge_prompt(document_path, catalog_path, template)


def _review_workspace(*paths: Path | str) -> Path:
    return resolve_repository_root(*paths)


def run_codex_judge(
    document_path: Path | str,
    catalog_path: Path | str,
    template: EnduserDocTemplate = DEFAULT_ENDUSER_DOC_TEMPLATE,
) -> JudgeReview:
    payload = build_codex_judge_prompt(document_path, catalog_path, template)
    response = _run_codex_command(
        payload,
        cwd=_review_workspace(document_path, catalog_path),
        output_schema={
            "type": "object",
            "properties": {
                "runner": {"type": "string", "const": "codex"},
                "status": {"type": "string"},
                "scores": {
                    "type": "object",
                    "properties": {
                        "coverage": {"type": "number"},
                        "evidence_alignment": {"type": "number"},
                        "format_compliance": {"type": "number"},
                        "clarity": {"type": "number"},
                    },
                    "required": ["coverage", "evidence_alignment", "format_compliance", "clarity"],
                    "additionalProperties": False,
                },
                "summary": {"type": "string"},
                "findings": STRING_ARRAY_SCHEMA,
            },
            "required": ["runner", "status", "scores", "summary", "findings"],
            "additionalProperties": False,
        },
    )
    response = _normalize_judge_response(response)
    return JudgeReview.model_validate(response)


def run_codex_adversarial(
    document_path: Path | str,
    catalog_path: Path | str,
    template: EnduserDocTemplate = DEFAULT_ENDUSER_DOC_TEMPLATE,
) -> AdversarialReview:
    payload = build_codex_adversarial_prompt(document_path, catalog_path, template)
    response = _run_codex_command(
        payload,
        cwd=_review_workspace(document_path, catalog_path),
        output_schema={
            "type": "object",
            "properties": {
                "runner": {"type": "string", "const": "codex"},
                "status": {"type": "string"},
                "findings": STRING_ARRAY_SCHEMA,
                "unsupported_claims": STRING_ARRAY_SCHEMA,
                "missing_evidence": STRING_ARRAY_SCHEMA,
                "format_attacks": STRING_ARRAY_SCHEMA,
                "summary": {"type": "string"},
            },
            "required": [
                "runner",
                "status",
                "findings",
                "unsupported_claims",
                "missing_evidence",
                "format_attacks",
                "summary",
            ],
            "additionalProperties": False,
        },
    )
    response = _normalize_adversarial_response(response)
    return AdversarialReview.model_validate(response)


def run_codex_final_draft(
    document_path: Path | str,
    catalog_path: Path | str,
    template: EnduserDocTemplate,
    adversarial_review: AdversarialReview,
) -> str:
    payload = build_codex_final_draft_prompt(
        document_path,
        catalog_path,
        template,
        adversarial_review.model_dump(),
    )
    response = _run_codex_command(
        payload,
        cwd=_review_workspace(document_path, catalog_path),
        output_schema={
            "type": "object",
            "properties": {"document": {"type": "string"}},
            "required": ["document"],
            "additionalProperties": False,
        },
    )
    document = response.get("document", "").strip()
    if not document:
        raise ValueError("codex final draft response did not include a document")
    return document + ("\n" if not document.endswith("\n") else "")


__all__ = [
    "AdversarialReview",
    "EnduserReviewArtifact",
    "JudgeReview",
    "PublicationDecision",
    "ReviewScoreSet",
    "build_review_prompt",
    "run_codex_adversarial",
    "run_codex_final_draft",
    "run_codex_judge",
]
