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


def ended_by_stop(exc: BaseException) -> bool:
    """Whether `exc` is the error of a request that ended because the Service is stopping
    (`ServiceStoppingError`), or has it as its cause. A group is a stop when each member is: a
    group that holds a real failure is a failure (#2753)."""
    if isinstance(exc, ServiceStoppingError):
        return True
    if isinstance(exc, BaseExceptionGroup):
        return all(ended_by_stop(sub) for sub in exc.exceptions)
    return exc.__cause__ is not None and ended_by_stop(exc.__cause__)


class RoadmapImplementError(DevOpsCLIError):
    """Raised when `devops roadmap implement` refuses to start a step, or cannot read its inputs.

    A refused step has made no model request and changed nothing in the checkout.
    """

    error_code = "ROADMAP_IMPLEMENT_REFUSED"


class OverWindowError(RoadmapImplementError):
    """Raised when the inputs of an implement step measure more than the window allows (#3057)."""

    def __init__(
        self,
        message: str,
        *,
        measured: int,
        limit: int,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.measured = measured
        self.limit = limit
        super().__init__(
            message,
            details={
                "measured": measured,
                "limit": limit,
                **(details or {}),
            },
        )


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


class RoadmapStatusLostError(GitHubOperationError):
    """Raised after a Status write when the issue, read again, holds another Status (#5018).

    Another writer changed the issue between the write and the read, so the Status that the job
    wrote is lost. The next round of the job derives the Status again from the issue as it is.
    """

    error_code = "ROADMAP_STATUS_LOST"

    def __init__(
        self,
        message: str,
        *,
        operation: str = "roadmap.item.write_status",
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


class RoadmapStageDegenerateError(RoadmapStageError):
    """Raised for an item whose plan reply holds a placeholder in every text of the plan (#4204).

    The same request would give the same reply, so the job sends no second request. The error has
    the code of `RoadmapStageError`; the stage metric counts it under the result `degenerate`.
    """


class RoadmapPlanRewriteError(DevOpsCLIError):
    """Raised when `devops roadmap plan-recheck --confirm` refuses to write a rewritten plan (#3556).

    The command checks every file before it writes the first, so a refused run has written nothing.
    """

    error_code = "ROADMAP_PLAN_REWRITE_REFUSED"


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


class RoadmapMcpUnavailableError(DevOpsCLIError):
    """Raised when the MCP server is unavailable at job start (#3221)."""

    error_code = "ROADMAP_MCP_UNAVAILABLE"

    def __init__(
        self,
        url: str,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.url = url
        super().__init__(
            message or f"MCP server at '{url}' is unavailable.",
            details={"url": url, **(details or {})},
        )


class RoadmapReviewError(DevOpsCLIError):
    """Raised when `devops roadmap review run` cannot resolve its window or read git (#4686).

    The review writes no file. The message names the option, the tag, the time or the git command
    that failed.
    """

    error_code = "ROADMAP_REVIEW_FAILED"
