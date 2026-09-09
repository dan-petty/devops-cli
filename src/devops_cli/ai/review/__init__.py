"""AI Code Review subpackage for multi-agent pipeline, verification, patching, and reporting."""

from __future__ import annotations

from devops_cli.ai.review.ast_imports import (
    extract_imports_from_diff,
    extract_imports_from_source,
    group_imports_by_package,
)
from devops_cli.ai.review.chunker import diff_pages, diff_stream_chunks, find_repo_files
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
from devops_cli.ai.review.contract_grounding import (
    format_contract_grounding_for_prompt,
    resolve_grounded_contracts,
)
from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback
from devops_cli.ai.review.flags import ReviewStageFlags, resolve_stage_flags
from devops_cli.ai.review.patching import stage_finding_patch
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.pool import ReviewWorkerPool, TokenBucketRateLimiter
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
    "ReviewWorkerPool",
    "SavedFinding",
    "TokenBucketRateLimiter",
    "auto_record_invalidated_finding",
    "consolidate_duplicate_findings",
    "diff_pages",
    "diff_stream_chunks",
    "export_invalidated_feedback",
    "extract_imports_from_diff",
    "extract_imports_from_source",
    "extract_json_block",
    "find_repo_files",
    "find_similar_hallucinations",
    "format_contract_grounding_for_prompt",
    "group_imports_by_package",
    "is_common_hallucination",
    "load_common_hallucinations",
    "normalize_unicode_text",
    "parse_review_response",
    "register_common_hallucination",
    "resolve_grounded_contracts",
    "resolve_stage_flags",
    "save_common_hallucinations",
    "stage_finding_patch",
]
