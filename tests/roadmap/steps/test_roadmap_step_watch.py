"""Tests for devops_cli.roadmap.steps.watch: pure verdict function and blocking watch (#5021)."""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.github.check_verdict import CheckBucket, PRCheckItem
from devops_cli.roadmap.failure import FailureClass

PRVerdict: Any = None
WatchState: Any = None
WatchVerdict: Any = None
verdict: Any = None

try:
    from devops_cli.roadmap.steps.watch import (
        PRVerdict as _PRVerdict,
    )
    from devops_cli.roadmap.steps.watch import (
        WatchState as _WatchState,
    )
    from devops_cli.roadmap.steps.watch import (
        WatchVerdict as _WatchVerdict,
    )
    from devops_cli.roadmap.steps.watch import (
        verdict as _verdict,
    )

    PRVerdict = _PRVerdict
    WatchState = _WatchState
    WatchVerdict = _WatchVerdict
    verdict = _verdict
except ImportError:
    pass


@pytest.fixture(autouse=True)
def _check_module_available() -> None:
    if verdict is None:
        pytest.fail("devops_cli.roadmap.steps.watch is not implemented on base branch")


def _check(
    name: str,
    bucket: CheckBucket = CheckBucket.PASS,
    link: str = "https://example.com/check/1",
) -> PRCheckItem:
    return PRCheckItem(
        name=name,
        bucket=bucket,
        status="completed",
        conclusion="success" if bucket == CheckBucket.PASS else "failure",
        link=link,
    )


def test_verdict_pending_when_no_checks() -> None:
    """1. PENDING: No checks reported yet (#4927)."""
    state = WatchState(pull=10, head_sha="a1b2c3d4e5f6", checks=())
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.PENDING


def test_verdict_pending_when_checks_running() -> None:
    """2. PENDING: Checks still running."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        checks=(_check("lint"), _check("test", bucket=CheckBucket.PENDING)),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.PENDING


def test_verdict_ready_when_all_checks_passed() -> None:
    """3. READY: All checks passed, no blockers."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        expected_head="a1b2c3d4e5f6",
        checks=(_check("lint"), _check("test")),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.READY


def test_verdict_failed_when_check_failed() -> None:
    """4. FAILED: A check failed (with classified failure)."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        checks=(_check("lint"), _check("test", bucket=CheckBucket.FAIL)),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.FAILED
    assert result.check == "test"
    assert result.failure_class == FailureClass.TEST


def test_verdict_conflict_when_merge_conflicts() -> None:
    """5. CONFLICT: Merge conflicts with base."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        mergeable=False,
        mergeable_state="dirty",
        checks=(_check("lint"),),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.CONFLICT


def test_verdict_behind_when_behind_base() -> None:
    """6. BEHIND: Behind base branch."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        mergeable_state="behind",
        checks=(_check("lint"),),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.BEHIND


def test_verdict_threads_when_unresolved_threads() -> None:
    """7. THREADS: Unresolved review threads."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        unresolved_threads=2,
        checks=(_check("lint"),),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.THREADS


def test_verdict_merged_when_merged() -> None:
    """8. MERGED: Pull request is merged."""
    state = WatchState(pull=10, head_sha="a1b2c3d4e5f6", merged=True)
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.MERGED


def test_verdict_closed_when_closed() -> None:
    """9. CLOSED: Pull request is closed without being merged."""
    state = WatchState(pull=10, head_sha="a1b2c3d4e5f6", state="closed", merged=False)
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.CLOSED


def test_verdict_head_moved_when_mismatch() -> None:
    """10. HEAD_MOVED: Head does not match expected head."""
    state = WatchState(pull=10, head_sha="111111111111", expected_head="222222222222")
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.HEAD_MOVED


def test_skip_ci_commit_message_gets_no_verdict() -> None:
    """Owner decision 2026-11-13: a head whose commit message holds [skip ci] gets no verdict."""
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        commit_message="docs: update readme [skip ci]",
        checks=(_check("test"),),
    )
    assert verdict(state) is None


def test_failed_shard_check_is_selected_over_join_check() -> None:
    """A failed shard check is preferred over the join check Tests & Coverage."""
    join = _check("Tests & Coverage", bucket=CheckBucket.FAIL)
    shard = _check("Tests & Coverage (shard 3 of 4)", bucket=CheckBucket.FAIL)
    state = WatchState(
        pull=10,
        head_sha="a1b2c3d4e5f6",
        checks=(join, shard),
    )
    result = verdict(state)
    assert result is not None
    assert result.verdict == PRVerdict.FAILED
    assert result.check == "Tests & Coverage (shard 3 of 4)"
