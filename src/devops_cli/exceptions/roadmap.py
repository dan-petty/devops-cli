"""Roadmap execution exceptions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError


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
