"""Unit tests for GitHub rate limiter, pacing, backoff, and caching subsystem."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from devops_cli.github.rate_limiter import (
    GitHubRateLimiter,
    get_github_rate_limiter,
    reset_github_rate_limiter,
    run_gh,
)


@pytest.fixture(autouse=True)
def isolate_rate_limiter():
    """Ensure global rate limiter singleton is reset before and after each test."""
    reset_github_rate_limiter()
    yield
    reset_github_rate_limiter()


def test_rate_limiter_pacing() -> None:
    """Verify rate limiter enforces minimum inter-request interval."""
    limiter = GitHubRateLimiter(min_interval=0.05)
    t0 = time.perf_counter()
    limiter.acquire()
    limiter.acquire()
    elapsed = time.perf_counter() - t0
    assert elapsed >= 0.045, f"Expected pacing delay >= 0.045s, got {elapsed}s"


def test_rate_limiter_quota_warning() -> None:
    """Verify rate limiter detects low quota and returns warning state."""
    limiter = GitHubRateLimiter()
    assert limiter.is_quota_low(remaining=1000) is False
    assert limiter.is_quota_low(remaining=50) is True
    assert limiter.is_quota_critical(remaining=50) is False
    assert limiter.is_quota_critical(remaining=10) is True


def test_rate_limiter_backoff_calculation() -> None:
    """Verify exponential backoff with jitter on secondary rate limits."""
    limiter = GitHubRateLimiter()
    err_secondary = "GraphQL: API rate limit already exceeded for user ID 7726889."
    assert limiter.is_rate_limit_error(err_secondary) is True

    delay_1 = limiter.calculate_backoff_delay(err_secondary, attempt=1)
    delay_2 = limiter.calculate_backoff_delay(err_secondary, attempt=2)
    assert 0.5 <= delay_1 <= 3.0
    assert delay_2 > delay_1

    non_rate_err = "Error: repository not found"
    assert limiter.is_rate_limit_error(non_rate_err) is False
    assert limiter.calculate_backoff_delay(non_rate_err, attempt=1) == 0.0


def test_rate_limiter_ephemeral_cache() -> None:
    """Verify ephemeral read cache stores and returns data within TTL."""
    limiter = GitHubRateLimiter()
    key = "gh:rate_limit"
    assert limiter.get_cached(key) is None

    limiter.set_cached(key, '{"resources": {}}', ttl=1.0)
    assert limiter.get_cached(key) == '{"resources": {}}'

    time.sleep(1.05)
    assert limiter.get_cached(key) is None


def test_run_gh_cached_read() -> None:
    """Verify run_gh avoids subprocess execution when cached result is present."""
    limiter = get_github_rate_limiter()
    limiter.clear_cache()

    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "rate_limit"],
            returncode=0,
            stdout='{"resources": {"core": {"remaining": 5000}}}',
            stderr="",
        )
        res1 = run_gh(["api", "rate_limit"], use_cache=True, cache_ttl=5.0)
        assert res1.returncode == 0
        assert mock_sub.call_count == 1

        # Second call should hit the cache without calling run_subprocess
        res2 = run_gh(["api", "rate_limit"], use_cache=True, cache_ttl=5.0)
        assert res2.returncode == 0
        assert res2.stdout == res1.stdout
        assert mock_sub.call_count == 1

    limiter.clear_cache()


def test_run_gh_rate_limit_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_gh retries with backoff on secondary rate limits."""
    limiter = get_github_rate_limiter()
    limiter.clear_cache()

    # Shorten backoff for tests
    monkeypatch.setattr(limiter, "min_interval", 0.01)

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub,
        patch("time.sleep") as mock_sleep,
    ):
        mock_sub.side_effect = [
            subprocess.CompletedProcess(
                args=["gh", "api", "issues"],
                returncode=1,
                stdout="",
                stderr="GraphQL: API rate limit already exceeded for user ID 7726889.",
            ),
            subprocess.CompletedProcess(
                args=["gh", "api", "issues"],
                returncode=0,
                stdout='[{"id": 1}]',
                stderr="",
            ),
        ]
        res = run_gh(["api", "issues"], max_retries=2)
        assert res.returncode == 0
        assert res.stdout == '[{"id": 1}]'
        assert mock_sub.call_count == 2
        mock_sleep.assert_called()


def test_run_gh_check_raises_called_process_error() -> None:
    """Verify run_gh raises CalledProcessError when check=True on non-zero exit."""
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "unknown"],
            returncode=4,
            stdout="",
            stderr="Not Found",
        )
        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            run_gh(["api", "unknown"], check=True, max_retries=0)
        assert exc_info.value.returncode == 4


def test_run_gh_input_passed_to_subprocess() -> None:
    """Verify run_gh passes stdin input to run_subprocess."""
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "graphql"],
            returncode=0,
            stdout='{"data": {}}',
            stderr="",
        )
        res = run_gh(["api", "graphql"], input='{"query": "viewer"}')
        assert res.returncode == 0
        mock_sub.assert_called_once()
        call_kwargs = mock_sub.call_args[1]
        assert call_kwargs["input"] == '{"query": "viewer"}'


def test_should_cache_predicates() -> None:
    """Verify _should_cache correctly differentiates read from mutation commands."""
    from devops_cli.github.rate_limiter import _should_cache

    assert _should_cache(["api", "rate_limit"], use_cache=True) is True
    assert _should_cache(["api", "rate_limit"], use_cache=False) is False
    assert _should_cache(["api", "-X", "POST", "issues"], use_cache=True) is False
    assert _should_cache(["pr", "create"], use_cache=True) is False
    assert _should_cache(["issue", "close", "123"], use_cache=True) is False
    assert _should_cache(["pr", "ready", "42"], use_cache=True) is False
    assert _should_cache(["api", "repos/o/r", "-f", "title=bug"], use_cache=True) is False
    assert _should_cache(["api", "graphql"], use_cache=True, input="mutation { ... }") is False
    assert _should_cache([], use_cache=True) is False


def test_rate_limiter_env_interval_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_github_rate_limiter respects DEVOPS_GH_RATE_INTERVAL."""
    import devops_cli.github.rate_limiter as rl_mod

    monkeypatch.setenv("DEVOPS_GH_RATE_INTERVAL", "0.25")
    # Reset singleton
    monkeypatch.setattr(rl_mod, "_GLOBAL_RATE_LIMITER", None)
    limiter = rl_mod.get_github_rate_limiter()
    assert limiter.min_interval == 0.25

    # Invalid string falls back to default
    monkeypatch.setenv("DEVOPS_GH_RATE_INTERVAL", "invalid-float")
    monkeypatch.setattr(rl_mod, "_GLOBAL_RATE_LIMITER", None)
    fallback_limiter = rl_mod.get_github_rate_limiter()
    assert fallback_limiter.min_interval == rl_mod.DEFAULT_GH_MIN_INTERVAL_SECONDS


def test_calculate_adaptive_delay_from_ratio() -> None:
    """Verify adaptive delay progressively backs off as ratio approaches zero."""
    from devops_cli.github.rate_limiter import _calculate_adaptive_delay_from_ratio

    min_int = 0.5
    # High quota (>50% remaining)
    assert _calculate_adaptive_delay_from_ratio(1.0, min_int) == min_int
    assert _calculate_adaptive_delay_from_ratio(0.75, min_int) == min_int
    assert _calculate_adaptive_delay_from_ratio(0.51, min_int) == min_int

    # 25% to 50% remaining: 0.5s to 2.0s
    d_40 = _calculate_adaptive_delay_from_ratio(0.40, min_int)
    assert 0.5 < d_40 < 2.0

    # 10% to 25% remaining: 2.0s to 5.0s
    d_20 = _calculate_adaptive_delay_from_ratio(0.20, min_int)
    assert 2.0 < d_20 < 5.0

    # 2% to 10% remaining: 5.0s to 15.0s
    d_5 = _calculate_adaptive_delay_from_ratio(0.05, min_int)
    assert 5.0 < d_5 < 15.0

    # <2% remaining: 15.0s to 30.0s
    d_1 = _calculate_adaptive_delay_from_ratio(0.01, min_int)
    assert 15.0 < d_1 <= 30.0
    assert _calculate_adaptive_delay_from_ratio(0.0, min_int) == 30.0


def test_rate_limiter_adaptive_quota_tracking() -> None:
    """Verify GitHubRateLimiter tracks quota and applies progressive delay."""
    limiter = GitHubRateLimiter(min_interval=0.5)

    # Initial state (uninitialized) returns min_interval
    assert limiter.calculate_adaptive_delay("graphql") == 0.5

    # Update with 4000/5000 remaining (80%) -> min_interval
    limiter.update_quota("graphql", remaining=4000, limit=5000)
    assert limiter.calculate_adaptive_delay("graphql") == 0.5

    # Update with 600/5000 remaining (12%) -> between 2.0s and 5.0s
    limiter.update_quota("graphql", remaining=600, limit=5000)
    delay_12 = limiter.calculate_adaptive_delay("graphql")
    assert 2.0 < delay_12 < 5.0

    # Update with 50/5000 remaining (1%) -> between 15.0s and 30.0s
    limiter.update_quota("graphql", remaining=50, limit=5000)
    delay_1 = limiter.calculate_adaptive_delay("graphql")
    assert 15.0 < delay_1 < 30.0

    # Update with 0 remaining and reset 25s in future -> wait ~25s
    now = time.time()
    limiter.update_quota("graphql", remaining=0, limit=5000, reset_epoch=now + 25.0)
    delay_0 = limiter.calculate_adaptive_delay("graphql")
    assert 20.0 <= delay_0 <= 26.0


def test_detect_resource_helper() -> None:
    """Verify _detect_resource accurately identifies graphql vs core endpoints."""
    from devops_cli.github.rate_limiter import _detect_resource

    assert _detect_resource(["api", "graphql", "-f", "query=..."]) == "graphql"
    assert _detect_resource(["project", "list", "--owner", "@me"]) == "graphql"
    assert (
        _detect_resource(["project", "item-add", "1", "--url", "http://example.com"]) == "graphql"
    )
    assert _detect_resource(["api", "user", "-i"]) == "core"
    assert _detect_resource(["issue", "list"]) == "core"
    assert _detect_resource(["pr", "checks", "123"]) == "core"


def test_run_gh_normalizes_leading_gh_arg() -> None:
    """Verify run_gh strips leading gh executable if passed redundantly in args."""
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "user"],
            returncode=0,
            stdout='{"login": "testuser"}',
            stderr="",
        )
        res = run_gh(["gh", "api", "user"])
        assert res.returncode == 0
        call_args = mock_sub.call_args[0][0]
        # Must not be ["gh", "gh", "api", "user"]
        assert call_args == ["gh", "api", "user"]


def test_run_gh_passively_updates_graphql_quota() -> None:
    """Verify run_gh passively extracts rateLimit field and updates limiter quota."""
    limiter = get_github_rate_limiter()

    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "graphql"],
            returncode=0,
            stdout='{"data": {"rateLimit": {"remaining": 3200, "limit": 5000, "resetAt": "2026-09-15T06:00:00Z"}}}',
            stderr="",
        )
        res = run_gh(["api", "graphql", "-f", "query={ viewer { login } }"])
        assert res.returncode == 0
        quota = limiter.get_quota("graphql")
        assert quota.remaining == 3200
        assert quota.limit == 5000
        assert quota.reset_epoch > 0


def test_rate_limiter_window_budget_pacing() -> None:
    """Verify rate limiter calculates window budget pacing delay when quota drops faster than time."""
    limiter = GitHubRateLimiter(min_interval=0.5)
    now = time.time()
    # 50 minutes left (3000s) and 1000 tokens remaining in GraphQL
    # Budget delay = (3000 / 1000) * 2.0 = 6.0s
    limiter.update_quota("graphql", remaining=1000, limit=5000, reset_epoch=now + 3000.0)
    delay = limiter.calculate_adaptive_delay("graphql")
    assert 5.5 <= delay <= 6.5, f"Expected budget delay around 6.0s, got {delay}s"

    # 10 minutes left (600s) and 4000 tokens remaining -> pacing can be min_interval (0.5s)
    limiter.update_quota("graphql", remaining=4000, limit=5000, reset_epoch=now + 600.0)
    delay_fast = limiter.calculate_adaptive_delay("graphql")
    assert delay_fast == 0.5


def test_rate_limiter_disk_quota_persistence(tmp_path: Path) -> None:
    """Verify quota state is safely persisted and restored from disk cache."""
    cache_file = tmp_path / "gh_quota.json"
    limiter1 = GitHubRateLimiter(min_interval=0.5, persist_path=cache_file)
    now = time.time()
    limiter1.update_quota("graphql", remaining=2200, limit=5000, reset_epoch=now + 1800.0)
    assert cache_file.is_file()

    # Second limiter loads existing state from disk
    limiter2 = GitHubRateLimiter(min_interval=0.5, persist_path=cache_file)
    q = limiter2.get_quota("graphql")
    assert q.remaining == 2200
    assert q.limit == 5000
    assert q.reset_epoch == pytest.approx(now + 1800.0, abs=1.0)


def test_rate_limiter_decrement_quota_estimate(tmp_path: Path) -> None:
    """Verify decrement_quota_estimate tracks usage when rate limit headers are absent."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(min_interval=0.5, persist_path=cache_file)
    limiter.update_quota("graphql", remaining=100, limit=5000)

    limiter.decrement_quota_estimate("graphql", cost=5)
    q = limiter.get_quota("graphql")
    assert q.remaining == 95
    assert q.used == 4905
