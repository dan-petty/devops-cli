"""Roadmap execution exceptions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.config import ConfigurationError
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

    @property
    def is_configuration_only(self) -> bool:
        """Whether every job failure in the round's cause group was a ConfigurationError."""
        cause = self.__cause__
        if isinstance(cause, BaseExceptionGroup):
            match, rest = cause.split(ConfigurationError)
            return match is not None and rest is None
        return isinstance(cause, ConfigurationError)


class ServiceStoppingError(RoadmapRunError):
    """Raised when a request ends because the Service is stopping (#2753).

    The request budget raises it for a request that would wait for the window: the stop does
    not wait. The round that gets it is not at fault, so it is no failed round of its job.
    """

    error_code = "SERVICE_STOPPING"


class RoadmapImplementError(DevOpsCLIError):
    """Raised when `devops roadmap implement` refuses to start a step, or cannot read its inputs.

    A refused step has made no model request and changed nothing in the checkout.
    """

    error_code = "ROADMAP_IMPLEMENT_REFUSED"


class ImplementEvalError(DevOpsCLIError):
    """Raised when `devops roadmap eval implement` cannot read or use a fixture, or is asked for
    one that does not exist (#3030).

    The command has made no model request and cloned nothing.
    """

    error_code = "ROADMAP_EVAL_REFUSED"


class RoadmapItemChangedError(GitHubOperationError):
    """Raised before a job's field write that would revert a change made since it read the Item.

    The job planned without that change, so writing would revert it (ADR 0002). Nothing is
    written; the next run reads the issue again and plans with the change.
    """

    error_code = "ROADMAP_ITEM_CHANGED"

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
            details=details,
        )


class RoadmapClaimError(DevOpsCLIError):
    """Raised when a claim of a roadmap Item is refused, because another owner holds it or
    because the issue is no Item (#2910).

    Nothing is written. `owner` names the owner that holds the Item, when one does.
    """

    error_code = "ROADMAP_ITEM_CLAIMED"

    def __init__(
        self,
        message: str,
        *,
        owner: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.owner = owner
        super().__init__(message, details={"owner": owner, **(details or {})})


class RoadmapRefineError(DevOpsCLIError):
    """Raised after a refine run in which the model call failed for one or more items.

    Refine skipped each such item and wrote the others first. The message names each skipped
    item with its error's class and schema violation count, never the model's text.
    `readied_count` is the number of items the same run set Ready before it failed.
    """

    error_code = "ROADMAP_REFINE_FAILED"

    def __init__(
        self,
        message: str,
        *,
        failed_items: Sequence[int] = (),
        readied_count: int = 0,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.failed_items = tuple(failed_items)
        self.readied_count = readied_count
        super().__init__(
            message,
            details={
                "failed_items": list(self.failed_items),
                "readied_count": readied_count,
                **(details or {}),
            },
        )


class RoadmapAlternativesError(DevOpsCLIError):
    """Raised after an alternatives run that tried items and checked none of them.

    The job recorded each failure in the job record of its item first (#2949). A run that checks
    at least one item does not raise. The message names each skipped item with its reason, never
    the model's text.
    """

    error_code = "ROADMAP_ALTERNATIVES_FAILED"

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
            details={"failed_items": list(self.failed_items), **(details or {})},
        )


class RoadmapStageError(DevOpsCLIError):
    """Raised after a stage run in which one or more items failed (#2654).

    The job staged each other item first. The message names each failed item and says why,
    never with the model's text; `failed_items` holds their numbers.
    """

    error_code = "ROADMAP_STAGE_FAILED"

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
            details={"failed_items": list(self.failed_items), **(details or {})},
        )


class RoadmapIntakeError(DevOpsCLIError):
    """Raised after an intake round in which the writes failed for one or more candidates.

    Intake skipped each such candidate and wrote the others first (#1443). The message names
    each skipped candidate, by issue number or, for one never filed, by title, with its error's
    class; `failed_items` holds the numbers.
    """

    error_code = "ROADMAP_INTAKE_FAILED"

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
            details={"failed_items": list(self.failed_items), **(details or {})},
        )
