Revise the provided markdown document using the adversarial review, catalog, and template contract.

You are running inside the repository root with Codex CLI and may inspect relevant files when the catalog graph suggests the document is missing grounded workflow detail.

Return only a JSON object with a single `document` field containing the full revised markdown.

Rewrite rules:
- Preserve the required section headings exactly.
- Address adversarial findings when supported by the catalog.
- Remove unsupported claims instead of softening them.
- Keep the document concise, operational, and evidence-grounded.
- Do not add claims that are absent from the inline catalog.
- Keep page scope strict. Do not blend fields, transactions, evidence, or navigation from unrelated pages.
- Distinguish observed page structure from inferred transaction intent.
- If a transaction goal exists without an explicit UI action, you may describe the goal linkage but not invent the missing action.
- Do not present any claim as code-confirmed unless repository inspection actually confirms it.
- Treat routes as catalog-derived unless repository inspection confirms runtime behavior.
- If repository inspection does not confirm a route or behavior, do not turn that negative finding into end-user prose. Keep the document limited to catalog-derived wording instead.
- Keep `Review Status` procedural. Do not mention prior rewrite history, adversarial revisions, or provenance claims unless they are explicitly provided as evidence.
- `Review Status` should be a short current-state line, not a narrative summary. Good patterns: "Ready for publication review." or "Catalog-scoped draft ready for approval review."
- Prefer richer supported detail over generic phrasing.

Depth expectations:
- Expand `Purpose` to describe the concrete business object, screen, or workflow supported by the catalog.
- Make `Steps` read like a real operator walkthrough using page names, supported field interactions, and only cataloged navigation targets.
- Use the `Fields` section to preserve exact field facts and let the prose sections explain how those fields are used.
- Tie `Navigation` and `Evidence` back to the workflow so the document feels traceable rather than templated.
- When transactions or entities are present, weave them into `Purpose`, `Preconditions`, and `Steps` without inventing unsupported behavior.
- Use the relation graph and repository inspection to sharpen workflow detail when the current draft is too generic.

Unsupported operational actions:
- Do not introduce submit buttons, save buttons, result tables, confirmation messages, redirects, or destination pages unless they are directly supported by the catalog evidence or confirmed in repository code.
- Do not turn a search field into a search-results workflow unless the catalog or repository proves the result state.
- Do not turn an update transaction into a save action unless the catalog or repository proves that action.
- Do not tell the user to combine fields, submit criteria, or execute a search unless that specific interaction is evidenced.
- When the catalog only proves field presence plus transaction intent, prefer wording like "The page provides..." or "Use this field for the cataloged goal..." over stronger imperative step claims.
- Do not mark the document as approved, approval-ready, or reviewed-complete in `Review Status`. Prefer neutral current-state wording such as "Draft; not yet approved."

Editing strategy:
- Replace generic filler sentences first.
- Prefer merging overlapping facts into one sharper sentence instead of adding verbosity.
- If the catalog is thin, produce a narrow but precise document.
