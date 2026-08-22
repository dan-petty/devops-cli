"""Pydantic models for structured code review output.

Re-exported from devops_cli.ai.review_schema.
"""

from __future__ import annotations

from devops_cli.ai.review_schema import (
    _RECOMMENDATION_ALIASES,
    _SEVERITY_RANK,
    _UNICODE_REPLACEMENTS,
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    consolidate_duplicate_findings,
    extract_json_block,
    normalize_unicode_text,
    parse_review_result,
)

__all__ = [
    "FileReviewPayload",
    "Finding",
    "ReviewResult",
    "ReviewSessionPayload",
    "SavedFinding",
    "_RECOMMENDATION_ALIASES",
    "_SEVERITY_RANK",
    "_UNICODE_REPLACEMENTS",
    "consolidate_duplicate_findings",
    "extract_json_block",
    "normalize_unicode_text",
    "parse_review_result",
]
