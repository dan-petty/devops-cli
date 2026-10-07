"""Suppression evaluation from .devops/review.toml and inline markers (#871).

Suppressions read from .devops/review.toml at the base revision or from inline markers.
Markers added by the reviewed change itself do not suppress findings; they stay OPEN
and are marked as 'suppressed by this change'.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import PurePosixPath
from typing import Any

_INLINE_MARKER_REGEX = re.compile(
    r"(?:#|//)\s*(?:noqa|nosec|nosemgrep|no-semgrep)\b", re.IGNORECASE
)


@dataclass(frozen=True)
class ReviewSuppression:
    """A suppression rule loaded from .devops/review.toml."""

    reason: str
    rule: str | None = None
    path: str | None = None
    fingerprint: str | None = None
    expiry: str | None = None

    @property
    def is_expired(self) -> bool:
        """Return True if an expiry date is set and has elapsed."""
        if not self.expiry or not self.expiry.strip():
            return False
        try:
            exp_date = date.fromisoformat(self.expiry.strip())
            return date.today() > exp_date
        except ValueError:
            return False

    def matches(self, *, rule_id: str, path: str, fingerprint: str) -> bool:
        """Return True if this suppression rule matches the target finding."""
        if self.is_expired:
            return False

        if self.fingerprint and self.fingerprint.strip() == fingerprint.strip():
            return True

        rule_match = True
        if self.rule and self.rule.strip():
            rule_match = self.rule.strip().lower() == rule_id.strip().lower()

        path_match = True
        if self.path and self.path.strip():
            clean_path = path.replace("\\", "/").lstrip("/")
            pattern = self.path.strip().replace("\\", "/").lstrip("/")
            posix_path = PurePosixPath(clean_path)
            path_match = posix_path.match(pattern) or posix_path.match(f"*/{pattern}")

        if self.rule or self.path:
            return rule_match and path_match

        return False


def load_review_suppressions(review_config: dict[str, Any]) -> list[ReviewSuppression]:
    """Parse [[suppressions]] list from parsed review.toml dictionary."""
    raw_list = review_config.get("suppressions", [])
    if not isinstance(raw_list, list):
        return []

    suppressions: list[ReviewSuppression] = []
    for entry in raw_list:
        if not isinstance(entry, dict):
            continue
        reason = entry.get("reason", "").strip()
        if not reason:
            continue
        suppressions.append(
            ReviewSuppression(
                reason=reason,
                rule=entry.get("rule"),
                path=entry.get("path"),
                fingerprint=entry.get("fingerprint"),
                expiry=entry.get("expiry"),
            )
        )
    return suppressions


def has_inline_marker(line_text: str) -> bool:
    """Return True if line_text contains an inline suppression marker."""
    return bool(_INLINE_MARKER_REGEX.search(line_text))


def check_inline_marker_in_diff(
    path: str,
    line: int,
    added_diff_lines: set[tuple[str, int]],
    file_lines: Sequence[str],
) -> tuple[bool, bool]:
    """Determine if a line has an inline marker and whether it was added by the change.

    Returns:
        (has_marker, added_by_change)
    """
    if not (1 <= line <= len(file_lines)):
        return False, False
    line_text = file_lines[line - 1]
    if not has_inline_marker(line_text):
        return False, False

    is_added = (path, line) in added_diff_lines
    return True, is_added
