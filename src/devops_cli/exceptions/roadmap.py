"""Roadmap execution exceptions."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_ROADMAP_CARD_CHANGED,
    CONST_ERROR_CODE_ROADMAP_REFINE_FAILED,
    CONST_GRAPHQL_REFUSAL_RESET_KEY,
)
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.git import GitHubOperationError


class RoadmapRunError(DevOpsCLIError):
    """Raised when one or more roadmap jobs fail during execution.

    `reset_at` is the earliest reset a failed job's GraphQL budget refusal named, None when no
    job was refused; the Service starts no round before it (#1400).
    """

    def __init__(
        self,
        message: str,
        *,
        failed_jobs: Sequence[str] = (),
        reset_at: datetime | None = None,
        details: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.failed_jobs = tuple(failed_jobs)
        self.reset_at = reset_at
        extra = dict(details) if details is not None else {}
        if failed_jobs and "failed_jobs" not in extra:
            extra["failed_jobs"] = list(failed_jobs)
        if reset_at is not None:
            extra[CONST_GRAPHQL_REFUSAL_RESET_KEY] = reset_at.isoformat()
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


class RoadmapRefineError(DevOpsCLIError):
    """Raised after a refine run in which the model call failed for one or more items.

    Refine skipped each such item and wrote the others first. The message names each skipped
    item with its error's class and schema violation count, never the model's text.
    """

    def __init__(
        self,
        message: str,
        *,
        failed_items: Sequence[int] = (),
        details: dict[str, Any] | None = None,
    ) -> None:
        self.failed_items = tuple(failed_items)
        super().__init__(
            message,
            error_code=CONST_ERROR_CODE_ROADMAP_REFINE_FAILED,
            details={"failed_items": list(self.failed_items), **(details or {})},
        )
