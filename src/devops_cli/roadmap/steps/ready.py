"""The roadmap step `ready`: draft readiness and the single wrapper to mark a pull request ready
(ADR 0021, section 8; #5021).

`mark_ready` asks `draft_readiness` before it sends `gh pr ready`, and sends nothing when the answer
is not ready, so no path marks a draft ready that the one decision refuses (#6123). A caller that
holds the draft that it judged gives it; else `mark_ready` reads the draft with `read_ready_draft`.
Only the `--force` of a person skips the decision.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.exceptions import RoadmapImplementError
from devops_cli.github.check_verdict import CheckVerdictSummary, read_check_runs
from devops_cli.github.client import PullStatus
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

if TYPE_CHECKING:
    from devops_cli.roadmap.implement.implement_pull import Draft
    from devops_cli.roadmap.stores.store import RoadmapStore

logger = logging.getLogger(__name__)


def draft_readiness(draft: Any, extra_checks: Sequence[Callable[[Any], Any]] = ()) -> Any:
    """One function decides when any draft pull request is ready for review (#2916, #5021)."""
    from devops_cli.roadmap.implement.implement_pull import draft_readiness as _draft_readiness

    return _draft_readiness(draft, extra_checks)


def read_ready_draft(
    repo: str,
    pull: int,
    *,
    store: RoadmapStore | None = None,
    status: PullStatus | None = None,
    checks: CheckVerdictSummary | None = None,
) -> Draft:
    """The draft of pull request `pull` of `repo` that `draft_readiness` judges: `read_draft` with
    the check runs of its head. It reads the pull request when `status` is None, and the check runs
    when `checks` is None."""
    from devops_cli.roadmap.implement.implement_pull import read_draft

    client = get_github_session().client
    if status is None:
        status = client.get_pull_status(repo, pull)
    if checks is None:
        owner, name = repo.split("/", 1)
        checks = read_check_runs(owner, name, status.head_sha)
    return read_draft(repo, pull, pull=status, checks=checks, store=store, client=client)


def _check_head(repo: str, pull: int, expected_head: str | None) -> None:
    """Raise `RoadmapImplementError` when the remote head of `pull` is not `expected_head`."""
    if expected_head:
        client = get_github_session().client
        status = client.get_pull_status(repo, pull)
        if status.head_sha != expected_head:
            raise RoadmapImplementError(
                f"PR #{pull} head moved: current {status.head_sha[:12]} does not match "
                f"expected {expected_head[:12]}."
            )


def mark_ready(
    repo: str,
    pull: int,
    expected_head: str | None = None,
    *,
    draft: Draft | None = None,
    force: bool = False,
) -> None:
    """Mark the draft pull request `pull` of `repo` ready for review with `gh pr ready`.

    `draft_readiness` judges `draft` first, or the draft that `read_ready_draft` reads when `draft`
    is None. An answer other than ready raises `RoadmapImplementError` with its reason, and sends
    no `gh pr ready` (#6123). Only the `--force` of a person sets `force`, which skips the decision.
    Then the remote head must equal `expected_head`. Raises `RoadmapImplementError` when the head
    moved or `gh` fails.
    """
    if not force:
        from devops_cli.roadmap.implement.implement_pull import Answer

        judged = draft if draft is not None else read_ready_draft(repo, pull)
        readiness = draft_readiness(judged)
        if readiness.answer is not Answer.READY:
            raise RoadmapImplementError(
                MESSAGES.roadmap.draft_not_ready.format(
                    pull=pull, answer=readiness.answer.value, reason=readiness.reason
                )
            )
    _run_ready(repo, pull, expected_head)


def mark_draft(repo: str, pull: int, expected_head: str | None = None) -> None:
    """Make the pull request `pull` of `repo` a draft again with `gh pr ready --undo`, so the fix
    rows take it and no person merges it (#5969). The head check and the errors are the ones of
    `mark_ready`."""
    _run_ready(repo, pull, expected_head, undo=True)


def _run_ready(repo: str, pull: int, expected_head: str | None, *, undo: bool = False) -> None:
    _check_head(repo, pull, expected_head)
    flags = ["--undo"] if undo else []
    done = run_gh([CONST_GH_CLI, "pr", "ready", str(pull), *flags, "--repo", repo], check=False)
    if done.returncode != 0:
        raw_output = (done.stderr or done.stdout or "").strip()
        output = mask_secrets(raw_output)
        err = RoadmapImplementError(
            MESSAGES.roadmap.implement_stop_ready_failed.format(output=output)
        )
        setattr(err, "output", raw_output)
        raise err
