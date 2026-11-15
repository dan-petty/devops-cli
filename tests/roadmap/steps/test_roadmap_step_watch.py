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
watch: Any = None

try:
    from devops_cli.roadmap.steps.watch import (
        PRVerdict as loaded_PRVerdict,
    )
    from devops_cli.roadmap.steps.watch import (
        WatchState as loaded_WatchState,
    )
    from devops_cli.roadmap.steps.watch import (
        WatchVerdict as loaded_WatchVerdict,
    )
    from devops_cli.roadmap.steps.watch import (
        verdict as loaded_verdict,
    )
    from devops_cli.roadmap.steps.watch import (
        watch as loaded_watch,
    )

    PRVerdict = loaded_PRVerdict
    WatchState = loaded_WatchState
    WatchVerdict = loaded_WatchVerdict
    verdict = loaded_verdict
    watch = loaded_watch
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


def test_watch_verdict_to_json() -> None:
    """WatchVerdict.to_json produces valid JSON with all fields."""
    import json

    v = WatchVerdict(
        verdict=PRVerdict.FAILED,
        check="test",
        failure_class=FailureClass.TEST,
        reason="test failed",
    )
    raw = v.to_json()
    data = json.loads(raw)
    assert data["verdict"] == "failed"
    assert data["check"] == "test"
    assert data["failure_class"] == "test"
    assert data["reason"] == "test failed"


def test_watch_reads_state_and_returns_verdict(
    github_api_and_gh: tuple[Any, Any],
) -> None:
    """watch reads PR status and check runs through the GitHub session."""
    from tests.support.fakes.github import github_json

    api, _gh = github_api_and_gh
    pull_payload = {
        "state": "open",
        "draft": False,
        "merged": False,
        "head": {"sha": "a1b2c3d4e5f6"},
        "base": {"ref": "main"},
    }
    api.route("GET", "/repos/owner/repo/pulls/10", github_json(pull_payload))
    checks_payload = {
        "total_count": 1,
        "check_runs": [
            {
                "name": "test",
                "status": "completed",
                "conclusion": "success",
                "html_url": "https://example.com/check/1",
            }
        ],
    }
    api.route(
        "GET",
        "/repos/owner/repo/commits/a1b2c3d4e5f6/check-runs?per_page=100",
        github_json(checks_payload),
    )
    callback_calls = []
    res = watch(
        "owner/repo",
        10,
        expected_head="a1b2c3d4e5f6",
        block=False,
        status_callback=lambda st, el: callback_calls.append((st, el)),
    )
    assert res.verdict == PRVerdict.READY
    assert len(callback_calls) == 1
    assert callback_calls[0][0].pull == 10


def test_watch_blocking_retries_transient_failure_then_settles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """watch retries transient GitHubOperationError during polling."""
    from devops_cli.core import clock
    from devops_cli.exceptions import GitHubOperationError
    from devops_cli.roadmap.steps import watch as watch_mod

    sleep_calls = []
    monkeypatch.setattr(clock, "sleep", lambda s: sleep_calls.append(s))

    calls = 0

    def fake_read(repo: str, pull: int, expected_head: str | None = None) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise GitHubOperationError("502 Server Error")
        return WatchState(pull=pull, head_sha="1234", checks=(_check("test"),))

    monkeypatch.setattr(watch_mod, "_read_watch_state", fake_read)

    res = watch("owner/repo", 10, timeout=100, interval=5, block=True)
    assert res.verdict == PRVerdict.READY
    assert calls == 2
    assert sleep_calls == [5]


def test_watch_skip_ci_returns_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """watch handles skip ci commits by returning PENDING."""
    from devops_cli.roadmap.steps import watch as watch_mod

    state = WatchState(
        pull=10,
        head_sha="1234",
        commit_message="docs: typo [skip ci]",
        checks=(_check("test"),),
    )
    monkeypatch.setattr(watch_mod, "_read_watch_state", lambda *a, **k: state)

    res = watch("owner/repo", 10, block=True)
    assert res.verdict == PRVerdict.PENDING
    assert "skip ci" in res.reason


def test_watch_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """watch exits with pending verdict when deadline is exceeded."""
    from devops_cli.core import clock
    from devops_cli.roadmap.steps import watch as watch_mod

    state = WatchState(
        pull=10,
        head_sha="1234",
        checks=(_check("test", bucket=CheckBucket.PENDING),),
    )
    monkeypatch.setattr(watch_mod, "_read_watch_state", lambda *a, **k: state)

    times = [0.0, 10.0, 100.0]
    monkeypatch.setattr(clock, "monotonic", lambda: times.pop(0) if times else 200.0)
    monkeypatch.setattr(clock, "sleep", lambda s: None)

    res = watch("owner/repo", 10, timeout=50, interval=10, block=True)
    assert res.verdict == PRVerdict.PENDING
    assert "timed out" in res.reason
