Render a user-facing markdown document from the provided catalog.

Follow these rules exactly:
- Use the template contract and output template as hard constraints.
- Preserve the required section headings exactly.
- Ground every claim in the catalog content.
- Prefer precise, operational language over generic prose.
- Do not invent entities, pages, fields, transactions, permissions, or evidence.
- If the catalog represents more than one page, stay within one coherent page scope instead of blending unrelated fields or evidence.
- Do not invent buttons, result tables, save actions, redirects, or navigation targets that are not directly evidenced.
- Treat routes and page access as catalog-derived unless the evidence explicitly confirms runtime behavior.
- Do not imply that users can combine fields, submit criteria, or complete a transaction action unless that interaction is directly evidenced.
- Extract as much supported detail as possible from routes, field metadata, evidence summaries, entity descriptions, transaction goals, and relation structure.

Depth requirements by section:
- `Purpose`: explain the page or workflow in concrete product terms, using page names, routes, entities, and transaction goals when present.
- `Audience`: infer likely operators or business users only when supported by names, workflow context, or catalog wording; otherwise stay neutral.
- `Preconditions`: include access, navigation, or state preconditions only when directly implied by the catalog.
- `Steps`: turn the catalog into a specific workflow with observable page actions, not generic filler. If the catalog does not prove a UI action, prefer a scope-limited step over an invented one.
- `Fields`: preserve the table format and use exact field labels, types, required flags, and readonly state.
- `Navigation`: mention concrete route transitions or explicitly state that no supported navigation target is known.
- `Evidence`: include all relevant evidence ids with short summaries tied to claims elsewhere in the document.
- `Review Status`: keep this section brief and procedural as a current-state line, not a review summary.

Writing rules:
- Prefer explicit nouns from the catalog over pronouns or vague references.
- When the catalog is sparse, say less rather than inventing behavior.
- When multiple records support the same workflow, synthesize them into a coherent operational explanation.
