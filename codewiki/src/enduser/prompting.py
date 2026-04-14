"""Prompt composition helpers for enduser documentation workflows."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path
import subprocess

import yaml

from codewiki.src.enduser.docs import (
    EnduserDocTemplate,
    build_enduser_doc_scope,
    infer_enduser_document_page_id,
)
from codewiki.src.enduser.io import load_enduser_catalog


def _load_prompt(name: str) -> str:
    return files("codewiki").joinpath("prompts", "enduser", name).read_text(encoding="utf-8").strip()


def _markdown_block(title: str, body: str, fence: str) -> str:
    return f"## {title}\n```{fence}\n{body.strip()}\n```"


def _template_contract(template: EnduserDocTemplate) -> str:
    return yaml.safe_dump(
        {
            "template_id": template.template_id,
            "required_sections": template.required_sections,
            "rules": {
                "steps_must_be_numbered": template.steps_must_be_numbered,
                "fields_must_be_table": template.fields_must_be_table,
                "evidence_requires_ids": template.evidence_requires_ids,
            },
            "strategy": {
                "document_kind": template.document_kind,
                "emphasize_verification": template.emphasize_verification,
                "mention_scope_limits": template.mention_scope_limits,
            },
        },
        sort_keys=False,
    ).strip()


def resolve_repository_root(*paths: Path | str) -> Path:
    resolved_paths = [Path(path).resolve() for path in paths]
    for path in resolved_paths:
        probe = path if path.is_dir() else path.parent
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=str(probe),
                check=True,
                capture_output=True,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
        root = completed.stdout.strip()
        if root:
            return Path(root).resolve()

    if not resolved_paths:
        return Path.cwd().resolve()
    first_path = resolved_paths[0]
    return (first_path if first_path.is_dir() else first_path.parent).resolve()


def _repository_context(repository_root: Path) -> str:
    return yaml.safe_dump(
        {
            "repository_root": str(repository_root),
            "execution_model": "codex-cli",
            "codebase_access": [
                "The agent is running in the repository root and may inspect relevant files.",
                "Use the inline catalog and document as primary artifacts, then use repository inspection only to verify claims, not to invent missing UI behavior.",
                "Prefer code paths, routes, handlers, validations, and persistence logic that align with the selected page scope.",
                "If repository inspection does not confirm a behavior, keep the wording catalog-derived rather than code-confirmed.",
                "Do not surface negative repository-inspection findings inside the end-user document unless the task explicitly asks for repo validation notes.",
            ],
        },
        sort_keys=False,
    ).strip()


def _resolve_scope(catalog_path: Path | str, document_path: Path | str | None = None):
    catalog = load_enduser_catalog(catalog_path)
    selection_method = "catalog-default"
    page_id = None

    if document_path is not None:
        markdown = Path(document_path).read_text(encoding="utf-8")
        page_id = infer_enduser_document_page_id(markdown, catalog)
        if page_id is not None:
            selection_method = "document-inferred"

    try:
        scope = build_enduser_doc_scope(catalog, page_id=page_id)
    except ValueError:
        return catalog, None, {"selection_method": "unresolved", "selected_page_id": None}

    return catalog, scope, {"selection_method": selection_method, "selected_page_id": scope.page.id}


def _catalog_summary(catalog_path: Path | str, document_path: Path | str | None = None) -> str:
    catalog, scope, scope_meta = _resolve_scope(catalog_path, document_path=document_path)
    if scope is None:
        relation_items = [
            {
                "source": relation.source,
                "relation": relation.relation,
                "target": relation.target,
                "evidence_ids": relation.evidence_ids,
            }
            for relation in catalog.relations[:20]
        ]
        return yaml.safe_dump(
            {
                "scope": scope_meta,
                "counts": {
                    "entities": len(catalog.entities),
                    "pages": len(catalog.pages),
                    "fields": len(catalog.fields),
                    "transactions": len(catalog.transactions),
                    "evidence": len(catalog.evidence),
                    "relations": len(catalog.relations),
                },
                "pages": [
                    {
                        "id": page.id,
                        "name": page.name,
                        "route": page.route,
                        "screenshots": page.screenshot_refs,
                    }
                    for page in catalog.pages[:10]
                ],
                "relations": relation_items,
            },
            sort_keys=False,
        ).strip()

    navigation_targets = [page for page in scope.related_pages if page.id != scope.page.id]
    return yaml.safe_dump(
        {
            "scope": scope_meta,
            "selected_page": {
                "id": scope.page.id,
                "name": scope.page.name,
                "route": scope.page.route,
                "screenshots": scope.page.screenshot_refs,
            },
            "counts": {
                "pages": len(scope.related_pages),
                "fields": len(scope.fields),
                "transactions": len(scope.transactions),
                "entities": len(scope.entities),
                "evidence": len(scope.evidence),
                "relations": len(scope.relations),
            },
            "fields": [
                {
                    "id": field.id,
                    "name": field.name,
                    "label": field.label,
                    "field_type": field.field_type,
                    "required": field.required,
                    "readonly": field.readonly,
                }
                for field in scope.fields
            ],
            "transactions": [
                {
                    "id": transaction.id,
                    "name": transaction.name,
                    "goal": transaction.goal,
                }
                for transaction in scope.transactions
            ],
            "entities": [
                {
                    "id": entity.id,
                    "name": entity.name,
                    "description": entity.description,
                }
                for entity in scope.entities
            ],
            "navigation_targets": [
                {
                    "id": page.id,
                    "name": page.name,
                    "route": page.route,
                }
                for page in navigation_targets
            ],
            "evidence": [
                {
                    "id": evidence.id,
                    "evidence_type": evidence.evidence_type,
                    "summary": evidence.summary,
                    "source_ref": evidence.source_ref,
                }
                for evidence in scope.evidence
            ],
            "relations": [
                {
                    "source": relation.source,
                    "relation": relation.relation,
                    "target": relation.target,
                    "evidence_ids": relation.evidence_ids,
                }
                for relation in scope.relations
            ],
        },
        sort_keys=False,
    ).strip()


def _rewrite_context(catalog_path: Path | str, document_path: Path | str | None = None) -> str:
    catalog, scope, scope_meta = _resolve_scope(catalog_path, document_path=document_path)
    if scope is None:
        return yaml.safe_dump(
            {
                "scope": scope_meta,
                "rewrite_priority": [
                    "Resolve page scope before expanding workflow language.",
                    "Fail closed on unsupported actions when page inference is ambiguous.",
                ],
            },
            sort_keys=False,
        ).strip()

    navigation_targets = [page for page in scope.related_pages if page.id != scope.page.id]
    return yaml.safe_dump(
        {
            "scope": scope_meta,
            "document_focus": {
                "page_name": scope.page.name,
                "page_route": scope.page.route,
                "field_labels": [field.label for field in scope.fields],
                "transaction_names": [transaction.name for transaction in scope.transactions],
                "entity_names": [entity.name for entity in scope.entities],
                "rewrite_priority": [
                    "Keep the document inside the selected page scope.",
                    "Treat page structure, linked transactions, and linked entities as different evidence layers.",
                    "Prefer explicit scope limits over plausible but unsupported workflow prose.",
                    "If the catalog does not show a button, result set, save action, or destination, say less.",
                ],
            },
            "page_workflow_context": {
                "selected_page": {
                    "id": scope.page.id,
                    "name": scope.page.name,
                    "route": scope.page.route,
                },
                "fields_on_page": [
                    {
                        "id": field.id,
                        "name": field.name,
                        "label": field.label,
                        "field_type": field.field_type,
                        "required": field.required,
                        "readonly": field.readonly,
                    }
                    for field in scope.fields
                ],
                "transactions_on_page": [
                    {
                        "id": transaction.id,
                        "name": transaction.name,
                        "goal": transaction.goal,
                    }
                    for transaction in scope.transactions
                ],
                "entities_reachable_from_transactions": [
                    {
                        "id": entity.id,
                        "name": entity.name,
                        "description": entity.description,
                    }
                    for entity in scope.entities
                ],
                "navigation_targets": [
                    {
                        "id": page.id,
                        "name": page.name,
                        "route": page.route,
                    }
                    for page in navigation_targets
                ],
                "evidence_for_scope": [
                    {
                        "id": evidence.id,
                        "summary": evidence.summary,
                        "evidence_type": evidence.evidence_type,
                        "source_ref": evidence.source_ref,
                    }
                    for evidence in scope.evidence
                ],
            },
            "graph_reasoning_guidance": {
                "preferred_walks": [
                    "page -> contains -> field",
                    "page -> participates_in -> transaction",
                    "transaction -> updates -> entity",
                    "page -> navigates_to -> page",
                ],
                "disallowed_inference_patterns": [
                    "field presence -> submit button",
                    "transaction goal -> save button",
                    "search page -> result table",
                    "route existence -> cross-page navigation",
                ],
                "rewrite_goal": "Use the selected page subgraph to produce a narrow, supportable user document.",
            },
        },
        sort_keys=False,
    ).strip()


def build_generation_prompt(catalog_yaml: str, template: EnduserDocTemplate) -> str:
    return "\n\n".join(
        [
            _load_prompt("base_generation.md"),
            _markdown_block("Template Contract", _template_contract(template), "yaml"),
            _markdown_block("Output Template", template.body_template, "markdown"),
            _markdown_block("Catalog YAML", catalog_yaml, "yaml"),
        ]
    )


def build_codex_judge_prompt(document_path: Path | str, catalog_path: Path | str, template: EnduserDocTemplate) -> str:
    repository_root = resolve_repository_root(document_path, catalog_path)
    return "\n\n".join(
        [
            _load_prompt("codex_judge.md"),
            _markdown_block("Repository Context", _repository_context(repository_root), "yaml"),
            _markdown_block("Template Contract", _template_contract(template), "yaml"),
            _markdown_block("Output Template", template.body_template, "markdown"),
            _markdown_block("Document Path", str(Path(document_path)), "text"),
            _markdown_block("Catalog Path", str(Path(catalog_path)), "text"),
            _markdown_block("Catalog Summary", _catalog_summary(catalog_path, document_path=document_path), "yaml"),
            _markdown_block("Document Markdown", Path(document_path).read_text(encoding="utf-8"), "markdown"),
            _markdown_block("Catalog YAML", Path(catalog_path).read_text(encoding="utf-8"), "yaml"),
        ]
    )


def build_codex_final_draft_prompt(
    document_path: Path | str,
    catalog_path: Path | str,
    template: EnduserDocTemplate,
    adversarial_review: dict,
) -> str:
    repository_root = resolve_repository_root(document_path, catalog_path)
    return "\n\n".join(
        [
            _load_prompt("codex_rewrite.md"),
            _markdown_block("Repository Context", _repository_context(repository_root), "yaml"),
            _markdown_block("Template Contract", _template_contract(template), "yaml"),
            _markdown_block("Output Template", template.body_template, "markdown"),
            _markdown_block(
                "Adversarial Review",
                yaml.safe_dump(adversarial_review, sort_keys=False).strip(),
                "yaml",
            ),
            _markdown_block("Document Path", str(Path(document_path)), "text"),
            _markdown_block("Catalog Path", str(Path(catalog_path)), "text"),
            _markdown_block("Rewrite Context", _rewrite_context(catalog_path, document_path=document_path), "yaml"),
            _markdown_block("Catalog Summary", _catalog_summary(catalog_path, document_path=document_path), "yaml"),
            _markdown_block("Document Markdown", Path(document_path).read_text(encoding="utf-8"), "markdown"),
            _markdown_block("Catalog YAML", Path(catalog_path).read_text(encoding="utf-8"), "yaml"),
        ]
    )


def build_codex_adversarial_prompt(
    document_path: Path | str,
    catalog_path: Path | str,
    template: EnduserDocTemplate,
) -> str:
    repository_root = resolve_repository_root(document_path, catalog_path)
    return "\n\n".join(
        [
            _load_prompt("codex_adversarial.md"),
            _markdown_block("Repository Context", _repository_context(repository_root), "yaml"),
            _markdown_block("Template Contract", _template_contract(template), "yaml"),
            _markdown_block("Output Template", template.body_template, "markdown"),
            _markdown_block("Document Path", str(Path(document_path)), "text"),
            _markdown_block("Catalog Path", str(Path(catalog_path)), "text"),
            _markdown_block("Rewrite Context", _rewrite_context(catalog_path, document_path=document_path), "yaml"),
            _markdown_block("Catalog Summary", _catalog_summary(catalog_path, document_path=document_path), "yaml"),
            _markdown_block("Document Markdown", Path(document_path).read_text(encoding="utf-8"), "markdown"),
            _markdown_block("Catalog YAML", Path(catalog_path).read_text(encoding="utf-8"), "yaml"),
        ]
    )


__all__ = [
    "build_codex_adversarial_prompt",
    "build_codex_final_draft_prompt",
    "build_codex_judge_prompt",
    "build_generation_prompt",
    "resolve_repository_root",
]
