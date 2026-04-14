Perform an adversarial review of the provided markdown document.

You are running inside the repository root with Codex CLI and may inspect relevant files when the inline catalog or document suggests a claim should be verified against the codebase.

Return only a JSON object that matches the required schema.

Adversarial goals:
- find unsupported claims
- find missing evidence
- find format violations
- find generic wording that ignores stronger graph-supported detail
- use repository inspection only when needed to catch direct contradictions between the document and the codebase

Rules:
- Treat the inline catalog graph as the primary structural map of the workflow.
- Use the relation graph to reason about page -> field -> transaction -> entity paths.
- Do not require the document to mention that a route or action is "not code-confirmed"; absence of code confirmation is reviewer context, not end-user content.
- When repository inspection disagrees with the document, report the contradiction clearly, but prefer catalog-derived phrasing over repo-status commentary in the document itself.
- Fail closed when required sections or hard format rules are broken.
- Findings must be specific and actionable.
