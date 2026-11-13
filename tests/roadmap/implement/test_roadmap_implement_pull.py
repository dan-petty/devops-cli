"""The implement job watch reads the checks of its pull request as check runs only (#2877).

The App token holds no `statuses` permission, which the commit status endpoint needs. The watch
reads check runs only, so a refusal of the status endpoint does not stop the item. Git runs for
real on a clone with an `origin`; GitHub's REST API and `gh` are faked at their edges.
"""

from __future__ import annotations

import pytest

from devops_cli.roadmap.implement.implement_pull import WatchKind, watch_pull
from tests.support.fakes.process import ProcessAnswer
from tests.support.roadmap_implement import BRANCH, FAIL, PULL, JobWorld
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

_FORBIDDEN = ProcessAnswer(
    returncode=1, stderr="gh: Resource not accessible by integration (HTTP 403)"
)


def _status_reads(world: JobWorld) -> list[str]:
    """Each gh command whose arguments name the commit status endpoint of a head commit."""
    return [
        " ".join(call.argv)
        for call in world.programs.calls
        if "/commits/" in " ".join(call.argv) and "/status" in " ".join(call.argv)
    ]


def _head(world: JobWorld) -> str:
    """The tip of the staged branch on `origin`, the head the watch settles on."""
    return world.repo.origin_git("rev-parse", BRANCH)


def test_the_watch_of_passed_check_runs_sends_no_status_read(job_world: JobWorld) -> None:
    """A passed check run is ready, and a refusal of the status endpoint does not stop the item."""
    job_world.pull._answer("/status", _FORBIDDEN)
    watch = watch_pull(STAGE_REPO, PULL, _head(job_world))
    assert watch.kind is WatchKind.READY
    assert _status_reads(job_world) == []


def test_the_watch_of_a_failed_check_run_sends_no_status_read(job_world: JobWorld) -> None:
    """A failed check run reports that check, with no request to the status endpoint."""
    job_world.pull._answer("/status", _FORBIDDEN)
    job_world.pull.runs = [[FAIL]]
    watch = watch_pull(STAGE_REPO, PULL, _head(job_world))
    assert watch.kind is WatchKind.FAILED
    assert _status_reads(job_world) == []


def test_the_watch_names_the_failed_shard_and_not_the_join_check(job_world: JobWorld) -> None:
    """The join check fails when a shard fails, and its log holds no test output."""
    join = {**FAIL, "html_url": f"https://github.com/{STAGE_REPO}/actions/runs/101/job/1"}
    shard = {
        **FAIL,
        "name": "Tests & Coverage (shard 2 of 4)",
        "html_url": f"https://github.com/{STAGE_REPO}/actions/runs/101/job/2",
    }
    job_world.pull.runs = [[join, shard]]
    watch = watch_pull(STAGE_REPO, PULL, _head(job_world))
    assert watch.kind is WatchKind.FAILED
    assert watch.check is not None
    assert watch.check.name == "Tests & Coverage (shard 2 of 4)"
    assert "shard 2 of 4" in watch.reason


def test_a_pull_request_closed_without_a_merge_stops_the_watch(job_world: JobWorld) -> None:
    """A pull request closed while the job runs can no longer become ready, so the watch stops the
    item and does not call it ready (#2530)."""
    job_world.pull.closed = True
    watch = watch_pull(STAGE_REPO, PULL, _head(job_world))
    assert (watch.kind, watch.reason) == (
        WatchKind.STOPPED,
        "The pull request was merged or closed while the job ran.",
    )
