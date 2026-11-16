"""The roadmap step `ready`: draft readiness and the single wrapper to mark a pull request ready
(ADR 0021, section 8; #5021)."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.exceptions import RoadmapImplementError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.security.sanitizer import mask_secrets

logger = logging.getLogger(__name__)


def draft_readiness(draft: Any, extra_checks: Sequence[Callable[[Any], Any]] = ()) -> Any:
    """One function decides when any draft pull request is ready for review (#2916, #5021)."""
    from devops_cli.roadmap.implement.implement_pull import draft_readiness as _draft_readiness

    return _draft_readiness(draft, extra_checks)


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
) -> None:
    """Mark the draft pull request `pull` of `repo` ready for review with `gh pr ready`.

    Checks that the remote head equals `expected_head` before marking ready.
    Raises `RoadmapImplementError` when head moved or `gh` fails.
    """
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
