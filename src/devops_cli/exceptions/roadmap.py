"""Roadmap execution exceptions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from devops_cli.config.constants import CONST_ERROR_CODE_ROADMAP_CARD_CHANGED
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubOperationError


class RoadmapRunError(DevOpsCLIError):
    """Raised when one or more roadmap jobs fail during execution."""

    def __init__(
        self,
        message: str,
        *,
        failed_jobs: Sequence[str] = (),
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.failed_jobs = tuple(failed_jobs)
        extra = dict(details) if details is not None else {}
        if failed_jobs and "failed_jobs" not in extra:
            extra["failed_jobs"] = list(failed_jobs)
        super().__init__(message, details=extra, **kwargs)


class RoadmapCardChangedError(GitHubOperationError):
    """Raised before a job's board write that would revert a change made since it read the card.

    The job planned without that change, so writing would revert it (ADR 0002). Nothing is
    written; the next run reads the board again and plans with the change.
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str = "roadmap.item.set_field",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            operation=operation,
            error_code=CONST_ERROR_CODE_ROADMAP_CARD_CHANGED,
            details=details,
        )
