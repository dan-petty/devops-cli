"""The start of the implement job from a workstation (#2913).

A step runs only in the pod of a runner Job (`implement_run.require_runner`). A person who wants
one item implemented does not have that pod, so `devops roadmap implement --item <n> --confirm`
starts a runner Job for the item. The command makes the Job with `start_job` of `devops k8s
run-job`, the code that the supported manual path already uses. This module holds what the
roadmap decides before it: the args of the Job, the options that need the runner, and the check of
the item.

**The check.** It reads the item through the roadmap store only. The pod makes the full plan (the
staged branch, the pull request, the authors of the commits, a stop and its retry), and it needs
a clone and the bot login of the GitHub App, which a workstation does not hold. So the check
refuses what the labels and the Status already show: an issue that is no open item, an item that
an agent or a person claimed, and an item that is neither Ready nor Planned. An item with
`owner/service` passes: the claim of the Service holds nothing against a job, and a running Job of
the repository is the lock that `start_job` checks.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from devops_cli.config.constants import (
    CONST_ROADMAP_STATUS_PLANNED,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.config.defaults import DEFAULT_ROADMAP_IMPLEMENT_LIMIT
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.claim import claimed_by
from devops_cli.roadmap.request_plan import StoreRequests
from devops_cli.roadmap.store import GitHubState, RoadmapStore

_STARTABLE = frozenset({CONST_ROADMAP_STATUS_READY, CONST_ROADMAP_STATUS_PLANNED})


def job_args(repo: str, number: int) -> list[str]:
    """The args of the runner Job for item `number`. The repository is in them, so the pod needs
    no checkout to find it."""
    return ["roadmap", "implement", "--repo", repo, "--item", str(number), "--confirm"]


def run_job_command(repo: str) -> str:
    """The `devops k8s run-job` command that runs the implement job for `repo`, without its
    options. The options of the job go after it."""
    return f"devops k8s run-job --template runner --repo {repo} -- roadmap implement --repo {repo}"


def runner_only_options(
    *, source: Path | None, filters: Sequence[str] | None, limit: int
) -> list[str]:
    """The options that the call gave and that only the job in a runner uses: `--source` is the
    clone of the job, and `--filter` and `--limit` choose the items. `--item` takes the one item
    it names and uses neither the filter nor the limit."""
    given = {
        "--source": source is not None,
        "--filter": bool(filters),
        "--limit": limit != DEFAULT_ROADMAP_IMPLEMENT_LIMIT,
    }
    return [option for option, used in given.items() if used]


def refusal(repo: str, *, options: Sequence[str]) -> str:
    """Why `--confirm` outside a runner starts no Job, and the command that does the work: the
    options that need the runner, else the missing `--item`."""
    texts = MESSAGES.roadmap
    why = (
        texts.implement_outside_why_options.format(options=", ".join(options))
        if options
        else texts.implement_outside_why_item
    )
    return texts.implement_outside_refused.format(why=why, command=run_job_command(repo))


def require_startable(store: RoadmapStore, number: int) -> None:
    """Raise `RoadmapImplementError` unless a runner Job may start for item `number`: an open item
    of the roadmap that neither an agent nor a person claimed, and that is Ready or Planned."""
    texts = MESSAGES.roadmap
    item = store.item(number)
    if item is None:
        raise RoadmapImplementError(texts.implement_outside_not_item.format(number=number))
    if item.state is not GitHubState.OPEN:
        raise RoadmapImplementError(texts.implement_outside_closed.format(number=number))
    if (owner := claimed_by(item)) is not None:
        raise RoadmapImplementError(
            texts.implement_outside_claimed.format(number=number, owner=owner)
        )
    if item.status not in _STARTABLE:
        raise RoadmapImplementError(
            texts.implement_outside_status.format(number=number, status=item.status or "none")
        )


def read_requests(repo: str, number: int) -> list[PlannedRequest]:
    """The requests of `require_startable`, for the dry run: the read of the item."""
    return StoreRequests(repo).issue(f"#{number}")


__all__ = [
    "job_args",
    "read_requests",
    "refusal",
    "require_startable",
    "run_job_command",
    "runner_only_options",
]
