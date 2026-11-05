"""How Ruff resolves `select` and `ignore`, for the checks that read `pyproject.toml` (#2164)."""

from __future__ import annotations

from collections.abc import Sequence


def ruff_enforces(rule: str, select: Sequence[str], ignore: Sequence[str]) -> bool:
    """Report whether Ruff would actually run one rule under a given configuration.

    Ruff selects and ignores by *prefix*, resolving the longest match, so comparing codes
    as literal strings is wrong in both directions. With `ignore = ["B"]` Ruff suppresses
    B017 entirely while a set-difference still reports it enforced -- a test that certifies
    the very rule it is meant to pin. With `select = ["B"]`, the family-level spelling this
    release schedules, the set difference reports B017 missing although Ruff runs it.

    `ALL` selects everything, so it is the least specific match: any explicit ignore beats
    it. A tie goes to ignore, matching Ruff's own resolution.
    """

    def specificity(prefixes: Sequence[str]) -> int | None:
        matches = [len(p) for p in prefixes if p == "ALL" or rule.startswith(p)]
        widened = [
            0 if p == "ALL" else len(p) for p in prefixes if p == "ALL" or rule.startswith(p)
        ]
        return max(widened) if matches else None

    selected = specificity(select)
    if selected is None:
        return False
    ignored = specificity(ignore)
    return ignored is None or ignored < selected


def names_rule(rule: str, code: str) -> bool:
    """Report whether one selector names a rule, by Ruff's prefix matching."""
    return code == "ALL" or rule.startswith(code)
