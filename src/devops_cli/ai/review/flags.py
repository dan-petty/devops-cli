"""Review pipeline stage feature flags and resolver helpers."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class ReviewStageFlags(BaseModel):
    """Feature flags controlling individual stage execution in the review pipeline."""

    model_config = ConfigDict(frozen=True)

    pre_analysis: bool = True
    static_scan: bool = True
    group_analysis: bool = True
    reporting: bool = True

    def any_enabled(self) -> bool:
        """Return True if at least one review stage is enabled."""
        return self.pre_analysis or self.static_scan or self.group_analysis or self.reporting

    def to_dict(self) -> dict[str, bool]:
        """Serialize flags to a dictionary."""
        return {
            "pre_analysis": self.pre_analysis,
            "static_scan": self.static_scan,
            "group_analysis": self.group_analysis,
            "reporting": self.reporting,
        }

    def needs_model(self) -> bool:
        """Return True if any model-driven stage is enabled."""
        return self.group_analysis


def resolve_stage_flags(
    *,
    no_pre_analysis: bool = False,
    pre_analysis_only: bool = False,
    no_static_scan: bool = False,
    static_scan_only: bool = False,
    no_group_analysis: bool = False,
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
        "reporting": reporting_only,
    }
    has_only = any(only_flags.values())

    if has_only:
        return ReviewStageFlags(
            pre_analysis=pre_analysis_only and not no_pre_analysis,
            static_scan=static_scan_only and not no_static_scan,
            group_analysis=False,
            reporting=reporting_only and not no_reporting,
        )

    return ReviewStageFlags(
        pre_analysis=not no_pre_analysis,
        static_scan=not no_static_scan,
        group_analysis=not no_group_analysis,
        reporting=not no_reporting,
    )
