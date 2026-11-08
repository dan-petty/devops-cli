"""Support helpers for validating Trivy ignore files (.trivyignore)."""

from __future__ import annotations

import re
from datetime import date

# The `exp:` field of a `.trivyignore` entry, in the form that Trivy parses: `exp:YYYY-MM-DD`.
TRIVYIGNORE_EXP = re.compile(r"exp:(?P<day>\d{4}-\d{2}-\d{2})")


def trivyignore_problems(text: str, today: date) -> list[str]:
    """Return one problem for each entry of a `.trivyignore` text that breaks the file's rule.

    The header of the file says that a pinned finding records a reason and an expiration date. An
    entry needs a comment line right above it (the reason) and an `exp:YYYY-MM-DD` field that is
    after `today`: Trivy stops to apply an entry on the day of its date, and it skips an entry
    whose date it cannot parse.
    """
    problems: list[str] = []
    has_reason = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("#"):
            has_reason = True
            continue
        if not line:
            has_reason = False
            continue
        entry, *fields = line.split()
        if not has_reason:
            problems.append(f"line {number}: {entry} has no reason in the comment above it")
        has_reason = False
        exps = [field for field in fields if field.startswith("exp:")]
        match = TRIVYIGNORE_EXP.fullmatch(exps[0]) if exps else None
        if match is None:
            problems.append(f"line {number}: {entry} has no exp:YYYY-MM-DD date")
        elif date.fromisoformat(match["day"]) <= today:
            problems.append(f"line {number}: {entry} expired on {match['day']}")
    return problems
