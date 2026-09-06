"""AI Code Review subpackage for multi-agent pipeline, verification, patching, and reporting."""

from __future__ import annotations

from devops_cli.ai.review.chunker import diff_pages, find_repo_files
from devops_cli.ai.review.common_hallucinations import (
    CommonHallucinationEntry,
    HallucinationCategory,
    HallucinationMatch,
    auto_record_invalidated_finding,
    find_similar_hallucinations,
    is_common_hallucination,
    load_common_hallucinations,
    register_common_hallucination,
    save_common_hallucinations,
)
from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback
from devops_cli.ai.review.flags import ReviewStageFlags, resolve_stage_flags
from devops_cli.ai.review.patching import stage_finding_patch
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.runner import ReviewClients
from devops_cli.ai.review_schema import (
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    consolidate_duplicate_findings,
    extract_json_block,
    normalize_unicode_text,
    parse_review_response,
)

__all__ = [
    "CommonHallucinationEntry",
    "FeedbackRecord",
    "FileReviewPayload",
    "Finding",
    "HallucinationCategory",
    "HallucinationMatch",
    "ReviewClients",
    "ReviewPipelineOrchestrator",
    "ReviewResult",
    "ReviewSessionPayload",
    "ReviewStageFlags",
    "SavedFinding",
    "auto_record_invalidated_finding",
    "consolidate_duplicate_findings",
    "diff_pages",
    "export_invalidated_feedback",
    "extract_json_block",
    "find_repo_files",
    "find_similar_hallucinations",
    "is_common_hallucination",
    "load_common_hallucinations",
    "normalize_unicode_text",
    "parse_review_response",
    "register_common_hallucination",
    "resolve_stage_flags",
    "save_common_hallucinations",
    "stage_finding_patch",
]
