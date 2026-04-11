import pytest


def test_review_artifact_requires_codex_judge_and_opencode_adversarial_sections():
    from codewiki.src.enduser.review import EnduserReviewArtifact

    artifact = EnduserReviewArtifact.model_validate(
        {
            "document_path": "doc.md",
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
                "runner": "opencode",
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
    assert artifact.adversarial.runner == "opencode"
    assert artifact.publication_decision.status == "approved"


def test_publication_decision_rejects_failed_reviews():
    from codewiki.src.enduser.review import EnduserReviewArtifact

    with pytest.raises(ValueError, match="publication decision"):
        EnduserReviewArtifact.model_validate(
            {
                "document_path": "doc.md",
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
                    "runner": "opencode",
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
