#!/usr/bin/env python3
"""Deterministic codex shim for Makefile sample review runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _output_path(argv: list[str]) -> Path:
    if "--output-last-message" not in argv:
        raise SystemExit("missing --output-last-message")
    return Path(argv[argv.index("--output-last-message") + 1])


def main() -> int:
    prompt = sys.stdin.read()
    output_path = _output_path(sys.argv)

    if "Perform an adversarial review of the provided markdown document." in prompt:
        payload = {
            "runner": "codex",
            "status": "pass",
            "findings": [],
            "unsupported_claims": [],
            "missing_evidence": [],
            "format_attacks": [],
            "summary": "Sample review found no blocking issues.",
        }
    elif "## Adversarial Review" in prompt:
        payload = {
            "document": (
                "# Customer Search User Guide\n\n"
                "## Purpose\n"
                "Customer Search supports the cataloged Search Customer workflow.\n\n"
                "## Audience\n"
                "Users who need the Customer Search page.\n\n"
                "## Preconditions\n"
                "- Use this guide only for Customer Search.\n\n"
                "## Steps\n"
                "1. Open Customer Search at /customers/search.\n"
                "2. Review Customer Name and Customer Status as the supported page inputs.\n"
                "3. Use the page within the cataloged Search Customer goal.\n\n"
                "## Fields\n"
                "| Field | Label | Type | Required | Readonly |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| `customer_name` | Customer Name | `text` | no | no |\n"
                "| `customer_status` | Customer Status | `select` | no | no |\n\n"
                "## Navigation\n"
                "- Cataloged route: `/customers/search`\n"
                "- No cataloged navigation targets are linked from this page.\n\n"
                "## Evidence\n"
                "- `ev.playwright.page.customers_search`: Playwright crawl evidence for Customer Search.\n"
                "- `ev.screenshot.page.customers_search`: Screenshot evidence for Customer Search.\n\n"
                "## Review Status\n"
                "Draft; not yet approved.\n"
            )
        }
    else:
        payload = {
            "runner": "codex",
            "status": "pass",
            "scores": {
                "coverage": 4,
                "evidence_alignment": 5,
                "format_compliance": 5,
                "clarity": 4,
            },
            "summary": "Sample final draft passed review.",
            "findings": [],
        }

    output_path.write_text(json.dumps(payload), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
