"""A review answer of three findings, and the replies a model wraps it in (#1312).

The response-repair tests and the consolidation tests read the same answer: as JSON, in a fenced
block, after a Markdown link, and cut off inside its third finding.
"""

from __future__ import annotations

import json
from typing import Any

FINDINGS: list[dict[str, Any]] = [
    {
        "severity": "HIGH",
        "location": f"src/app.py:{line}",
        "title": title,
        "description": "User input reaches the query unchecked.",
        "fix": "Bind the value as a query parameter.",
    }
    for line, title in (
        (10, "SQL injection in search"),
        (24, "Unbounded page size"),
        (31, "Stack trace in error page"),
    )
]
TITLES = [finding["title"] for finding in FINDINGS]
REVIEW = {"findings": FINDINGS}
REVIEW_TEXT = json.dumps(REVIEW, indent=2)
REVIEW_BLOCK = "```json\n" + REVIEW_TEXT + "\n```"
LINK = "See [OWASP A03](https://example.com/owasp-a03) for context.\n\n"
# Cut off inside the third finding, as a reply that runs out of tokens is.
TRUNCATED = REVIEW_TEXT[: REVIEW_TEXT.rindex('"description"')]
