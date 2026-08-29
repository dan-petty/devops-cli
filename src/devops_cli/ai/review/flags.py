"""Review pipeline stage feature flags and resolver helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ReviewStageFlags:
    """Feature flags controlling individual stage execution in the review pipeline."""

    pre_analysis: bool = True
    static_scan: bool = True
    persona_review: bool = True
    verification: bool = True
    reranking: bool = True
    reporting: bool = True

    def any_enabled(self) -> bool:
        """Return True if at least one review stage is enabled."""
        return (
            self.pre_analysis
            or self.static_scan
            or self.persona_review
            or self.verification
            or self.reranking
            or self.reporting
        )

    def to_dict(self) -> dict[str, bool]:
        """Serialize flags to a dictionary."""
        return {
            "pre_analysis": self.pre_analysis,
            "static_scan": self.static_scan,
            "persona_review": self.persona_review,
            "verification": self.verification,
            "reranking": self.reranking,
            "reporting": self.reporting,
        }


def resolve_stage_flags(
    *,
    no_pre_analysis: bool = False,
    pre_analysis_only: bool = False,
    no_static_scan: bool = False,
    static_scan_only: bool = False,
    no_persona_review: bool = False,
    persona_review_only: bool = False,
    no_verification: bool = False,
    verification_only: bool = False,
    no_reranking: bool = False,
    reranking_only: bool = False,
    no_reporting: bool = False,
    reporting_only: bool = False,
    **kwargs: Any,
) -> ReviewStageFlags:
    """Resolve stage feature flags from CLI options.

    Precedence rules:
    1. If any '--<stage>-only' flag is True, all unspecified stages default to False.
    2. If '--no-<stage>' is True, that stage is set to False.
    3. Otherwise, all stages default to True.
    """
    only_flags = {
        "pre_analysis": pre_analysis_only,
        "static_scan": static_scan_only,
        "persona_review": persona_review_only,
        "verification": verification_only,
        "reranking": reranking_only,
        "reporting": reporting_only,
    }
    has_only = any(only_flags.values())

    if has_only:
        return ReviewStageFlags(
            pre_analysis=pre_analysis_only and not no_pre_analysis,
            static_scan=static_scan_only and not no_static_scan,
            persona_review=persona_review_only and not no_persona_review,
            verification=verification_only and not no_verification,
            reranking=reranking_only and not no_reranking,
            reporting=reporting_only and not no_reporting,
        )

    return ReviewStageFlags(
        pre_analysis=not no_pre_analysis,
        static_scan=not no_static_scan,
        persona_review=not no_persona_review,
        verification=not no_verification,
        reranking=not no_reranking,
        reporting=not no_reporting,
    )
