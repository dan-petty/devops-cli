"""AI Code Review subpackage for the multi-agent pipeline, verdicts, and reporting."""

from __future__ import annotations

from devops_cli.ai.review.ast_imports import (
    extract_imports_from_diff,
    extract_imports_from_source,
    group_imports_by_package,
)
from devops_cli.ai.review.category_metrics import (
    CategoryMetric,
    collect_historical_category_metrics,
    compute_category_metrics,
    format_category_baseline_markdown,
    resolve_finding_category,
)
from devops_cli.ai.review.chunker import diff_pages, diff_stream_chunks, find_repo_files
from devops_cli.ai.review.contract_grounding import (
    format_contract_grounding_for_prompt,
    resolve_grounded_contracts,
)
from devops_cli.ai.review.exporter import FeedbackRecord, export_invalidated_feedback
from devops_cli.ai.review.flags import ReviewStageFlags, resolve_stage_flags
from devops_cli.ai.review.pipeline import ReviewPipelineOrchestrator
from devops_cli.ai.review.pool import ReviewWorkerPool, TokenBucketRateLimiter
from devops_cli.ai.review.review_environment import validate_criteria_command
from devops_cli.ai.review.runner import ReviewClients
from devops_cli.ai.review.verdicts import (
    VerifiedBy,
    apply_verdict,
    assert_verdict_invariants,
)
from devops_cli.ai.review_schema import (
    CriterionExecutionResult,
    FileReviewPayload,
    Finding,
    ReviewResult,
    ReviewSessionPayload,
    SavedFinding,
    VerificationCriterion,
    compute_verdict_distributions,
    consolidate_duplicate_findings,
    extract_json_block,
    is_field_discriminating,
    normalize_unicode_text,
    parse_review_response,
)

__all__ = [
    "CategoryMetric",
    "CriterionExecutionResult",
    "FeedbackRecord",
    "FileReviewPayload",
    "Finding",
    "ReviewClients",
    "ReviewPipelineOrchestrator",
    "ReviewResult",
    "ReviewSessionPayload",
    "ReviewStageFlags",
    "ReviewWorkerPool",
    "SavedFinding",
    "TokenBucketRateLimiter",
    "VerificationCriterion",
    "VerifiedBy",
    "apply_verdict",
    "assert_verdict_invariants",
    "collect_historical_category_metrics",
    "compute_category_metrics",
    "compute_verdict_distributions",
    "consolidate_duplicate_findings",
    "diff_pages",
    "diff_stream_chunks",
    "export_invalidated_feedback",
    "extract_imports_from_diff",
    "extract_imports_from_source",
    "extract_json_block",
    "find_repo_files",
    "format_category_baseline_markdown",
    "format_contract_grounding_for_prompt",
    "group_imports_by_package",
    "is_field_discriminating",
    "normalize_unicode_text",
    "parse_review_response",
    "resolve_finding_category",
    "resolve_grounded_contracts",
    "resolve_stage_flags",
    "validate_criteria_command",
]
