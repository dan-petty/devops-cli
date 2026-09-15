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


def test_calculate_allowed_rate() -> None:
    """Verify allowed rate decays smoothly from initial burst rate to 0 as tokens approach 0."""
    from devops_cli.github.rate_limiter import calculate_allowed_rate

    # 5000 quota with 3600s left: natural rate 1.39 rps, burst rate 2.78 rps
    r_0 = calculate_allowed_rate(used=0, remaining=5000, limit=5000, time_left=3600.0)
    assert 2.77 < r_0 < 2.78

    # 50% consumed (2500 rem, 1800s left) -> ~2.06 rps
    r_50 = calculate_allowed_rate(used=2500, remaining=2500, limit=5000, time_left=1800.0)
    assert 2.05 < r_50 < 2.07

    # Search: 30 limit, 60s window -> natural rate 0.5 rps, burst rate 1.0 rps
    r_search = calculate_allowed_rate(used=0, remaining=30, limit=30, time_left=60.0)
    assert r_search == 1.0

    # Code search: 10 limit, 60s window -> natural rate 0.167 rps, burst rate 0.333 rps
    r_code_search = calculate_allowed_rate(used=0, remaining=10, limit=10, time_left=60.0)
    assert 0.33 < r_code_search < 0.34

    # 98% consumed -> rate drops to near zero
    r_98 = calculate_allowed_rate(used=4900, remaining=100, limit=5000, time_left=3000.0)
    assert r_98 < 0.001

    # 0 remaining -> exactly 0.0 rps
    assert calculate_allowed_rate(used=5000, remaining=0, limit=5000, time_left=600.0) == 0.0


def test_calculate_exponential_backoff() -> None:
    """Verify inter-request delay is reciprocal of allowed rate and caps at max_delay."""
    from devops_cli.github.rate_limiter import calculate_exponential_backoff

    # 0% used (5000 rem, 3600s left) -> reciprocal of 2.778 rps (~0.360s)
    d_0 = calculate_exponential_backoff(used=0, remaining=5000, limit=5000, time_left=3600.0)
    assert 0.35 < d_0 < 0.37

    # When min_interval floor is provided, respected
    assert (
        calculate_exponential_backoff(
            used=0, remaining=5000, limit=5000, time_left=3600.0, min_interval=0.5
        )
        == 0.5
    )

    # 50% used (2500 rem, 1800s left) -> reciprocal of ~2.058 rps (~0.486s)
    d_50 = calculate_exponential_backoff(used=2500, remaining=2500, limit=5000, time_left=1800.0)
    assert 0.48 < d_50 < 0.50

    # Search: 30 rem, 60s left -> reciprocal of 1.0 rps = 1.0s
    d_search = calculate_exponential_backoff(used=0, remaining=30, limit=30, time_left=60.0)
    assert d_search == 1.0

    # 99% used -> capped at max_delay (60.0s)
    d_99 = calculate_exponential_backoff(used=4950, remaining=50, limit=5000, time_left=1000.0)
    assert d_99 == 60.0

    # 0 remaining -> max_delay (60.0s)
    assert calculate_exponential_backoff(used=5000, remaining=0, limit=5000) == 60.0


def test_adaptive_rate_limiter_rate_decay() -> None:
    """Verify AdaptiveRateLimiter velocity decay across consumption stages."""
    from devops_cli.github.rate_limiter import AdaptiveRateLimiter

    limiter = AdaptiveRateLimiter(quota=5000, window_seconds=3600.0, burst_multiplier=2.0)
    assert limiter.natural_rate == pytest.approx(1.38888, rel=1e-3)
    assert limiter.initial_burst_rate == pytest.approx(2.7777, rel=1e-3)

    # Initial rate at 0 consumed is 2.78 rps
    assert limiter.get_allowed_rate() == pytest.approx(2.7777, rel=1e-3)

    # Halfway consumed (2500 tokens) -> ~2.058 rps
    limiter.requests_consumed = 2500
    assert limiter.get_allowed_rate() == pytest.approx(2.0579, rel=1e-3)

    # 90% consumed (4500 tokens) -> ~0.187 rps
    limiter.requests_consumed = 4500
    assert limiter.get_allowed_rate() == pytest.approx(0.1867, rel=1e-3)

    # Fully consumed -> 0.0 rps
    limiter.requests_consumed = 5000
    assert limiter.get_allowed_rate() == 0.0


async def test_adaptive_rate_limiter_acquire() -> None:
    """Verify AdaptiveRateLimiter acquire async and sync inter-request pacing."""
    from devops_cli.github.rate_limiter import AdaptiveRateLimiter

    test_limiter = AdaptiveRateLimiter(quota=100, window_seconds=10.0, burst_multiplier=2.0)
    delay = await test_limiter.acquire()
    assert delay > 0.0
    assert test_limiter.requests_consumed == 1

    sync_delay = test_limiter.acquire_sync()
    assert sync_delay > 0.0
    assert test_limiter.requests_consumed == 2


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


def test_rate_limiter_adaptive_quota_tracking() -> None:
    """Verify GitHubRateLimiter tracks quota and applies exponential delay."""
    limiter = GitHubRateLimiter(min_interval=0.5)

    # Initial state (uninitialized) returns min_interval
    assert limiter.calculate_adaptive_delay("graphql") == 0.5

    # Update with 4000/5000 remaining (20% used) -> low backoff near min_interval
    limiter.update_quota("graphql", remaining=4000, limit=5000)
    delay_20 = limiter.calculate_adaptive_delay("graphql")
    assert 0.5 <= delay_20 < 0.8

    # Update with 500/5000 remaining (90% used) -> progressive exponential delay
    limiter.update_quota("graphql", remaining=500, limit=5000)
    delay_90 = limiter.calculate_adaptive_delay("graphql")
    assert delay_90 > 2.0

    # Update with 50/5000 remaining (99% used) -> high exponential delay
    limiter.update_quota("graphql", remaining=50, limit=5000)
    delay_99 = limiter.calculate_adaptive_delay("graphql")
    assert delay_99 >= 40.0

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
    """Verify rate limiter calculates dynamic adaptive delay when quota drops faster than time."""
    limiter = GitHubRateLimiter(min_interval=0.5)
    now = time.time()
    # 50 minutes left (3000s) and 1000 tokens remaining in GraphQL
    # Dynamic adaptive decay rate = 0.2008 rps -> delay = ~4.98s
    limiter.update_quota("graphql", remaining=1000, limit=5000, reset_epoch=now + 3000.0)
    delay = limiter.calculate_adaptive_delay("graphql")
    assert 4.5 <= delay <= 5.5, f"Expected adaptive delay around 5.0s, got {delay}s"

    # 10 minutes left (600s) and 4000 tokens remaining -> pacing near min_interval (0.5s)
    limiter.update_quota("graphql", remaining=4000, limit=5000, reset_epoch=now + 600.0)
    delay_fast = limiter.calculate_adaptive_delay("graphql")
    assert 0.5 <= delay_fast <= 0.6


def test_expected_four_minute_graphql_spend_cap() -> None:
    """Verify rate limiter bounds spend to <= 666.7 requests after 4 minutes in 60m window.

    With 5000 initial quota and 2.0x burst multiplier over a 3600s window, the baseline
    burst rate is 2.7778 rps (0.360s per request). In 240 seconds (4 minutes), the
    maximum permitted request spend is 240 * (5000 / 3600) * 2.0 = 666.7 tokens.
    """
    from devops_cli.github.rate_limiter import GitHubAdaptiveLimiter

    limiter = GitHubAdaptiveLimiter(initial_quota=5000, window_seconds=3600.0, burst_multiplier=2.0)
    burst_rate = limiter.initial_burst_rate
    assert burst_rate == pytest.approx(2.77777, rel=1e-3)
    min_delay = 1.0 / burst_rate
    assert min_delay == pytest.approx(0.360, rel=1e-3)

    # In 240 seconds (4 minutes), maximum possible requests at burst velocity:
    max_spend_4m = 240.0 * burst_rate
    assert max_spend_4m == pytest.approx(666.6667, rel=1e-3)

    # If an external source depleted 4048 tokens in 4 minutes (remaining = 952, 3360s left),
    # the limiter must engage tight braking (rate < 0.2 rps, delay > 6.0s) rather than allowing rapid requests.
    now = time.time()
    limiter.update_window_state(remaining=952, limit=5000, epoch_reset=now + 3360.0)
    choked_rate = limiter.get_allowed_rate()
    assert choked_rate < 0.2, f"Expected choked rate < 0.2 rps, got {choked_rate}"
    choked_delay = 1.0 / choked_rate
    assert choked_delay > 6.0, f"Expected brake delay > 6.0s, got {choked_delay}"


def test_invariant_cannot_consume_eighty_percent_in_ten_percent_window() -> None:
    """Verify invariant: limiter mathematically prevents consuming 80% of tokens in under 10% of window.

    In a 3600s window with 5000 quota and 2.0x burst multiplier:
    - 10% of window is 360 seconds.
    - 80% of quota is 4000 tokens.
    - Initial burst velocity is capped at 2.7778 rps.
    - In 360 seconds, maximum possible tokens consumed by acquire() is 360 * 2.7778 = 1000 tokens (20%).
    - Therefore, consuming 4000 tokens (80%) in under 360 seconds (10%) is mathematically precluded.
    """
    from devops_cli.github.rate_limiter import GitHubAdaptiveLimiter

    limiter = GitHubAdaptiveLimiter(initial_quota=5000, window_seconds=3600.0, burst_multiplier=2.0)
    window_10_percent = 3600.0 * 0.10  # 360s
    max_tokens_in_10_percent = window_10_percent * limiter.initial_burst_rate  # 1000 tokens

    # Max tokens that can be consumed in 10% of window is exactly 20% of quota (1000 / 5000)
    assert max_tokens_in_10_percent <= 0.20 * 5000
    assert max_tokens_in_10_percent < 0.80 * 5000

    # Furthermore, verify that each request is paced by at least 1.0 / burst_rate
    limiter_sim = GitHubAdaptiveLimiter(
        initial_quota=5000, window_seconds=3600.0, burst_multiplier=2.0
    )
    for _ in range(10):
        rate = limiter_sim.get_allowed_rate()
        delay = 1.0 / rate
        assert delay >= 0.35, f"Delay {delay}s violates velocity cap"
        limiter_sim.remaining -= 1


def test_rate_limiter_acquire_pacing_sequence() -> None:
    """Verify acquire enforces inter-request delay on every request."""
    limiter = GitHubRateLimiter(min_interval=0.02)
    # Simulate 4 rapid acquire calls
    t0 = time.perf_counter()
    for _ in range(4):
        delay = limiter.acquire()
        assert delay >= 0.02
    elapsed = time.perf_counter() - t0
    assert elapsed >= 0.06, f"Expected sequential delay >= 0.06s for 4 requests, got {elapsed}s"


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


def test_code_scanning_autofix_window_and_detection() -> None:
    """Verify code_scanning_autofix is detected and uses actual 60s window, not 3600s."""
    from devops_cli.github.rate_limiter import _detect_resource, calculate_allowed_rate

    # Command detection
    args = ["api", "repos/owner/repo/code-scanning/alerts/42/autofix"]
    assert _detect_resource(args) == "code_scanning_autofix"

    # Natural rate calculation with 60s window (10 limit, 10 rem)
    # Must be ~0.167 rps, burst rate ~0.333 rps (not 0.0027 rps from 3600 window)
    rate_60 = calculate_allowed_rate(used=0, remaining=10, limit=10, time_left=60.0)
    assert 0.33 < rate_60 < 0.34

    # Pacing in rate limiter does not cap out at 60s delay from 3600s fallback
    limiter = GitHubRateLimiter(min_interval=0.5)
    now = time.time()
    limiter.update_quota("code_scanning_autofix", remaining=10, limit=10, reset_epoch=now + 60.0)
    delay = limiter.calculate_adaptive_delay("code_scanning_autofix")
    assert delay <= 6.5, f"Delay {delay}s should be within 60s window budget, not 3600s default"


def test_github_adaptive_limiter_dynamic_time_windows() -> None:
    """Verify GitHubAdaptiveLimiter dynamically adapts to any window value."""
    from devops_cli.github.rate_limiter import GitHubAdaptiveLimiter

    # Initializing with explicit window (e.g. 60s for small burst quotas)
    limiter_small = GitHubAdaptiveLimiter(initial_quota=10, window_seconds=60.0)
    assert limiter_small.seconds_until_reset == 60.0
    assert limiter_small.quota == 10
    assert limiter_small.natural_rate == pytest.approx(10 / 60.0)

    # Initializing arbitrary window (e.g. 120s or 15s)
    limiter_120 = GitHubAdaptiveLimiter(initial_quota=50, window_seconds=120.0)
    assert limiter_120.seconds_until_reset == 120.0

    # Live update with actual response epoch_reset
    now = time.time()
    limiter_small.update_window_state(remaining=8, limit=10, epoch_reset=now + 45.0)
    assert limiter_small.remaining == 8
    assert limiter_small.quota == 10
    assert limiter_small.seconds_until_reset == pytest.approx(45.0, abs=1.0)
    # Allowed rate uses 8 / 45s
    rate = limiter_small.get_allowed_rate()
    assert rate > 0.0


def test_dynamic_window_learning_from_consecutive_resets() -> None:
    """Verify rate limiter derives actual window duration from consecutive reset epochs."""
    limiter = GitHubRateLimiter(min_interval=0.5)
    now = time.time()

    # First reset observed at T + 30s
    limiter.update_quota("code_scanning_autofix", remaining=9, limit=10, reset_epoch=now + 30.0)

    # Next cycle reset observed at T + 90s (60s window elapsed)
    limiter.update_quota("code_scanning_autofix", remaining=10, limit=10, reset_epoch=now + 90.0)

    state = limiter._quotas.get("code_scanning_autofix")
    assert state is not None
    assert state.window_seconds == pytest.approx(60.0, abs=0.1)


def test_adaptive_pacer_prevents_excessive_window_spend() -> None:
    """Verify pacer bounds cumulative request spend within window fraction.

    In a 60-minute (3600s) quota window with 5000 tokens and burst multiplier 2.0:
    - Natural rate = 5000 / 3600 = 1.3889 tokens/sec
    - Initial burst rate = 2.0 * 1.3889 = 2.7778 tokens/sec
    - After 4 minutes (240s), maximum allowable token spend without throttling is
      strictly bounded: 240 * (2.0 * 5000 / 3600) = 666.7 tokens.
    - Consuming 4048 of 5000 tokens (80%) in 4 minutes (< 10% of window) is
      mathematically precluded by inter-request pacing delays.
    """
    from devops_cli.github.rate_limiter import GitHubAdaptiveLimiter

    limiter = GitHubAdaptiveLimiter(initial_quota=5000, window_seconds=3600.0, burst_multiplier=2.0)

    # At t=0, allowed rate is bounded by burst allowance
    rate_initial = limiter.get_allowed_rate()
    assert rate_initial == pytest.approx(2.7777, rel=1e-3)
    min_inter_request_delay = 1.0 / rate_initial
    assert min_inter_request_delay == pytest.approx(0.36, rel=1e-2)

    # Max requests permitted over 240s at initial burst speed
    max_spend_4_minutes = 240.0 * rate_initial
    assert max_spend_4_minutes == pytest.approx(666.7, rel=1e-2)

    # Simulate live GitHub rate limit update when 4048 tokens are spent:
    # Remaining drops to 952 tokens with 3360s remaining until reset
    now = time.time()
    limiter.update_window_state(remaining=952, limit=5000, epoch_reset=now + 3360.0)
    rate_throttled = limiter.get_allowed_rate()

    # Throttled rate drops dramatically below 0.35 rps, requiring substantial delay (> 3.0s)
    assert rate_throttled < 0.35
    delay_throttled = 1.0 / rate_throttled
    assert delay_throttled > 3.0
