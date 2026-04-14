import pytest


def test_review_artifact_requires_codex_judge_and_codex_adversarial_sections():
    from codewiki.src.enduser.review import EnduserReviewArtifact

    artifact = EnduserReviewArtifact.model_validate(
        {
            "document_path": "doc.md",
            "final_document_path": "doc.final.md",
            "catalog_path": "catalog.yaml",
            "template_id": "page-default",
            "judge": {
                "runner": "codex",
                "status": "pass",
                "scores": {
                    "coverage": 4,
                    "evidence_alignment": 5,
                    "format_compliance": 5,
                    "clarity": 4,
                },
                "summary": "Judge passed the document.",
                "findings": [],
            },
            "adversarial": {
                "runner": "codex",
                "status": "pass",
                "findings": [],
                "unsupported_claims": [],
                "missing_evidence": [],
                "format_attacks": [],
                "summary": "No adversarial issues found.",
            },
            "publication_decision": {
                "status": "approved",
                "reasons": [],
            },
        }
    )

    assert artifact.judge.runner == "codex"
    assert artifact.adversarial.runner == "codex"
    assert artifact.publication_decision.status == "approved"


def test_publication_decision_rejects_failed_final_judge_review():
    from codewiki.src.enduser.review import EnduserReviewArtifact

    with pytest.raises(ValueError, match="publication decision"):
        EnduserReviewArtifact.model_validate(
            {
                "document_path": "doc.md",
                "final_document_path": "doc.final.md",
                "catalog_path": "catalog.yaml",
                "template_id": "page-default",
                "judge": {
                    "runner": "codex",
                    "status": "fail",
                    "scores": {
                        "coverage": 2,
                        "evidence_alignment": 2,
                        "format_compliance": 5,
                        "clarity": 2,
                    },
                    "summary": "Judge found unsupported claims.",
                    "findings": ["Unsupported workflow claim."],
                },
                "adversarial": {
                    "runner": "codex",
                    "status": "pass",
                    "findings": [],
                    "unsupported_claims": [],
                    "missing_evidence": [],
                    "format_attacks": [],
                    "summary": "No adversarial issues found.",
                },
                "publication_decision": {
                    "status": "approved",
                    "reasons": [],
                },
            }
        )


def test_publication_decision_allows_failed_adversarial_when_final_judge_passes():
    from codewiki.src.enduser.review import EnduserReviewArtifact

    artifact = EnduserReviewArtifact.model_validate(
        {
            "document_path": "doc.md",
            "final_document_path": "doc.final.md",
            "catalog_path": "catalog.yaml",
            "template_id": "page-default",
            "judge": {
                "runner": "codex",
                "status": "pass",
                "scores": {
                    "coverage": 4,
                    "evidence_alignment": 4,
                    "format_compliance": 5,
                    "clarity": 4,
                },
                "summary": "Final draft passed.",
                "findings": [],
            },
            "adversarial": {
                "runner": "codex",
                "status": "fail",
                "findings": ["Initial draft was too generic."],
                "unsupported_claims": [],
                "missing_evidence": [],
                "format_attacks": [],
                "summary": "Initial draft had issues.",
            },
            "publication_decision": {
                "status": "approved",
                "reasons": [],
            },
        }
    )

    assert artifact.publication_decision.status == "approved"


def test_codex_adversarial_payload_is_normalized():
    from codewiki.src.enduser.review import AdversarialReview, _normalize_adversarial_response

    response = _normalize_adversarial_response(
        {
            "runner": "codex",
            "status": "pass",
            "findings": [{"type": "positive", "message": "Everything aligns."}],
            "unsupported_claims": [],
            "missing_evidence": [],
            "format_attacks": [],
            "summary": "Everything aligns.",
        }
    )

    review = AdversarialReview.model_validate(response)
    assert review.runner == "codex"
    assert review.status == "pass"
    assert review.findings == ["Everything aligns."]


def test_codex_structured_judge_payload_is_normalized():
    from codewiki.src.enduser.review import JudgeReview, _normalize_judge_response

    response = _normalize_judge_response(
        {
            "result": "pass_with_findings",
            "scores": {
                "evidence_alignment": 82,
                "format_compliance": 95,
                "catalog_coverage": 88,
                "overall": 87,
            },
            "findings": [
                {
                    "severity": "medium",
                    "location": "Steps",
                    "message": "Workflow wording is broader than the catalog supports.",
                }
            ],
            "summary": "The document is mostly consistent with the catalog.",
        }
    )

    review = JudgeReview.model_validate(response)
    assert review.runner == "codex"
    assert review.status == "pass"
    assert review.scores.coverage == 4
    assert review.findings == ["Workflow wording is broader than the catalog supports."]


def test_codex_native_structured_judge_payload_normalizes_fractional_scores():
    from codewiki.src.enduser.review import JudgeReview, _normalize_judge_response

    response = _normalize_judge_response(
        {
            "runner": "codex",
            "status": "pass",
            "scores": {
                "coverage": 0.76,
                "evidence_alignment": 0.52,
                "format_compliance": 0.93,
                "clarity": 0.82,
            },
            "summary": "Judge passed the final draft.",
            "findings": [],
        }
    )

    review = JudgeReview.model_validate(response)
    assert review.scores.coverage == 4
    assert review.scores.evidence_alignment == 3
    assert review.scores.format_compliance == 5
    assert review.scores.clarity == 4


def test_codex_adversarial_unknown_payload_fails_closed():
    from codewiki.src.enduser.review import _normalize_adversarial_response

    with pytest.raises(ValueError, match="unrecognized codex adversarial response shape"):
        _normalize_adversarial_response({"foo": "bar"})


def test_codex_adversarial_unknown_status_falls_back_to_findings():
    from codewiki.src.enduser.review import AdversarialReview, _normalize_adversarial_response

    response = _normalize_adversarial_response(
        {
            "runner": "codex",
            "status": "needs_revision",
            "findings": ["Unsupported workflow claim."],
            "unsupported_claims": [],
            "missing_evidence": [],
            "format_attacks": [],
            "summary": "Issues found.",
        }
    )

    review = AdversarialReview.model_validate(response)
    assert review.status == "fail"


def test_codex_unknown_payload_fails_closed():
    from codewiki.src.enduser.review import _normalize_judge_response

    with pytest.raises(ValueError, match="unrecognized codex response shape"):
        _normalize_judge_response({"foo": "bar"})


def test_build_review_prompt_uses_external_instructions_and_template_contract(tmp_path):
    from codewiki.src.enduser.docs import load_enduser_doc_template
    from codewiki.src.enduser.review import build_review_prompt

    document_path = tmp_path / "guide.md"
    catalog_path = tmp_path / "catalog.yaml"
    document_path.write_text(
        "# Sample\n\n## Purpose\nHi\n\n## Audience\nOps\n\n## Preconditions\n- ok\n\n## Steps\n1. Do it\n\n## Fields\n| Field | Label | Type | Required | Readonly |\n| --- | --- | --- | --- | --- |\n\n## Navigation\n- none\n\n## Evidence\n- `ev.one`: summary\n\n## Review Status\nPending\n",
        encoding="utf-8",
    )
    catalog_path.write_text(
        "pages: []\nfields: []\nevidence: []\nrelations: []\nentities: []\ntransactions: []\n",
        encoding="utf-8",
    )

    prompt = build_review_prompt(
        document_path, catalog_path, load_enduser_doc_template("page-default")
    )

    assert (
        "Review the provided markdown document against the catalog and template contract." in prompt
    )
    assert "## Repository Context" in prompt
    assert "## Template Contract" in prompt
    assert "template_id: page-default" in prompt
    assert "## Output Template" in prompt
    assert "## Catalog Summary" in prompt
    assert "counts:" in prompt
    assert "## Document Markdown" in prompt
    assert "## Catalog YAML" in prompt
    assert "Penalize shallow generic prose when the catalog supports stronger detail." in prompt
    assert "execution_model: codex-cli" in prompt


def test_build_review_prompt_uses_target_repository_root(tmp_path):
    import subprocess

    from codewiki.src.enduser.docs import load_enduser_doc_template
    from codewiki.src.enduser.review import build_review_prompt

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo_root), check=True, capture_output=True)
    docs_dir = repo_root / "docs"
    docs_dir.mkdir()
    document_path = docs_dir / "guide.md"
    catalog_path = docs_dir / "catalog.yaml"
    document_path.write_text(
        "# Sample\n\n## Purpose\nHi\n\n## Audience\nOps\n\n## Preconditions\n- ok\n\n## Steps\n1. Do it\n\n"
        "## Fields\n| Field | Label | Type | Required | Readonly |\n| --- | --- | --- | --- | --- |\n\n"
        "## Navigation\n- none\n\n## Evidence\n- `ev.one`: summary\n\n## Review Status\nPending\n",
        encoding="utf-8",
    )
    catalog_path.write_text(
        "entities: []\npages: []\nfields: []\ntransactions: []\nevidence: []\nrelations: []\n",
        encoding="utf-8",
    )

    prompt = build_review_prompt(
        document_path, catalog_path, load_enduser_doc_template("page-default")
    )

    assert f"repository_root: {repo_root}" in prompt


def test_build_codex_final_draft_prompt_includes_rewrite_context(tmp_path):
    from codewiki.src.enduser.docs import load_enduser_doc_template
    from codewiki.src.enduser.prompting import build_codex_final_draft_prompt
    from codewiki.src.enduser.review import AdversarialReview

    document_path = tmp_path / "guide.md"
    catalog_path = tmp_path / "catalog.yaml"
    document_path.write_text(
        "# Customer Edit User Guide\n\n## Purpose\nDraft.\n\n## Audience\nOps.\n\n## Preconditions\n- Access.\n\n## Steps\n1. Open.\n\n## Fields\n| Field | Label | Type | Required | Readonly |\n| --- | --- | --- | --- | --- |\n| `customer_name` | Customer Name | `text` | yes | no |\n\n## Navigation\n- none\n\n## Evidence\n- `ev.page`: summary\n\n## Review Status\nPending\n",
        encoding="utf-8",
    )
    catalog_path.write_text(
        "entities:\n"
        "  - id: entity.customer\n"
        "    name: Customer\n"
        "    description: Customer master record\n"
        "pages:\n"
        "  - id: page.customers_edit\n"
        "    name: Customer Edit\n"
        "    route: /customers/edit\n"
        "    screenshot_refs: []\n"
        "fields:\n"
        "  - id: field.customers_edit.customer_name\n"
        "    name: customer_name\n"
        "    label: Customer Name\n"
        "    field_type: text\n"
        "    required: true\n"
        "    readonly: false\n"
        "transactions:\n"
        "  - id: txn.customer_update\n"
        "    name: Update Customer\n"
        "    goal: Save customer changes\n"
        "evidence:\n"
        "  - id: ev.page\n"
        "    evidence_type: playwright\n"
        "    source_ref: /customers/edit\n"
        "    summary: Page evidence\n"
        "relations:\n"
        "  - source: page.customers_edit\n"
        "    relation: contains\n"
        "    target: field.customers_edit.customer_name\n"
        "    evidence_ids: [ev.page]\n"
        "  - source: page.customers_edit\n"
        "    relation: participates_in\n"
        "    target: txn.customer_update\n"
        "    evidence_ids: [ev.page]\n"
        "  - source: entity.customer\n"
        "    relation: appears_on\n"
        "    target: page.customers_edit\n"
        "    evidence_ids: [ev.page]\n",
        encoding="utf-8",
    )

    prompt = build_codex_final_draft_prompt(
        document_path,
        catalog_path,
        load_enduser_doc_template("page-default"),
        AdversarialReview(
            runner="codex",
            status="pass",
            findings=["Too generic."],
            unsupported_claims=[],
            missing_evidence=[],
            format_attacks=[],
            summary="Be more specific.",
        ).model_dump(),
    )

    assert "## Rewrite Context" in prompt
    assert "## Repository Context" in prompt
    assert "document_focus:" in prompt
    assert "page_workflow_context:" in prompt
    assert "graph_reasoning_guidance:" in prompt
    assert "Customer Edit" in prompt
    assert "Update Customer" in prompt
    assert "Customer Name" in prompt
