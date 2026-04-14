Perform an adversarial review of the provided markdown document.

Return only a JSON object that matches the required review shape.

Attack surface:
- unsupported claims
- missing evidence
- format violations
- wording that overstates what the catalog proves
- generic filler that avoids catalog-specific detail even when the catalog supports it

Rules:
- Fail closed when required sections or hard format rules are broken.
- Prefer precise findings over broad commentary.
- Use the supplied inline document and catalog as the only source of truth.
- Flag shallow wording when a stronger catalog-grounded statement was possible.
