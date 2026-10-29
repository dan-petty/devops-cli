"""AI Code Review subpackage for the multi-agent pipeline, verdicts, and reporting."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
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
    from devops_cli.ai.review.exporter import (
        FeedbackRecord,
        export_invalidated_feedback,
    )
    from devops_cli.ai.review.flags import (
        ReviewStageFlags,
        resolve_stage_flags,
    )
    from devops_cli.ai.review.pipeline import (
        ReviewPipelineOrchestrator,
    )
    from devops_cli.ai.review.pool import (
        ReviewWorkerPool,
        TokenBucketRateLimiter,
    )
    from devops_cli.ai.review.review_environment import (
        validate_criteria_command,
    )
    from devops_cli.ai.review.runner import (
        ReviewClients,
    )
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
        extract_json_block,
        is_field_discriminating,
        normalize_unicode_text,
        parse_review_response,
    )
    from devops_cli.review.targets import (
        find_repo_files,
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
    "export_invalidated_feedback",
    "extract_imports_from_diff",
    "extract_imports_from_source",
    "extract_json_block",
    "find_repo_files",
    "format_category_baseline_markdown",
    "group_imports_by_package",
    "is_field_discriminating",
    "normalize_unicode_text",
    "parse_review_response",
    "resolve_finding_category",
    "resolve_stage_flags",
    "validate_criteria_command",
]

_ATTR_MAP: dict[str, tuple[str, str]] = {
    "CategoryMetric": ("devops_cli.ai.review.category_metrics", "CategoryMetric"),
    "CriterionExecutionResult": ("devops_cli.ai.review_schema", "CriterionExecutionResult"),
    "FeedbackRecord": ("devops_cli.ai.review.exporter", "FeedbackRecord"),
    "FileReviewPayload": ("devops_cli.ai.review_schema", "FileReviewPayload"),
    "Finding": ("devops_cli.ai.review_schema", "Finding"),
    "ReviewClients": ("devops_cli.ai.review.runner", "ReviewClients"),
    "ReviewPipelineOrchestrator": ("devops_cli.ai.review.pipeline", "ReviewPipelineOrchestrator"),
    "ReviewResult": ("devops_cli.ai.review_schema", "ReviewResult"),
    "ReviewSessionPayload": ("devops_cli.ai.review_schema", "ReviewSessionPayload"),
    "ReviewStageFlags": ("devops_cli.ai.review.flags", "ReviewStageFlags"),
    "ReviewWorkerPool": ("devops_cli.ai.review.pool", "ReviewWorkerPool"),
    "SavedFinding": ("devops_cli.ai.review_schema", "SavedFinding"),
    "TokenBucketRateLimiter": ("devops_cli.ai.review.pool", "TokenBucketRateLimiter"),
    "VerificationCriterion": ("devops_cli.ai.review_schema", "VerificationCriterion"),
    "VerifiedBy": ("devops_cli.ai.review.verdicts", "VerifiedBy"),
    "apply_verdict": ("devops_cli.ai.review.verdicts", "apply_verdict"),
    "assert_verdict_invariants": ("devops_cli.ai.review.verdicts", "assert_verdict_invariants"),
    "collect_historical_category_metrics": (
        "devops_cli.ai.review.category_metrics",
        "collect_historical_category_metrics",
    ),
    "compute_category_metrics": (
        "devops_cli.ai.review.category_metrics",
        "compute_category_metrics",
    ),
    "compute_verdict_distributions": (
        "devops_cli.ai.review_schema",
        "compute_verdict_distributions",
    ),
    "export_invalidated_feedback": ("devops_cli.ai.review.exporter", "export_invalidated_feedback"),
    "extract_imports_from_diff": ("devops_cli.ai.review.ast_imports", "extract_imports_from_diff"),
    "extract_imports_from_source": (
        "devops_cli.ai.review.ast_imports",
        "extract_imports_from_source",
    ),
    "extract_json_block": ("devops_cli.ai.review_schema", "extract_json_block"),
    "find_repo_files": ("devops_cli.review.targets", "find_repo_files"),
    "format_category_baseline_markdown": (
        "devops_cli.ai.review.category_metrics",
        "format_category_baseline_markdown",
    ),
    "group_imports_by_package": ("devops_cli.ai.review.ast_imports", "group_imports_by_package"),
    "is_field_discriminating": ("devops_cli.ai.review_schema", "is_field_discriminating"),
    "normalize_unicode_text": ("devops_cli.ai.review_schema", "normalize_unicode_text"),
    "parse_review_response": ("devops_cli.ai.review_schema", "parse_review_response"),
    "resolve_finding_category": (
        "devops_cli.ai.review.category_metrics",
        "resolve_finding_category",
    ),
    "resolve_stage_flags": ("devops_cli.ai.review.flags", "resolve_stage_flags"),
    "validate_criteria_command": (
        "devops_cli.ai.review.review_environment",
        "validate_criteria_command",
    ),
}


def __getattr__(name: str) -> Any:
    if name in _ATTR_MAP:
        mod_name, attr = _ATTR_MAP[name]
        val = getattr(importlib.import_module(mod_name), attr)
        globals()[name] = val
        return val
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
