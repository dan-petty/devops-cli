"""AI Code Review subpackage for multi-agent pipeline, verification, patching, and reporting."""

from __future__ import annotations

from devops_cli.ai.review.chunker import _diff_pages, _find_repo_files
from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback
from devops_cli.ai.review.patching import stage_finding_patch
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import ReviewClients, _resolve_review_clients
from devops_cli.ai.review.schema import (
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
    "FeedbackRecord",
    "FileReviewPayload",
    "Finding",
    "ReviewClients",
    "ReviewPipelineOrchestrator",
    "ReviewResult",
    "ReviewSessionPayload",
    "SavedFinding",
    "_diff_pages",
    "_find_repo_files",
    "_resolve_review_clients",
    "consolidate_duplicate_findings",
    "export_invalidated_feedback",
    "extract_json_block",
    "normalize_unicode_text",
    "parse_review_result",
    "stage_finding_patch",
]
