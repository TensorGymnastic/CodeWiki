Review the provided markdown document against the catalog and template contract.

You are running inside the repository root with Codex CLI and may inspect relevant files when the inline artifacts suggest a claim should be checked against the actual codebase.

Return only a JSON object that matches the required schema.

Scoring rules:
- `coverage`: how completely the document reflects supported catalog facts.
- `evidence_alignment`: how well claims are tied to supplied evidence.
- `format_compliance`: whether the document obeys the template contract.
- `clarity`: whether the workflow is understandable and operationally precise.

Evaluation rules:
- Fail the review when the document contains unsupported claims, missing required sections, or broken format rules.
- Findings must be concrete and action-oriented.
- Use the supplied inline document and catalog as the only source of truth.
- Penalize shallow generic prose when the catalog supports stronger detail.
- Reward documents that connect workflow steps, fields, navigation, entities, transactions, and evidence into a coherent operator narrative.
- Use repository inspection sparingly and only to identify direct contradictions, not to force repo-status caveats into the end-user document.
