"""Unit tests for GitHub rate limiter, pacing, backoff, and caching subsystem."""

from __future__ import annotations

import subprocess
import time
from unittest.mock import patch

import pytest

from devops_cli.github.rate_limiter import (
    GitHubRateLimiter,
    get_github_rate_limiter,
    run_gh,
)


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
    assert fallback_limiter.min_interval == rl_mod._DEFAULT_MIN_INTERVAL_SECONDS
