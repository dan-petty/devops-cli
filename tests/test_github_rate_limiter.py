"""Unit tests for GitHub rate limiter and request pacing subsystem.

Verifies the simple delay formula:
    request delay = time in seconds until next quota reset for this subcommand / remaining requests
and mandatory pause enforcement.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import threading
import time
from collections.abc import Generator, Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.core import process
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.rate_limiter import (
    GitHubRateLimiter,
    QuotaState,
    calculate_request_delay,
    get_github_rate_limiter,
    reset_github_rate_limiter,
    run_gh,
)
from tests.support.fakes.clock import ClockFake


@pytest.fixture(autouse=True)
def isolate_rate_limiter(clock: ClockFake) -> Generator[None]:
    """Ensure global rate limiter singleton is reset before and after each test."""
    reset_github_rate_limiter()
    limiter = get_github_rate_limiter()
    now = time.time()
    for res in ("core", "graphql", "search", "code_search", "code_scanning_autofix"):
        limiter.update_quota(res, remaining=5000, limit=5000, reset_epoch=now + 3600.0)
    yield
    reset_github_rate_limiter()


def test_calculate_request_delay_user_spec_98_of_100() -> None:
    """Verify exact user specification:

    If you use 98 out of 100 tokens (remaining = 2) and have 30s out of a minute
    remaining, the request rate cannot be higher than 1 every 15 seconds (delay = 15.0s).
    """
    delay = calculate_request_delay(time_until_reset=30.0, remaining=2, limit=100)
    assert delay == 15.0
    # Request rate is 1 / 15.0 = 0.0667 req/s
    rate = 1.0 / delay
    assert rate == pytest.approx(1.0 / 15.0)


def test_calculate_request_delay_zero_rate_when_exhausted() -> None:
    """Verify rate is zero when threshold is exceeded (remaining == 0) until reset."""
    # 0 tokens remaining with 30s until reset -> delay must be full 30s (rate = 0)
    assert calculate_request_delay(time_until_reset=30.0, remaining=0) == 30.0
    # Negative tokens must raise ValueError
    with pytest.raises(ValueError, match="remaining requests must be non-negative"):
        calculate_request_delay(time_until_reset=45.0, remaining=-5)


def test_calculate_request_delay_variations() -> None:
    """Verify calculate_request_delay across multiple valid quota states."""
    delays = (
        calculate_request_delay(time_until_reset=3000.0, remaining=1000),
        round(calculate_request_delay(time_until_reset=3600.0, remaining=5000), 2),
        round(calculate_request_delay(time_until_reset=2400.0, remaining=2000), 2),
        calculate_request_delay(time_until_reset=0.0, remaining=10),
        calculate_request_delay(time_until_reset=0.0, remaining=0),
    )
    assert delays == (3.0, 0.72, 1.2, 0.0, 0.0)

    # Negative time_until_reset must raise ValueError
    with pytest.raises(ValueError, match="time_until_reset must be non-negative"):
        calculate_request_delay(time_until_reset=-10.0, remaining=10)


def test_quota_state_rejects_negative_values() -> None:
    """Verify QuotaState raises ValueError on negative limit, remaining, used, or reset_epoch."""

    with pytest.raises(ValueError, match="remaining requests must be non-negative"):
        QuotaState(remaining=-1)
    with pytest.raises(ValueError, match="rate limit must be non-negative"):
        QuotaState(limit=-100)
    with pytest.raises(ValueError, match="used requests must be non-negative"):
        QuotaState(used=-5)
    with pytest.raises(ValueError, match="reset_epoch must be non-negative"):
        QuotaState(reset_epoch=-1.0)

    state = QuotaState(remaining=10, limit=100, used=0, reset_epoch=100.0)
    with pytest.raises(ValueError, match="remaining requests must be non-negative"):
        state.remaining = -2
    with pytest.raises(ValueError, match="rate limit must be non-negative"):
        state.limit = -1
    with pytest.raises(ValueError, match="used requests must be non-negative"):
        state.used = -1
    with pytest.raises(ValueError, match="reset_epoch must be non-negative"):
        state.reset_epoch = -5.0
    with pytest.raises(ValueError, match="utilization cost must be non-negative"):
        state.record_utilization(cost=-1)


def test_calculate_request_delay_negative_limit() -> None:
    """Verify calculate_request_delay raises ValueError on negative limit."""
    with pytest.raises(ValueError, match="rate limit must be non-negative"):
        calculate_request_delay(time_until_reset=100.0, remaining=50, limit=-10)


def test_calculate_request_delay_zero_bypass_forbidden() -> None:
    """Verify pacing delay is strictly applied even when 0 tokens have been used (no 0.0s bypass)."""
    # 5000 remaining of 5000 limit with 3600s left -> 3600 / 5000 = 0.72s delay
    delay = calculate_request_delay(time_until_reset=3600.0, remaining=5000, limit=5000)
    assert round(delay, 2) == 0.72


def test_graphql_mandatory_pacing_default_no_bypass() -> None:
    """Verify GitHubRateLimiter applies mandatory pacing without 0.0s threshold bypass."""
    limiter = GitHubRateLimiter()
    now = time.time()

    # 5000 requests in 60 minutes -> 0.72s
    limiter._quotas["graphql"] = QuotaState(remaining=5000, limit=5000, reset_epoch=now + 3600.0)
    delay_5000 = limiter.calculate_delay("graphql")

    # 2000 requests in 40 minutes -> 1.20s
    limiter._quotas["graphql"] = QuotaState(remaining=2000, limit=5000, reset_epoch=now + 2400.0)
    delay_2000 = limiter.calculate_delay("graphql")

    assert (round(delay_5000, 2), round(delay_2000, 2)) == (0.72, 1.2)


def test_rate_limiter_no_initial_quotas() -> None:
    """Verify rate limiter has no hardcoded initial quotas, and that a failed refresh leaves the
    quota unread."""
    limiter = GitHubRateLimiter()
    state = limiter.get_quota("core")
    assert (state.remaining, state.limit, state.reset_epoch) == (None, None, None)

    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "rate_limit"],
            returncode=1,
            stdout="",
            stderr="API unavailable",
        )
        with pytest.raises(GitHubUnreadError):
            limiter.calculate_delay("core")


def test_rate_limiter_mandatory_pause_enforcement(clock: ClockFake) -> None:
    """Verify acquire institutes a mandatory pause using the calculated delay."""
    limiter = GitHubRateLimiter()
    now = time.time()

    # User scenario: 98 out of 100 tokens used (remaining = 2), 30s until reset
    limiter.update_quota("graphql", remaining=2, limit=100, reset_epoch=now + 30.0)

    delay = limiter.acquire("graphql")
    assert 14.0 <= delay <= 15.5  # ~15.0s
    assert len(clock.waits) == 1
    assert clock.waits[0] == pytest.approx(15.0, abs=0.5)


def test_rate_limiter_mandatory_pause_when_quota_exhausted(clock: ClockFake) -> None:
    """Verify acquire pauses for the full duration until reset when remaining <= 0."""
    limiter = GitHubRateLimiter()
    now = time.time()

    # 0 tokens remaining with 20s until reset
    limiter.update_quota("core", remaining=0, limit=5000, reset_epoch=now + 20.0)

    delay = limiter.acquire("core")
    assert 19.0 <= delay <= 20.0
    assert len(clock.waits) == 1
    assert clock.waits[0] == pytest.approx(20.0, abs=0.5)


def test_rate_limiter_acquire_mandatory_pacing(tmp_path: Path, clock: ClockFake) -> None:
    """Verify acquire always applies calculated pacing delay with zero threshold bypass."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()
    limiter.update_quota("core", remaining=3600, limit=5000, reset_epoch=now + 3600.0)
    delay = limiter.acquire("core")
    assert delay == pytest.approx(1.0, abs=0.1)
    assert len(clock.waits) == 1
    assert clock.waits[0] == pytest.approx(1.0, abs=0.1)


def test_rate_limiter_decrement_quota_estimate(tmp_path: Path) -> None:
    """Verify decrement_quota_estimate decreases remaining tokens and increases delay."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()
    limiter.update_quota("core", remaining=10, limit=100, reset_epoch=now + 60.0)

    # With 10 remaining, delay is 60 / 10 = ~6.0s
    assert limiter.calculate_delay("core") == pytest.approx(6.0, abs=0.5)

    # Decrement by 5
    limiter.decrement_quota_estimate("core", cost=5)
    q = limiter.get_quota("core")
    assert q.remaining == 5
    # With 5 remaining, delay is 60 / 5 = ~12.0s
    assert limiter.calculate_delay("core") == pytest.approx(12.0, abs=0.5)


def test_rate_limiter_disk_quota_persistence(tmp_path: Path) -> None:
    """Verify quota state is safely persisted and restored from disk cache."""
    cache_file = tmp_path / "gh_quota.json"
    limiter1 = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()
    limiter1.update_quota("graphql", remaining=2200, limit=5000, reset_epoch=now + 1800.0)
    assert cache_file.is_file()

    # Second limiter loads existing state from disk
    limiter2 = GitHubRateLimiter(persist_path=cache_file)
    q = limiter2.get_quota("graphql")
    assert q.remaining == 2200
    assert q.limit == 5000
    assert q.reset_epoch == pytest.approx(now + 1800.0, abs=1.0)


def test_rate_limiter_backoff_calculation() -> None:
    """Verify backoff calculation on secondary rate limits."""
    limiter = GitHubRateLimiter()
    err_secondary = "GraphQL: API rate limit already exceeded for user ID 7726889."
    assert limiter.is_rate_limit_error(err_secondary) is True

    delay_1 = limiter.calculate_backoff_delay(err_secondary, attempt=1)
    delay_2 = limiter.calculate_backoff_delay(err_secondary, attempt=2)
    non_rate_err = "Error: repository not found"
    assert (
        60.0 <= delay_1 <= 61.0,
        60.0 <= delay_2 <= 62.0,
        limiter.is_rate_limit_error(non_rate_err),
        limiter.calculate_backoff_delay(non_rate_err, attempt=1),
    ) == (True, True, False, 0.0)


def test_rate_limiter_ephemeral_cache(clock: ClockFake) -> None:
    """Verify ephemeral read cache stores and returns data within TTL."""
    limiter = GitHubRateLimiter()
    key = "gh:rate_limit"
    assert limiter.get_cached(key) is None

    limiter.set_cached(key, '{"resources": {}}', ttl=1.0)
    assert limiter.get_cached(key) == '{"resources": {}}'

    clock.sleep(1.05)
    assert limiter.get_cached(key) is None


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
    assert _detect_resource(["search", "code", "foo"]) == "code_search"
    assert _detect_resource(["search", "issues", "bar"]) == "search"
    assert (
        _detect_resource(["api", "repos/owner/repo/code-scanning/alerts/1/autofix"])
        == "code_scanning_autofix"
    )


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
        assert call_args == ["gh", "api", "user"]


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
        quota = limiter.get_quota("graphql")
        assert (
            res.returncode,
            quota.remaining,
            quota.limit,
            quota.reset_epoch is not None and quota.reset_epoch > 0,
        ) == (0, 3200, 5000, True)


def test_run_gh_passively_updates_header_quota() -> None:
    """Verify run_gh parses x-ratelimit-* headers from output."""
    limiter = get_github_rate_limiter()

    raw_output = (
        "HTTP/2.0 200 OK\r\n"
        "x-ratelimit-limit: 5000\r\n"
        "x-ratelimit-remaining: 4800\r\n"
        "x-ratelimit-reset: 1773550000\r\n"
        "\r\n"
        '{"id": 123}'
    )
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "users/octocat"],
            returncode=0,
            stdout=raw_output,
            stderr="",
        )
        res = run_gh(["api", "users/octocat", "-i"])
        assert res.returncode == 0
        quota = limiter.get_quota("core")
        assert quota.remaining == 4800
        assert quota.limit == 5000
        assert quota.reset_epoch == 1773550000.0


def test_run_gh_rate_limit_retry(monkeypatch: pytest.MonkeyPatch, clock: ClockFake) -> None:
    """Verify run_gh retries with backoff on secondary rate limits."""
    limiter = get_github_rate_limiter()
    limiter.clear_cache()
    monkeypatch.setattr(limiter, "min_interval", 0.01)

    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
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
    # Pacing also sleeps on every attempt; the backoff is the wait of at least the secondary floor.
    assert (
        res.returncode,
        res.stdout,
        mock_sub.call_count,
        max(clock.waits) >= limiter.secondary_rate_wait,
    ) == (
        0,
        '[{"id": 1}]',
        2,
        True,
    )


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


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        pytest.param(
            '{"message": "Bad credentials", "status": "401"}',
            "gh: Bad credentials (HTTP 401)",
            id="401-body",
        ),
        pytest.param("<html>upstream</html>", "gh: HTTP 502", id="html-502"),
    ],
)
def test_a_failed_rate_limit_read_returns_its_exit_status_without_reading_its_body(
    stdout: str, stderr: str
) -> None:
    """gh writes GitHub's error body to stdout when `gh api rate_limit` fails: `run_gh` returns
    the failed process for its caller to read, and parses no quota from the body (#983)."""
    failed = subprocess.CompletedProcess(["gh", "api", "rate_limit"], 1, stdout, stderr)
    before = get_github_rate_limiter().get_quota("core")
    with patch("devops_cli.github.rate_limiter.run_subprocess", return_value=failed):
        res = run_gh(["api", "rate_limit"])
    assert (res.returncode, res.stderr, get_github_rate_limiter().get_quota("core")) == (
        1,
        stderr,
        before,
    )


def test_run_gh_rate_limit_endpoint_extracts_all_resources(clock: ClockFake) -> None:
    """Verify /rate_limit endpoint response updates all resources directly without acquire sleep."""
    limiter = get_github_rate_limiter()
    output = (
        '{"resources": {'
        '"core": {"limit": 5000, "remaining": 4999, "reset": 1773551000},'
        '"graphql": {"limit": 5000, "remaining": 4500, "reset": 1773552000},'
        '"search": {"limit": 30, "remaining": 28, "reset": 1773550060}'
        "}}"
    )

    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "rate_limit"],
            returncode=0,
            stdout=output,
            stderr="",
        )
        res = run_gh(["api", "rate_limit"])
        assert res.returncode == 0
        # rate_limit inspection must not trigger pacing sleep
        assert clock.waits == []

        assert limiter.get_quota("core").remaining == 4999
        assert limiter.get_quota("graphql").remaining == 4500
        assert limiter.get_quota("search").remaining == 28


def test_quota_state_validate_direct() -> None:
    """Verify QuotaState.validate() raises ValueError on negative fields."""
    state = QuotaState()
    state.__dict__["remaining"] = -1
    with pytest.raises(ValueError, match="remaining requests must be non-negative"):
        state.validate()

    state.__dict__["remaining"] = 10
    state.__dict__["limit"] = -1
    with pytest.raises(ValueError, match="rate limit must be non-negative"):
        state.validate()

    state.__dict__["limit"] = 100
    state.__dict__["used"] = -1
    with pytest.raises(ValueError, match="used requests must be non-negative"):
        state.validate()

    state.__dict__["used"] = 0
    state.__dict__["reset_epoch"] = -1.0
    with pytest.raises(ValueError, match="reset_epoch must be non-negative"):
        state.validate()


def test_disk_quota_corrupt_or_unwritable(tmp_path: Path) -> None:
    """Verify disk quota loader handles corrupt JSON and saver handles unwritable directories."""
    from devops_cli.github.rate_limiter import _load_disk_quota, _save_disk_quota

    corrupt_file = tmp_path / "corrupt.json"
    corrupt_file.write_text("not json content", encoding="utf-8")
    assert _load_disk_quota(corrupt_file) == {}

    # Unwritable path handling
    unwritable = Path("/forbidden_sys_dir_test/quota.json")
    _save_disk_quota({"core": QuotaState(remaining=10)}, unwritable)


def test_extract_json_payload_edge_cases() -> None:
    """Verify extract_json_payload handles empty, non-JSON, and malformed strings."""
    from devops_cli.github.rate_limiter import extract_json_payload

    assert extract_json_payload("") is None
    assert extract_json_payload("Plain text with no brackets") is None
    assert extract_json_payload("Prefix { not valid json: 123") is None
    assert extract_json_payload('Preamble banner\n{"valid": 1}') == {"valid": 1}


def test_detect_resource_and_reset_epoch() -> None:
    """Verify _detect_resource and _parse_reset_epoch handle boundary values."""
    from devops_cli.github.rate_limiter import _detect_resource, _parse_reset_epoch

    assert _detect_resource([]) == "core"
    assert _detect_resource(["gh"]) == "core"
    assert _detect_resource(["api", "repos/owner/repo/dependency-graph/sbom"]) == "dependency_sbom"

    assert (_parse_reset_epoch(None), _parse_reset_epoch("")) == (None, None)
    with pytest.raises(ValueError, match="Failed to parse resetAt timestamp"):
        _parse_reset_epoch("invalid-date-string")
    assert _parse_reset_epoch("2026-09-15T12:00:00Z") is not None


def test_parse_safe_helpers() -> None:
    """Verify integer, float parsing and GraphQL extraction safe fallbacks."""
    from devops_cli.github.rate_limiter import (
        _extract_graphql_ratelimit_json,
        _parse_float_safe,
        _parse_int_safe,
    )

    assert _parse_int_safe("not-an-int", 42) == 42
    assert _parse_int_safe(" 10 ", 0) == 10
    assert _parse_float_safe("not-a-float", 3.14) == 3.14
    assert _parse_float_safe(" 2.5 ", 0.0) == 2.5

    limiter = GitHubRateLimiter()
    _extract_graphql_ratelimit_json("not json", limiter)
    _extract_graphql_ratelimit_json('{"data": "not a dict"}', limiter)
    _extract_graphql_ratelimit_json('{"data": {"rateLimit": null}}', limiter)


def test_calculate_delay_remaining_none_or_negative() -> None:
    """Verify calculate_delay raises error when remaining is None or negative."""
    limiter = GitHubRateLimiter()
    now = time.time()
    state_none = QuotaState(limit=100, reset_epoch=now + 10.0)
    state_none.__dict__["remaining"] = None
    with patch.object(limiter, "_resolve_quota_state", return_value=state_none):
        with pytest.raises(GitHubRateLimitError, match="remaining requests is unknown"):
            limiter.calculate_delay("core")

    state_neg = QuotaState(limit=100, reset_epoch=now + 10.0)
    state_neg.__dict__["remaining"] = -5
    with patch.object(limiter, "_resolve_quota_state", return_value=state_neg):
        with pytest.raises(ValueError, match="remaining requests must be non-negative"):
            limiter.calculate_delay("core")


def test_update_quota_negative_validations() -> None:
    """Verify update_quota rejects negative parameters."""
    limiter = GitHubRateLimiter()
    with pytest.raises(ValueError, match="remaining requests must be non-negative"):
        limiter.update_quota("core", remaining=-1)
    with pytest.raises(ValueError, match="rate limit must be non-negative"):
        limiter.update_quota("core", remaining=10, limit=-1)
    with pytest.raises(ValueError, match="reset_epoch must be non-negative"):
        limiter.update_quota("core", remaining=10, reset_epoch=-1.0)
    with pytest.raises(ValueError, match="used requests must be non-negative"):
        limiter.update_quota("core", remaining=10, used=-1)


def test_validate_gh_cwd(tmp_path: Path) -> None:
    """Verify _validate_gh_cwd accepts valid directories and rejects non-existent or prohibited system paths."""
    from devops_cli.github.rate_limiter import _validate_gh_cwd

    assert _validate_gh_cwd(None) is None
    assert _validate_gh_cwd(tmp_path) == tmp_path.resolve()

    with pytest.raises(ValueError, match="Invalid cwd directory"):
        _validate_gh_cwd(tmp_path / "nonexistent_dir_12345")

    with pytest.raises(ValueError, match="Prohibited system path for cwd"):
        _validate_gh_cwd(Path("/etc"))


def test_run_gh_with_cwd_and_called_process_error(tmp_path: Path) -> None:
    """Verify run_gh passes cwd and raises CalledProcessError when check=True on failure."""
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "list"], returncode=0, stdout="pr list output", stderr=""
        )
        res = run_gh(["pr", "list"], cwd=tmp_path)
        assert res.returncode == 0
        mock_sub.assert_called_once()
        assert mock_sub.call_args[1]["cwd"] == tmp_path.resolve()

    # Paginated with check=True and non-zero returncode raises CalledProcessError
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "repos/owner/repo/pulls", "--paginate"],
            returncode=1,
            stdout="",
            stderr="Failed to paginate",
        )
        with pytest.raises(subprocess.CalledProcessError):
            run_gh(["api", "repos/owner/repo/pulls", "--paginate"], check=True)


def test_quota_state_malformed_types_discarded(tmp_path: Path) -> None:
    """Verify QuotaState.from_dict and _load_disk_quota discard malformed/null fields gracefully."""
    import json

    cache_file = tmp_path / "gh_quota.json"
    cache_file.write_text(
        json.dumps(
            {
                "core": {
                    "limit": None,
                    "remaining": None,
                    "used": None,
                    "reset_epoch": None,
                    "last_updated": None,
                },
                "corrupted": {"used": "not_an_int"},
            }
        ),
        encoding="utf-8",
    )
    from devops_cli.github.rate_limiter import _load_disk_quota

    loaded = _load_disk_quota(cache_file)
    assert loaded == {}


def test_global_request_tracking_across_limiter_instances(tmp_path: Path) -> None:
    """Verify global requests and quota state synchronize across independent limiter instances."""
    cache_file = tmp_path / "gh_quota.json"
    limiter_a = GitHubRateLimiter(persist_path=cache_file)
    limiter_b = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()
    limiter_a.update_quota("core", remaining=100, limit=100, reset_epoch=now + 100.0)

    limiter_a.acquire("core")
    limiter_b.acquire("core")

    assert (
        limiter_a.get_global_request_count(),
        limiter_b.get_global_request_count(),
        limiter_a.get_quota("core").remaining,
        limiter_b.get_quota("core").remaining,
    ) == (2, 2, 98, 98)


def test_get_quota_live_disk_sync(tmp_path: Path) -> None:
    """Verify get_quota reloads fresh state from disk when updated externally."""
    cache_file = tmp_path / "gh_quota.json"
    limiter_a = GitHubRateLimiter(persist_path=cache_file)
    limiter_b = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()

    limiter_a.update_quota("graphql", remaining=500, limit=5000, reset_epoch=now + 3600.0)
    quota_b = limiter_b.get_quota("graphql")
    assert (quota_b.remaining, quota_b.limit) == (500, 5000)

    # External update from instance A
    limiter_a.update_quota("graphql", remaining=400, limit=5000, reset_epoch=now + 3600.0)
    quota_b_fresh = limiter_b.get_quota("graphql")
    assert quota_b_fresh.remaining == 400


def test_merge_single_quota_preserves_freshest_consumption() -> None:
    """Verify _merge_single_quota never overwrites lower remaining with stale higher count."""
    from devops_cli.github.rate_limiter import _merge_single_quota

    disk_state = QuotaState(limit=5000, remaining=3000, used=2000, reset_epoch=1000.0)
    mem_state = QuotaState(limit=5000, remaining=4000, used=1000, reset_epoch=1000.0)

    merged = _merge_single_quota(disk_state, mem_state)
    assert (merged.remaining, merged.used) == (3000, 2000)


def test_update_quota_preserves_utilization_on_unknown_used(tmp_path: Path) -> None:
    """Verify update_quota never resets or overwrites tracked used when used is None."""
    limiter = GitHubRateLimiter(persist_path=tmp_path / "gh_quota.json")
    now = time.time()

    limiter.update_quota("graphql", remaining=5000, limit=5000, used=150, reset_epoch=now + 3600.0)
    assert limiter.get_quota("graphql").used == 150

    # Live response without used header must preserve existing utilization, not reset to 0
    limiter.update_quota("graphql", remaining=4900, limit=5000, used=None, reset_epoch=now + 3600.0)
    assert (limiter.get_quota("graphql").used, limiter.get_quota("graphql").remaining) == (
        150,
        4900,
    )


def test_get_quota_unknown_subcommand_does_not_mutate_quotas() -> None:
    """Verify get_quota on untracked subcommand returns blank state without mutating internal quotas."""
    limiter = GitHubRateLimiter()
    quota = limiter.get_quota("nonexistent_subcmd")
    assert (quota.remaining, quota.used, quota.is_valid()) == (None, None, False)
    assert "nonexistent_subcmd" not in limiter._quotas


def test_quota_from_dict_preserves_none_and_rejects_malformed() -> None:
    """Verify QuotaState.from_dict preserves None rather than defaulting to 0, and rejects invalid types."""
    parsed = QuotaState.from_dict({"limit": 5000, "remaining": 5000, "reset_epoch": 1000.0})
    assert (parsed.used, parsed.last_request_epoch) == (None, None)
    with pytest.raises(GitHubRateLimitError, match="Expected dict for QuotaState"):
        QuotaState.from_dict("not_a_dict")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="Malformed quota state dictionary"):
        QuotaState.from_dict({"limit": "not_an_int"})
    with pytest.raises(ValueError, match="Malformed quota state dictionary"):
        QuotaState.from_dict({"reset_epoch": -10.0})


def test_is_cacheable_api_call_rejects_all_mutations() -> None:
    """Verify _is_cacheable_api_call rejects all HTTP mutation verbs and field arguments."""
    from devops_cli.github.rate_limiter import _is_cacheable_api_call

    assert _is_cacheable_api_call(["api", "repos/owner/repo/pulls"]) is True
    assert not _is_cacheable_api_call(["api", "-X", "POST", "repos/owner/repo/pulls"])
    assert not _is_cacheable_api_call(["api", "-X", "PUT", "repos/owner/repo/pulls"])
    assert not _is_cacheable_api_call(["api", "-X", "PATCH", "repos/owner/repo/pulls"])
    assert not _is_cacheable_api_call(["api", "-X", "DELETE", "repos/owner/repo/pulls"])
    assert not _is_cacheable_api_call(["api", "--method=DELETE", "repos/owner/repo/pulls"])
    assert not _is_cacheable_api_call(["api", "repos/owner/repo/pulls", "-f", "title=foo"])


def test_backoff_and_quota_max_age_enforcement() -> None:
    """Verify calculate_backoff_delay pauses for full reset epoch and quota_max_age detects stale quota."""
    limiter = GitHubRateLimiter(quota_max_age=10.0)
    now = time.time()
    limiter.update_quota("core", remaining=0, limit=5000, reset_epoch=now + 120.0)
    delay = limiter.calculate_backoff_delay("rate limit exceeded", attempt=1, subcommand="core")
    assert 118.0 <= delay <= 121.0

    state = QuotaState(
        limit=5000,
        remaining=4000,
        reset_epoch=now + 3600.0,
        last_updated=now - 20.0,
    )
    assert not state.is_valid(now=now, max_age=limiter.quota_max_age)
    assert state.is_valid(now=now) is True


def test_disk_quota_lock_exception_propagation_and_cleanup(tmp_path: Path) -> None:
    """Verify _disk_quota_lock unlocks and propagates inner exceptions without throw error."""
    from devops_cli.github.rate_limiter import _DISK_LOCK_STATE, _disk_quota_lock

    lock_target = tmp_path / "quota.json"
    lock_file = lock_target.with_suffix(".lock")

    with pytest.raises(ZeroDivisionError, match="division by zero"):
        with _disk_quota_lock(lock_target):
            assert _DISK_LOCK_STATE.depth.get(lock_file) == 1
            _ = 1 / 0

    assert _DISK_LOCK_STATE.depth.get(lock_file) == 0


def test_disk_quota_lock_oserror_fallback_and_propagation(tmp_path: Path) -> None:
    """Verify _disk_quota_lock yields and propagates exceptions when advisory locking fails."""
    from devops_cli.github.rate_limiter import _disk_quota_lock

    lock_target = tmp_path / "quota.json"

    with patch("fcntl.flock", side_effect=OSError("Flock failed")):
        with pytest.raises(KeyError):
            with _disk_quota_lock(lock_target):
                raise KeyError("expected_key_error")


def test_rate_limiter_acquire_propagates_unresolvable_quota_error(
    tmp_path: Path, clock: ClockFake
) -> None:
    """Verify acquire propagates GitHubRateLimitError when quota state cannot be resolved."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=cache_file, min_interval=0.05)

    with patch.object(
        limiter,
        "_resolve_quota_state",
        side_effect=GitHubRateLimitError("offline"),
    ):
        with pytest.raises(GitHubRateLimitError, match="offline"):
            limiter.acquire("core")
        assert clock.waits == []


def test_extract_rate_limit_endpoint_response_valid() -> None:
    """Verify _extract_rate_limit_endpoint_response parses valid metrics without defaulting reset to 0.0."""
    from devops_cli.github.rate_limiter import (
        GitHubRateLimiter,
        _extract_rate_limit_endpoint_response,
    )

    limiter = GitHubRateLimiter()
    raw = json.dumps(
        {
            "resources": {
                "core": {"limit": 5000, "remaining": 4900, "used": 100, "reset": 1789249509},
                "search": {"limit": 30, "remaining": 25},
            }
        }
    )
    _extract_rate_limit_endpoint_response(raw, limiter)
    core_quota = limiter.get_quota("core")
    assert (core_quota.remaining, core_quota.limit, core_quota.used, core_quota.reset_epoch) == (
        4900,
        5000,
        100,
        1789249509.0,
    )
    search_quota = limiter.get_quota("search")
    assert (search_quota.remaining, search_quota.limit, search_quota.reset_epoch) == (
        25,
        30,
        None,
    )


def test_extract_rate_limit_endpoint_response_invalid_format_raises() -> None:
    """Verify _extract_rate_limit_endpoint_response raises GitHubRateLimitError on invalid payload format."""
    from devops_cli.exceptions.git import GitHubRateLimitError
    from devops_cli.github.rate_limiter import (
        GitHubRateLimiter,
        _extract_rate_limit_endpoint_response,
    )

    limiter = GitHubRateLimiter()
    with pytest.raises(GitHubRateLimitError) as exc_info:
        _extract_rate_limit_endpoint_response("not-json", limiter)
    assert "Invalid rate_limit payload format" in str(exc_info.value)

    with pytest.raises(GitHubRateLimitError) as exc_info2:
        _extract_rate_limit_endpoint_response('{"no_resources": true}', limiter)
    assert "Missing resources dictionary" in str(exc_info2.value)


def test_extract_rate_limit_endpoint_response_malformed_metric_raises() -> None:
    """Verify _extract_rate_limit_endpoint_response raises GitHubRateLimitError on malformed metric values."""
    from devops_cli.exceptions.git import GitHubRateLimitError
    from devops_cli.github.rate_limiter import (
        GitHubRateLimiter,
        _extract_rate_limit_endpoint_response,
    )

    limiter = GitHubRateLimiter()
    bad_payload = json.dumps({"resources": {"core": {"remaining": "not-an-int"}}})
    with pytest.raises(GitHubRateLimitError) as exc_info:
        _extract_rate_limit_endpoint_response(bad_payload, limiter)
    assert "Malformed rate limit metric" in str(exc_info.value)


def test_rate_limiter_prune_expired_cache_ephemeral_and_disk(
    tmp_path: Path, clock: ClockFake
) -> None:
    """Verify prune_expired_cache purges expired entries from both memory and disk."""
    quota_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=quota_file)
    limiter.set_cached("valid_key", "valid_data", ttl=3600.0)
    limiter.set_cached("expired_key", "expired_data", ttl=0.01)
    clock.sleep(0.05)

    pruned = limiter.prune_expired_cache()
    valid_res = limiter.get_cached("valid_key")
    expired_res = limiter.get_cached("expired_key")

    assert (pruned >= 1, valid_res, expired_res) == (True, "valid_data", None)


def test_rate_limiter_init_prunes_expired_disk_cache(tmp_path: Path) -> None:
    """Verify rate limiter initialization prunes stale and corrupt response files on disk."""
    quota_file = tmp_path / "gh_quota.json"
    responses_dir = tmp_path / "responses"
    responses_dir.mkdir(parents=True, exist_ok=True)

    expired_file = responses_dir / "expired.json"
    expired_file.write_text(
        json.dumps({"expires_at": time.time() - 100.0, "data": "old"}), encoding="utf-8"
    )
    valid_file = responses_dir / "valid.json"
    valid_file.write_text(
        json.dumps({"expires_at": time.time() + 3600.0, "data": "fresh"}), encoding="utf-8"
    )
    corrupt_file = responses_dir / "corrupt.json"
    corrupt_file.write_text("invalid json payload", encoding="utf-8")

    _limiter = GitHubRateLimiter(persist_path=quota_file)

    assert (expired_file.exists(), valid_file.exists(), corrupt_file.exists()) == (
        False,
        True,
        False,
    )


def test_server_retry_after_returned_unchanged() -> None:
    """Verify server Retry-After delay is returned unchanged without local cap clamping."""
    limiter = GitHubRateLimiter(secondary_max_cap=300.0)
    msg_header = "HTTP 429: Too Many Requests\nRetry-After: 450\n"
    msg_text = "HTTP 403: You have exceeded a secondary rate limit. Please retry after 120 seconds."
    delay_header = limiter.calculate_backoff_delay(msg_header, attempt=1)
    delay_text = limiter.calculate_backoff_delay(msg_text, attempt=1)
    assert (delay_header, delay_text) == (450.0, 120.0)


def test_local_cap_bounds_client_growth_on_secondary_rate_limit() -> None:
    """Verify local cap bounds only the client's own growth on secondary rate limits."""
    limiter_default = GitHubRateLimiter()
    limiter_custom = GitHubRateLimiter(secondary_rate_wait=60.0, secondary_max_cap=75.0)
    err = "HTTP 403: You have exceeded a secondary rate limit."
    delay_high_attempt = limiter_default.calculate_backoff_delay(err, attempt=20)
    delay_custom_cap = limiter_custom.calculate_backoff_delay(err, attempt=10)
    assert (
        60.0 <= delay_high_attempt <= 300.0,
        60.0 <= delay_custom_cap <= 75.0,
    ) == (True, True)


def test_quota_remaining_positive_does_not_sleep_until_primary_reset() -> None:
    """Verify non-exhausted quota (remaining > 0) does not wait until primary reset epoch."""
    limiter = GitHubRateLimiter()
    now = time.time()
    limiter.update_quota("core", remaining=4999, limit=5000, reset_epoch=now + 3000.0)
    err = "HTTP 403: You have exceeded a secondary rate limit."
    delay = limiter.calculate_backoff_delay(err, attempt=1, subcommand="core")
    assert (delay < 3000.0, 60.0 <= delay <= 61.0) == (True, True)


def test_max_rate_limit_wait_raises_github_rate_limit_error() -> None:
    """Verify max_rate_limit_wait raises GitHubRateLimitError when required wait exceeds cap."""
    limiter = GitHubRateLimiter(max_rate_limit_wait=50.0)
    err_sec = "HTTP 403: You have exceeded a secondary rate limit."
    err_retry = "HTTP 429: Too Many Requests\nRetry-After: 90\n"

    with pytest.raises(GitHubRateLimitError, match="exceeds max_rate_limit_wait") as exc_sec:
        limiter.calculate_backoff_delay(err_sec, attempt=1)

    with pytest.raises(GitHubRateLimitError, match="exceeds max_rate_limit_wait") as exc_retry:
        limiter.calculate_backoff_delay(err_retry, attempt=1)

    now = time.time()
    limiter.update_quota("core", remaining=0, limit=5000, reset_epoch=now + 180.0)
    with pytest.raises(GitHubRateLimitError, match="Required primary rate limit wait") as exc_prim:
        limiter.calculate_backoff_delay("rate limit exceeded", attempt=1, subcommand="core")

    assert (
        "secondary" in str(exc_sec.value).lower(),
        "retry-after" in str(exc_retry.value).lower(),
        "primary" in str(exc_prim.value).lower(),
    ) == (True, True, True)


def test_rate_limiter_throttle_persistence_across_instances(tmp_path: Path) -> None:
    """Verify throttle counts and backoff sleep duration persist to disk and sync across instances."""
    quota_file = tmp_path / "gh_quota.json"
    limiter1 = GitHubRateLimiter(persist_path=quota_file)
    limiter1.record_throttle(45.5)
    limiter1.record_throttle(62.0)

    limiter2 = GitHubRateLimiter(persist_path=quota_file)
    assert (
        limiter1.get_total_throttles(),
        limiter1.get_total_wait_seconds(),
        limiter2.get_total_throttles(),
        limiter2.get_total_wait_seconds(),
    ) == (2, 107.5, 2, 107.5)


def test_the_rate_limit_check_reads_every_rate_limit_row_of_the_gh_output_table() -> None:
    """A rate limit is what the gh classifier's rate-limit rows call one (#983): the secondary
    rows count. gh project's owner lookup, a refused login, a missing scope and text gh echoes
    from the request, such as a `fix/...-retry-after` branch, do not."""
    limiter = GitHubRateLimiter()
    assert [
        limiter.is_rate_limit_error(said)
        for said in (
            "You have exceeded a secondary rate limit. Please wait a few minutes.",
            "gh: Please retry your request again later. (HTTP 403)",
            "HTTP 403: You have exceeded a secondary rate limit. Please retry after 120 seconds.",
            "API rate limit exceeded for user ID 12345",
            "unknown owner type",
            "gh: Bad credentials (HTTP 401)",
            "error: your authentication token is missing required scopes [read:project]",
            "HTTP 404: Not Found "
            "(https://api.github.com/repos/o/r/actions/runs?branch=fix%2F705-retry-after-handling)",
            "pull request create failed: GraphQL: No commits between main and "
            "fix/705-retry-after-handling (createPullRequest)",
            "repository not found",
            "",
        )
    ] == [True, True, True, True, False, False, False, False, False, False, False]


def test_run_gh_backs_off_on_a_rate_limit_only_a_secondary_row_names(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """gh's first answer names a secondary rate limit in words only the secondary rows hold:
    `run_gh` waits at least the secondary floor and sends the command again (#983)."""
    limiter = get_github_rate_limiter()
    monkeypatch.setattr(limiter, "min_interval", 0.01)
    refused = subprocess.CompletedProcess(
        ["gh", "api", "issues"], 1, "", "gh: Please retry your request again later. (HTTP 403)"
    )
    answered = subprocess.CompletedProcess(["gh", "api", "issues"], 0, "[]", "")
    with patch(
        "devops_cli.github.rate_limiter.run_subprocess", side_effect=[refused, answered]
    ) as run:
        res = run_gh(["api", "issues"], max_retries=2)
    assert (res.returncode, run.call_count, max(clock.waits) >= limiter.secondary_rate_wait) == (
        0,
        2,
        True,
    )


_PARTIAL_GRAPHQL_ANSWER = (
    '{{"data": {{"repository": {{"issues": {{"nodes": [{{"number": 705, "title": "{title}"}}]}}}}}},'
    ' "errors": [{{"type": "FORBIDDEN", "message": "Resource not accessible by integration"}}]}}'
)


@pytest.mark.parametrize(
    "title",
    [
        pytest.param("docs: what to do when the API rate limit exceeded", id="rate-limit-row"),
        pytest.param("unknown owner type", id="owner-lookup-phrase"),
    ],
)
def test_run_gh_backs_off_on_gh_s_stderr_never_on_github_s_answer_on_stdout(
    monkeypatch: pytest.MonkeyPatch, clock: ClockFake, title: str
) -> None:
    """A failed `gh api graphql` copies GitHub's partial answer, issue titles included, to
    stdout and writes only `gh: <message>` to stderr. A title that reads like a rate limit is
    GitHub's data, not gh's failure: the command is sent once, with no backoff (#983)."""
    limiter = get_github_rate_limiter()
    monkeypatch.setattr(limiter, "min_interval", 0.01)
    failed = subprocess.CompletedProcess(
        ["gh", "api", "graphql"],
        1,
        _PARTIAL_GRAPHQL_ANSWER.format(title=title),
        "gh: Resource not accessible by integration",
    )
    with patch("devops_cli.github.rate_limiter.run_subprocess", return_value=failed) as run:
        res = run_gh(["api", "graphql", "-f", "query=query { viewer { login } }"], max_retries=2)
    assert (
        res.returncode,
        run.call_count,
        max(clock.waits, default=0.0) < limiter.secondary_rate_wait,
    ) == (
        1,
        1,
        True,
    )


def test_each_identity_keeps_its_own_quota_and_response_cache(
    monkeypatch: pytest.MonkeyPatch, isolate_data_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Tokens A and B write separate ledgers and caches; A's cached read is never served to B.

    The identity directory is named by the token's SHA-256, so no path and no log line the
    ledger writes holds a token.
    """
    tokens = ("gho_identityAAAA", "gho_identityBBBB")
    caplog.set_level(logging.DEBUG, logger="devops_cli.github.rate_limiter")
    limiters: list[GitHubRateLimiter] = []
    answer = subprocess.CompletedProcess([], 0, stdout='[{"number": 1}]', stderr="")
    with patch("subprocess.run", return_value=answer) as run:
        for token in tokens:
            monkeypatch.setattr(process, "_github_token", token)
            limiter = get_github_rate_limiter()
            limiter.update_quota("core", remaining=5000, limit=5000, reset_epoch=time.time() + 60.0)
            run_gh(["api", "repos/octo/repo/issues"], use_cache=True)
            run_gh(["api", "repos/octo/repo/issues"], use_cache=True)
            limiters.append(limiter)
    identity_dirs = [limiter.persist_path.parent for limiter in limiters if limiter.persist_path]
    written = [str(path) for path in isolate_data_dir.rglob("*")]
    assert (
        [call.kwargs["env"]["GH_TOKEN"] for call in run.call_args_list],
        [directory.name for directory in identity_dirs],
        [len(list((directory / "responses").glob("*.json"))) for directory in identity_dirs],
        [(directory / "gh_quota.json").is_file() for directory in identity_dirs],
        [token for token in tokens if token in "\n".join(written) or token in caplog.text],
    ) == (
        list(tokens),
        [hashlib.sha256(token.encode()).hexdigest()[:16] for token in tokens],
        [1, 1],
        [True, True],
        [],
    )


# ── Write pacing decided from the request gh sends (#1125) ────────────────────

_MUTATION = (
    "mutation ResolveThread($id: ID!) { resolveReviewThread(input: {threadId: $id}) "
    "{ thread { id } } }"
)
_QUERY = "query Viewer { viewer { login } }"
_TWO_OPERATIONS = f"{_QUERY}\n{_MUTATION}"
_AFTER_A_COMMENT = f"# resolve the thread the reviewer answered\n{_MUTATION}"
_AFTER_A_FRAGMENT = (
    "fragment ThreadId on PullRequestReviewThread { id }\n"
    "mutation ResolveThread($id: ID!) { resolveReviewThread(input: {threadId: $id}) "
    "{ thread { ...ThreadId } } }"
)


def _paced_as_write(args: list[str], *, input: str | None = None, cwd: Path | None = None) -> bool:
    """Run `args` through `run_gh` with gh stubbed; the `is_mutation` its one acquire got."""

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=gh),
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as acquire,
    ):
        run_gh(args, input=input, cwd=cwd)
    (call,) = acquire.call_args_list
    return bool(call.kwargs["is_mutation"])


_API_REQUESTS: list[tuple[str, list[str], str | None, dict[str, str], bool]] = [
    # The issue's table, with the corrected answers.
    ("graphql-mutation-in-a-field", ["api", "graphql", "-f", f"query={_MUTATION}"], None, {}, True),
    (
        "graphql-mutation-on-stdin",
        ["api", "graphql", "--input", "-"],
        json.dumps({"query": _MUTATION, "variables": {"id": "T1"}}),
        {},
        True,
    ),
    (
        "rest-fields-post",
        ["api", "repos/o/r/pulls", "-f", "title=t", "-f", "head=h"],
        None,
        {},
        True,
    ),
    (
        "rest-input-file-posts",
        ["api", "repos/o/r/rulesets", "--input", "file.json"],
        None,
        {"file.json": "{}"},
        True,
    ),
    (
        "rest-explicit-post",
        ["api", "-X", "POST", "repos/o/r/issues", "-f", "title=t"],
        None,
        {},
        True,
    ),
    # The document's operation decides a GraphQL request.
    (
        "mutation-after-a-comment",
        ["api", "graphql", "-f", f"query={_AFTER_A_COMMENT}"],
        None,
        {},
        True,
    ),
    (
        "mutation-after-a-fragment",
        ["api", "graphql", "-f", f"query={_AFTER_A_FRAGMENT}"],
        None,
        {},
        True,
    ),
    ("shorthand-query", ["api", "graphql", "-f", "query={ viewer { login } }"], None, {}, False),
    ("named-query", ["api", "graphql", "-f", f"query={_QUERY}"], None, {}, False),
    (
        "operation-name-selects-the-query",
        ["api", "graphql", "-f", f"query={_TWO_OPERATIONS}", "-f", "operationName=Viewer"],
        None,
        {},
        False,
    ),
    (
        "operation-name-selects-the-mutation",
        ["api", "graphql", "-f", f"query={_TWO_OPERATIONS}", "-F", "operationName=ResolveThread"],
        None,
        {},
        True,
    ),
    (
        "body-operation-name-selects-the-query",
        ["api", "graphql", "--input", "-"],
        json.dumps({"query": _TWO_OPERATIONS, "operationName": "Viewer"}),
        {},
        False,
    ),
    (
        "two-operations-and-no-name",
        ["api", "graphql", "-f", f"query={_TWO_OPERATIONS}"],
        None,
        {},
        True,
    ),
    (
        "typed-field-reads-a-mutation-file",
        ["api", "graphql", "-F", "query=@op.graphql"],
        None,
        {"op.graphql": _MUTATION},
        True,
    ),
    (
        "typed-field-reads-a-query-file",
        ["api", "graphql", "-F", "query=@op.graphql"],
        None,
        {"op.graphql": _QUERY},
        False,
    ),
    ("typed-field-reads-stdin", ["api", "graphql", "-F", "query=@-"], _QUERY, {}, False),
    (
        "raw-field-sends-the-literal-not-the-file",
        ["api", "graphql", "-f", "query=@op.graphql"],
        None,
        {"op.graphql": _QUERY},
        True,
    ),
    (
        "input-file-holds-a-query",
        ["api", "graphql", "--input", "body.json"],
        None,
        {"body.json": json.dumps({"query": _QUERY})},
        False,
    ),
    # Every way gh accepts a method, and its default.
    (
        "method-get-with-a-field",
        ["api", "--method", "GET", "search/issues", "-f", "q=x"],
        None,
        {},
        False,
    ),
    ("attached-get", ["api", "-XGET", "search/issues", "-f", "q=x"], None, {}, False),
    (
        "accept-header-and-no-field",
        ["api", "-H", "Accept: application/vnd.github.raw+json", "repos/o/r/readme"],
        None,
        {},
        False,
    ),
    ("plain-get", ["api", "repos/o/r/pulls"], None, {}, False),
    ("attached-post", ["api", "-XPOST", "repos/o/r/pages/builds"], None, {}, True),
    ("equals-post", ["api", "-X=POST", "repos/o/r/pages/builds"], None, {}, True),
    ("long-equals-patch", ["api", "--method=PATCH", "repos/o/r/milestones/1"], None, {}, True),
    ("lower-case-delete", ["api", "--method", "delete", "repos/o/r/milestones/1"], None, {}, True),
    ("combined-include-and-put", ["api", "-iXPUT", "repos/o/r/pulls/1/merge"], None, {}, True),
    ("attached-raw-field", ["api", "repos/o/r/issues", "-ftitle=t"], None, {}, True),
    ("long-typed-field", ["api", "repos/o/r/pulls", "--field=draft=true"], None, {}, True),
    # `--paginate` doesn't make a write a read.
    (
        "paginated-rest-fields-post",
        ["api", "repos/o/r/issues", "--paginate", "-f", "title=t"],
        None,
        {},
        True,
    ),
    (
        "paginated-graphql-mutation",
        ["api", "graphql", "--paginate", "-f", "query=mutation { x }"],
        None,
        {},
        True,
    ),
    (
        "paginated-graphql-query",
        [
            "api",
            "graphql",
            "--paginate",
            "-f",
            "query=query($endCursor: String) { viewer { login } }",
        ],
        None,
        {},
        False,
    ),
    # Whatever cannot be read counts as a write.
    ("document-does-not-parse", ["api", "graphql", "-f", "query=query { viewer {"], None, {}, True),
    ("paginated-graphql-without-a-document", ["api", "graphql", "--paginate"], None, {}, True),
    (
        "paginated-graphql-query-on-unseen-stdin",
        ["api", "graphql", "--paginate", "-F", "query=@-"],
        None,
        {},
        True,
    ),
    (
        "paginated-graphql-body-on-unseen-stdin",
        ["api", "graphql", "--paginate", "--input", "-"],
        None,
        {},
        True,
    ),
    (
        "paginated-graphql-unreadable-file",
        ["api", "graphql", "--paginate", "-F", "query=@missing.graphql"],
        None,
        {},
        True,
    ),
    ("input-body-is-not-json", ["api", "graphql", "--input", "-"], _QUERY, {}, True),
    ("unreadable-file", ["api", "graphql", "-F", "query=@missing.graphql"], None, {}, True),
    ("argv-does-not-parse", ["api", "repos/o/r/pulls", "-X"], None, {}, True),
    ("graphql-without-a-document", ["api", "graphql"], None, {}, True),
    # Known limit: forms gh's flag parser accepts and argparse doesn't, so they count as writes.
    ("switch-given-a-value", ["api", "repos/o/r/pulls", "--paginate=true"], None, {}, True),
    ("dash-leading-value", ["api", "repos/o/r/pulls", "--jq", "-.a"], None, {}, True),
]


@pytest.mark.parametrize(
    ("args", "stdin", "files", "write"),
    [case[1:] for case in _API_REQUESTS],
    ids=[case[0] for case in _API_REQUESTS],
)
def test_gh_api_is_paced_as_a_write_from_the_request_gh_sends(
    tmp_path: Path, args: list[str], stdin: str | None, files: dict[str, str], write: bool
) -> None:
    """A `gh api` request is a write when gh sends POST, PUT, PATCH or DELETE, or, for
    `graphql`, when the operation it runs is a mutation. Relative `@file` and `--input` paths
    resolve against `run_gh`'s cwd, and stdin is `run_gh`'s input."""
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert _paced_as_write(args, input=stdin, cwd=tmp_path) is write


_HIGH_LEVEL_READS = [
    ["issue", "list", "--label", "sync"],
    ["label", "list", "--json", "name"],
    ["pr", "checks", "5"],
    ["pr", "diff", "5", "--color", "never"],
    ["pr", "list", "--state", "open"],
    ["pr", "view", "5", "--json", "title"],
    ["project", "field-list", "2", "--owner", "o"],
    ["project", "item-list", "2", "--owner", "o", "--format", "json"],
    ["project", "list", "--owner", "@me"],
    ["release", "list"],
    ["release", "view", "v0.2.26"],
    ["repo", "view", "o/r"],
    ["run", "list", "--branch", "main"],
    ["run", "view", "1"],
    ["search", "issues", "create", "--repo", "o/r"],
    # gh takes `-R`/`--repo` and `--owner` before the verb too.
    ["-R", "o/r", "issue", "list"],
    ["issue", "-R", "o/r", "list"],
    ["pr", "--repo", "o/r", "view", "1"],
    ["--repo", "o/r", "pr", "view", "1"],
    ["project", "--owner", "o", "item-list", "2"],
]
_HIGH_LEVEL_WRITES = [
    ["issue", "close", "5"],
    ["issue", "create", "--title", "t", "--body", "b"],
    ["label", "create", "sync"],
    ["pr", "close", "5"],
    ["pr", "create", "--title", "list"],
    ["pr", "edit", "5", "--add-label", "x"],
    ["pr", "ready", "5"],
    ["project", "create", "--owner", "o", "--title", "Roadmap"],
    ["project", "field-create", "2", "--owner", "o", "--name", "Value"],
    ["project", "field-delete", "--id", "F1"],
    ["project", "item-add", "2", "--owner", "o", "--url", "https://github.com/o/r/issues/1"],
    ["project", "item-create", "2", "--owner", "o", "--title", "t"],
    ["project", "item-delete", "2", "--owner", "o", "--id", "I1"],
    ["project", "item-edit", "--id", "I1", "--project-id", "P1", "--text", "view"],
    ["project", "link", "3", "--owner", "o", "--repo", "o/r"],
    ["release", "edit", "v0.2.26", "--draft=false"],
]


@pytest.mark.parametrize(
    ("args", "write"),
    [(args, False) for args in _HIGH_LEVEL_READS] + [(args, True) for args in _HIGH_LEVEL_WRITES],
    ids=[" ".join(args) for args in _HIGH_LEVEL_READS + _HIGH_LEVEL_WRITES],
)
def test_a_high_level_gh_command_is_classified_by_the_verb_in_the_verb_position(
    args: list[str], write: bool
) -> None:
    """A read verb in the verb position, or the `search` group, is a read; any other verb is a
    write, whatever words its options carry."""
    assert _paced_as_write(args) is write


def test_a_paginated_write_is_sent_once_as_given_and_paced_as_a_write() -> None:
    """`run_gh` hands gh a `--paginate` request as given, so a write with `--paginate` goes to
    gh once, unchanged, after one write acquire."""
    args = ["api", "repos/o/r/issues", "--paginate", "-f", "title=t"]
    sent: list[list[str]] = []

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        sent.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "{}", "")

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=gh),
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as acquire,
    ):
        run_gh(args)
    assert (sent, [call.kwargs.get("is_mutation") for call in acquire.call_args_list]) == (
        [["gh", *args]],
        [True],
    )


def test_gh_auth_is_not_paced() -> None:
    """`gh auth` runs outside the ledger, so it acquires nothing."""
    answer = subprocess.CompletedProcess(["gh"], 0, "", "")
    with (
        patch("devops_cli.github.rate_limiter.run_subprocess", return_value=answer),
        patch.object(GitHubRateLimiter, "acquire", autospec=True) as acquire,
    ):
        run_gh(["auth", "status"])
    assert acquire.call_count == 0


def test_the_classifier_takes_a_request_description() -> None:
    """The classifier reads a request description, so a caller that builds its own request
    (#983's session) asks the same question `run_gh`'s argv parser does."""
    from devops_cli.github.request_classifier import GitHubRequest, is_write_request

    requests = [
        GitHubRequest(method="GET", endpoint="repos/o/r/pulls"),
        GitHubRequest(method="post", endpoint="repos/o/r/issues"),
        GitHubRequest(method="DELETE", endpoint="repos/o/r/milestones/1"),
        GitHubRequest(method="POST", endpoint="graphql", document=_QUERY),
        GitHubRequest(method="POST", endpoint="graphql", document=_MUTATION),
        GitHubRequest(
            method="POST", endpoint="graphql", document=_TWO_OPERATIONS, operation_name="Viewer"
        ),
        GitHubRequest(method="POST", endpoint="graphql", document=_TWO_OPERATIONS),
        GitHubRequest(method="POST", endpoint="graphql"),
    ]
    assert [is_write_request(request) for request in requests] == [
        False,
        True,
        True,
        False,
        True,
        False,
        True,
        True,
    ]


def test_graphql_core_is_imported_only_to_classify_a_graphql_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No module imports graphql-core at load time, and only a `graphql` request needs it:
    with its import blocked, REST requests and high-level commands are still classified."""
    import ast
    import sys

    import devops_cli.github.rate_limiter as rate_limiter_module
    import devops_cli.github.request_classifier as classifier_module
    from devops_cli.github.request_classifier import is_write_gh_command

    def top_level_imports(path: str) -> set[str]:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
        names = {a.name for n in tree.body if isinstance(n, ast.Import) for a in n.names}
        return names | {n.module or "" for n in tree.body if isinstance(n, ast.ImportFrom)}

    loaded = top_level_imports(str(rate_limiter_module.__file__)) | top_level_imports(
        str(classifier_module.__file__)
    )
    monkeypatch.setitem(sys.modules, "graphql", None)
    answers = [
        is_write_gh_command(["api", "repos/o/r/pulls"]),
        is_write_gh_command(["api", "-X", "POST", "repos/o/r/issues"]),
        is_write_gh_command(["issue", "list"]),
    ]
    with pytest.raises(ImportError):
        is_write_gh_command(["api", "graphql", "-f", f"query={_QUERY}"])
    assert ([name for name in loaded if name.split(".")[0] == "graphql"], answers) == (
        [],
        [False, True, False],
    )


def test_the_write_interval_holds_across_resources(clock: ClockFake) -> None:
    """A REST write and a GraphQL write acquired at the same instant are scheduled at least
    `mutation_min_interval` apart; a GraphQL query at that instant is paced by its quota."""
    now = 1_000_000.0
    clock.move_to(now)

    def limiter() -> GitHubRateLimiter:
        fresh = GitHubRateLimiter(mutation_min_interval=1.0)
        for resource in ("core", "graphql"):
            fresh.update_quota(resource, remaining=5000, limit=5000, reset_epoch=now + 3600.0)
        return fresh

    writes = limiter()
    rest_write = writes.acquire("core", is_mutation=True)
    clock.move_to(now)
    graphql_write = writes.acquire("graphql", is_mutation=True)
    clock.move_to(now)
    reads = limiter()
    reads.acquire("core", is_mutation=True)
    clock.move_to(now)
    graphql_read = reads.acquire("graphql")
    assert (rest_write, graphql_write, graphql_read, len(clock.waits)) == (
        1.0,
        2.0,
        pytest.approx(0.72),
        4,
    )


def _write_pacing_limiter(now: float, *, core_remaining: int = 5000) -> GitHubRateLimiter:
    """A limiter with a one-second write interval and both quotas resetting in an hour."""
    limiter = GitHubRateLimiter(mutation_min_interval=1.0)
    limiter.update_quota("core", remaining=core_remaining, limit=5000, reset_epoch=now + 3600.0)
    limiter.update_quota("graphql", remaining=5000, limit=5000, reset_epoch=now + 3600.0)
    return limiter


def test_a_write_pushed_by_another_resource_does_not_delay_reads_after_it(
    clock: ClockFake,
) -> None:
    """A core write pushed to 2.0 s by a GraphQL write leaves core's own schedule at its
    quota's pace, so a core read after it waits 1.0 s plus core's pace (about 0.72 s), as it
    would with no GraphQL write."""
    now = 1_000_000.0
    clock.move_to(now)
    limiter = _write_pacing_limiter(now)
    sleeps = []
    for resource, is_mutation in (("graphql", True), ("core", True), ("core", False)):
        clock.move_to(now)
        sleeps.append(limiter.acquire(resource, is_mutation=is_mutation))
    assert sleeps == [1.0, 2.0, pytest.approx(1.72, abs=0.01)]


def test_a_read_does_not_wait_out_another_resources_quota_reset(clock: ClockFake) -> None:
    """With core's quota spent, a core write waits for core's reset and a GraphQL write after it
    keeps the interval, but a GraphQL read is paced by the GraphQL quota alone."""
    now = 1_000_000.0
    clock.move_to(now)
    limiter = _write_pacing_limiter(now, core_remaining=0)
    sleeps = []
    for resource, is_mutation in (("core", True), ("graphql", True), ("graphql", False)):
        clock.move_to(now)
        sleeps.append(limiter.acquire(resource, is_mutation=is_mutation))
    assert sleeps == [3600.0, 3601.0, pytest.approx(1.72, abs=0.01)]


@pytest.mark.parametrize(
    ("args", "cached"),
    [
        (["pr", "create", "--title", "list"], False),
        (["issue", "edit", "7", "--body", "view"], False),
        (["project", "item-edit", "--id", "status"], False),
        (["pr", "list"], True),
        (["pr", "--repo", "o/r", "view", "1"], True),
        (["project", "--owner", "o", "item-list", "2"], True),
    ],
    ids=["create-titled-list", "edit-body-view", "item-edit", "list", "repo-view", "owner-items"],
)
def test_a_cli_read_is_cached_only_by_the_verb_in_the_verb_position(
    args: list[str], cached: bool
) -> None:
    """A read verb anywhere in argv made a write cacheable (`pr create --title list`); the
    verb-position parser decides instead (#1125)."""
    from devops_cli.github.rate_limiter import _should_cache

    assert _should_cache(args, use_cache=True) is cached


def _graphql_answer(cost: int, remaining: int) -> str:
    rate_limit = {
        "cost": cost,
        "limit": 5000,
        "remaining": remaining,
        "used": 5000 - remaining,
        "resetAt": "2099-01-01T00:00:00Z",
    }
    return json.dumps({"data": {"rateLimit": rate_limit, "viewer": {"login": "x"}}})


def test_run_gh_charges_graphql_by_the_points_the_response_reports() -> None:
    """A GraphQL response that reports `rateLimit.cost` charges the limiter that many points
    and sets the points left; one that reports nothing charges no points, its estimate (2)
    taken from the points left instead (#1125)."""
    answers = iter([_graphql_answer(7, 4000), _graphql_answer(12, 3988), json.dumps({"data": {}})])

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(cmd, 0, next(answers), "")

    query = ["api", "graphql", "-f", "query=query { viewer { login } }"]
    limiter = get_github_rate_limiter()
    with patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=gh):
        charged = []
        for _ in range(3):
            run_gh(query)
            charged.append(limiter.points_charged("graphql"))
    assert (charged, limiter.get_quota("graphql").remaining) == ([7, 19, 19], 3986)


# ── A call at a quota window's reset (#1364) ──────────────────────────────────

# 2026-10-08T12:00:00Z. GitHub's `reset` is whole epoch seconds.
_RESET = 1_791_460_800.0
_ISSUES = ["api", "repos/o/r/issues"]
_RATE_LIMIT = ["api", "rate_limit"]
_REAL_RUN = subprocess.run


class _GhAtTheReset:
    """gh faked at the process edge: `gh api rate_limit` answers `resources`, exits with the
    status and stderr of `refusal`, or with `times_out` runs past its timeout, and any other gh
    command answers `[]`. Every gh argv is recorded, from any thread. A command that is not gh,
    such as the `uname -p` the tracer runs on first use, runs for real, so no test depends on
    which test warmed that cache."""

    def __init__(
        self,
        resources: dict[str, Any],
        *,
        refusal: tuple[int, str] | None = None,
        times_out: bool = False,
    ) -> None:
        self.resources = resources
        self.refusal = refusal
        self.times_out = times_out
        self.argvs: list[list[str]] = []
        self._lock = threading.Lock()

    def __call__(self, cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] != "gh":
            return _REAL_RUN(cmd, **kwargs)
        with self._lock:
            self.argvs.append(list(cmd[1:]))
        if cmd[1:] != _RATE_LIMIT:
            return subprocess.CompletedProcess(cmd, 0, "[]", "")
        if self.times_out:
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        if self.refusal is not None:
            return subprocess.CompletedProcess(cmd, self.refusal[0], "", self.refusal[1])
        return subprocess.CompletedProcess(cmd, 0, json.dumps({"resources": self.resources}), "")

    def refreshes(self) -> int:
        return self.argvs.count(_RATE_LIMIT)

    def commands(self) -> list[list[str]]:
        return [argv for argv in self.argvs if argv != _RATE_LIMIT]


def _window(remaining: int, reset: float, limit: int = 5000) -> dict[str, int]:
    return {"limit": limit, "remaining": remaining, "used": limit - remaining, "reset": int(reset)}


@contextmanager
def _clock_at(
    clock: ClockFake, now: float, gh: _GhAtTheReset, *, stored_core_reset: float
) -> Iterator[ClockFake]:
    """Freeze the clock at `now` with gh faked, store a `core` window that resets at
    `stored_core_reset`, and yield the recorder of every wait."""
    clock.move_to(now)
    clock.waits.clear()
    with patch("subprocess.run", side_effect=gh):
        get_github_rate_limiter().update_quota(
            "core", remaining=7, limit=5000, used=4993, reset_epoch=stored_core_reset
        )
        yield clock


def test_a_call_just_past_a_reset_waits_out_the_reset_second(
    caplog: pytest.LogCaptureFixture, clock: ClockFake
) -> None:
    """GitHub still reports the window that reset 0.5 s ago: the call refreshes once, waits until a
    second past that reset and runs, logging the boundary once. The request is not counted against
    the old window."""
    caplog.set_level(logging.INFO, logger="devops_cli.github.rate_limiter")
    gh = _GhAtTheReset({"core": _window(7, _RESET)})
    with _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET):
        proc = run_gh(_ISSUES)
        core = get_github_rate_limiter().get_quota("core")
    boundary = [r.getMessage() for r in caplog.records if "quota window reset" in r.getMessage()]
    assert (
        proc.returncode,
        gh.refreshes(),
        gh.commands(),
        clock.waits,
        (core.remaining, core.used),
        boundary,
    ) == (
        0,
        1,
        [_ISSUES],
        [0.5],
        (7, 4993),
        [
            "[RateLimit] 'core' quota window reset at 2026-10-08T12:00:00Z, 0.50s ago; "
            "waiting until at least 2026-10-08T12:00:01Z"
        ],
    )


def test_a_call_after_an_idle_hour_paces_from_the_new_window(clock: ClockFake) -> None:
    """A stored window that ended an hour ago refreshes into the new one and paces from it:
    3,600 s over 5,000 requests is 0.72 s, with no clock error."""
    gh = _GhAtTheReset({"core": _window(5000, _RESET + 3600.0)})
    with _clock_at(clock, _RESET, gh, stored_core_reset=_RESET - 3600.0):
        proc = run_gh(_ISSUES)
    waits = [round(wait, 2) for wait in clock.waits]
    assert (proc.returncode, gh.refreshes(), gh.commands(), waits) == (0, 1, [_ISSUES], [0.72])


def test_a_clock_within_the_bound_past_the_reset_runs_and_refreshes_again(
    clock: ClockFake,
) -> None:
    """The clock is 2 s past a reset GitHub keeps repeating: each call runs with no wait, and the
    next call refreshes again before it runs."""
    gh = _GhAtTheReset({"core": _window(7, _RESET)})
    with _clock_at(clock, _RESET + 2.0, gh, stored_core_reset=_RESET):
        codes = [run_gh(_ISSUES).returncode, run_gh(_ISSUES).returncode]
    assert (codes, gh.argvs, clock.waits) == (
        [0, 0],
        [_RATE_LIMIT, _ISSUES, _RATE_LIMIT, _ISSUES],
        [],
    )


def test_a_clock_past_the_bound_fails_closed_naming_both_clocks(clock: ClockFake) -> None:
    """GitHub's fresh answer resets 60 s before the local clock: the clocks disagree, the error
    names the reset, the clock and the gap, carries no `reset_epoch` a pause could key on, and the
    command never runs."""
    gh = _GhAtTheReset({"core": _window(7, _RESET)})
    with (
        _clock_at(clock, _RESET + 60.0, gh, stored_core_reset=_RESET),
        pytest.raises(GitHubRateLimitError) as raised,
    ):
        run_gh(_ISSUES)
    details = raised.value.details
    assert (
        raised.value.message,
        {key: details.get(key) for key in ("reported_reset", "local_clock", "gap_seconds")},
        "reset_epoch" in details,
        gh.commands(),
        clock.waits,
    ) == (
        "The local clock and GitHub's disagree: GitHub's 'core' quota window reset at "
        "2026-10-08T12:00:00Z and the local clock reads 2026-10-08T12:01:00Z, 60.00s past it, "
        "more than the 5s they may differ. Correct the local clock.",
        {
            "reported_reset": "2026-10-08T12:00:00Z",
            "local_clock": "2026-10-08T12:01:00Z",
            "gap_seconds": "60.00",
        },
        False,
        [],
        [],
    )


def test_a_failed_refresh_fails_closed_naming_the_gh_failure(clock: ClockFake) -> None:
    """`gh api rate_limit` exits 1 with a 502: the unread error names gh's failure and the
    command never runs."""
    gh = _GhAtTheReset({}, refusal=(1, "HTTP 502: Bad Gateway"))
    with (
        _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET),
        pytest.raises(GitHubOperationError) as raised,
    ):
        run_gh(_ISSUES)
    assert (
        type(raised.value),
        raised.value.message,
        gh.refreshes(),
        gh.commands(),
        clock.waits,
    ) == (
        GitHubUnreadError,
        "Failed to refresh rate limits from GitHub API: HTTP 502: Bad Gateway",
        1,
        [],
        [],
    )


@pytest.mark.parametrize(
    ("refusal", "error", "status"),
    [
        pytest.param(
            (1, "gh: Bad credentials (HTTP 401)"), GitHubUnauthenticatedError, 401, id="401"
        ),
        pytest.param(
            (4, "To get started with GitHub CLI, please run:  gh auth login"),
            GitHubUnauthenticatedError,
            None,
            id="exit-4",
        ),
        pytest.param(
            (1, "gh: API rate limit exceeded for user ID 1. (HTTP 403)"),
            GitHubRateLimitError,
            403,
            id="rate-limited",
        ),
        pytest.param((1, ""), GitHubUnreadError, None, id="silent"),
    ],
)
def test_a_failed_refresh_raises_the_class_the_gh_classifier_names_or_unread(
    clock: ClockFake,
    refusal: tuple[int, str],
    error: type[GitHubOperationError],
    status: int | None,
) -> None:
    """A failed refresh raises the class the gh classifier names: GitHub refusing gh's token
    (HTTP 401) or gh exiting 4 ("requires authentication") the unauthenticated error, a rate
    limit the rate-limit error; a failure it names no class for leaves the quota unread. Each
    carries gh's exit status and the status gh wrote, as ints, and the command never runs."""
    gh = _GhAtTheReset({}, refusal=refusal)
    with (
        _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET),
        pytest.raises(GitHubOperationError) as raised,
    ):
        run_gh(_ISSUES)
    details = raised.value.details
    assert (
        type(raised.value),
        details.get("status"),
        details["exit_code"],
        details["operation"],
        gh.commands(),
    ) == (error, status, refusal[0], "refresh_quota", [])


def test_a_refresh_that_times_out_leaves_the_quota_unread(clock: ClockFake) -> None:
    """`gh api rate_limit` running past its timeout raises the unread error naming the
    timeout, not a raw `TimeoutExpired`, and the command never runs."""
    gh = _GhAtTheReset({}, times_out=True)
    with (
        _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET),
        pytest.raises(GitHubOperationError) as raised,
    ):
        run_gh(_ISSUES)
    assert (
        type(raised.value),
        raised.value.details["operation"],
        "gh api rate_limit timed out after" in raised.value.message,
        gh.refreshes(),
        gh.commands(),
    ) == (GitHubUnreadError, "refresh_quota", True, 1, [])


def test_an_empty_refresh_answer_leaves_the_quota_unread(clock: ClockFake) -> None:
    """`gh api rate_limit` exiting 0 with nothing on stdout raises the unread error, so a
    caller that stops on a rate limit, such as intake, does not stop on it, and the command
    never runs."""
    gh = _GhAtTheReset({}, refusal=(0, ""))
    with (
        _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET),
        pytest.raises(GitHubOperationError) as raised,
    ):
        run_gh(_ISSUES)
    assert (
        type(raised.value),
        raised.value.message,
        raised.value.details["operation"],
        gh.refreshes(),
        gh.commands(),
    ) == (GitHubUnreadError, "GitHub rate_limit API returned empty output", "refresh_quota", 1, [])


def test_an_answer_without_the_resource_fails_closed_over_a_stale_entry(clock: ClockFake) -> None:
    """The stored `core` window reset 0.5 s ago and GitHub's answer lists only `graphql` and
    `search`: the error names `core` and the listed resources, and the command never runs."""
    gh = _GhAtTheReset(
        {"graphql": _window(4000, _RESET + 1800.0), "search": _window(30, _RESET + 60.0, limit=30)}
    )
    with (
        _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET),
        pytest.raises(GitHubRateLimitError) as raised,
    ):
        run_gh(_ISSUES)
    details = raised.value.details
    assert (
        raised.value.message,
        details.get("reported_resources"),
        "reset_epoch" in details,
        gh.commands(),
        clock.waits,
    ) == (
        "GitHub's rate_limit answer has no 'core' quota with remaining and reset; "
        "it reports: graphql, search",
        "graphql, search",
        False,
        [],
        [],
    )


def test_two_workers_at_the_reset_both_wait_it_out_and_run(clock: ClockFake) -> None:
    """Two threads call `run_gh` at the boundary of the first case: each refreshes, waits 0.5 s
    and runs its command, and neither raises."""
    gh = _GhAtTheReset({"core": _window(7, _RESET)})
    with (
        _clock_at(clock, _RESET + 0.5, gh, stored_core_reset=_RESET),
        clock.concurrent_sleeps(2),
        ThreadPoolExecutor(max_workers=2) as workers,
    ):
        codes = list(workers.map(lambda _: run_gh(_ISSUES).returncode, range(2)))
    assert (codes, gh.refreshes(), gh.commands(), clock.waits) == (
        [0, 0],
        2,
        [_ISSUES, _ISSUES],
        [0.5, 0.5],
    )


# ── A rate-limit check whose output a gh flag changes (#1886) ─────────────────

_ANSWER = {"resources": {"core": _window(4830, _RESET), "graphql": _window(4321, _RESET)}}
_BODY = json.dumps(_ANSWER)


def _gh_printing(stdout: str, argvs: list[list[str]]) -> Any:
    """gh faked at the process edge: each gh command prints `stdout`, exits 0 and is recorded in
    `argvs`. A command that is not gh runs for real, as `_GhAtTheReset` lets it."""

    def gh(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[0] != "gh":
            return _REAL_RUN(cmd, **kwargs)
        argvs.append(list(cmd[1:]))
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    return gh


def _quotas() -> dict[str, tuple[int | None, float | None]]:
    limiter = get_github_rate_limiter()
    return {
        resource: (limiter.get_quota(resource).remaining, limiter.get_quota(resource).reset_epoch)
        for resource in ("core", "graphql")
    }


@pytest.mark.parametrize(
    ("flags", "printed"),
    [
        pytest.param(["--jq", ".resources.graphql.remaining"], "4321\n", id="jq"),
        pytest.param(["-q", ".resources.graphql.remaining"], "4321\n", id="q"),
        pytest.param(["--template", "{{.resources.graphql.remaining}}"], "4321", id="template"),
        pytest.param(["-t", "{{.resources.graphql.remaining}}"], "4321", id="t"),
        pytest.param(["--paginate", "--slurp"], f"[{_BODY}]\n", id="slurp"),
        pytest.param(
            ["--verbose"],
            "* Request to https://api.github.com/rate_limit\n> GET /rate_limit HTTP/1.1\n\n"
            f"< HTTP/2.0 200 OK\n\n{_BODY}\n* Request took 1ms\n",
            id="verbose",
        ),
        pytest.param(["--silent"], "", id="silent"),
    ],
)
def test_a_rate_limit_check_whose_output_a_flag_changes_returns_it_and_reads_no_quota(
    flags: list[str], printed: str
) -> None:
    """With an output flag, gh prints something other than the /rate_limit answer: `run_gh`
    returns what gh printed, runs gh once, and keeps the stored quotas."""
    argvs: list[list[str]] = []
    before = _quotas()
    with patch("subprocess.run", side_effect=_gh_printing(printed, argvs)):
        proc = run_gh(["api", "rate_limit", *flags])
    assert (proc.returncode, proc.stdout, argvs, _quotas()) == (
        0,
        printed,
        [["api", "rate_limit", *flags]],
        before,
    )


@pytest.mark.parametrize(
    ("flags", "printed"),
    [
        pytest.param([], _BODY, id="plain"),
        pytest.param(
            ["--include"], f"HTTP/2.0 200 OK\nContent-Type: application/json\n\n{_BODY}", id="i"
        ),
        pytest.param(["--paginate"], _BODY, id="paginate"),
    ],
)
def test_a_rate_limit_check_that_prints_the_answer_reads_the_quota_from_it(
    flags: list[str], printed: str
) -> None:
    """gh prints the /rate_limit answer whole, after the status line and headers `--include`
    adds: `run_gh` stores the quota of each resource it reports."""
    argvs: list[list[str]] = []
    with patch("subprocess.run", side_effect=_gh_printing(printed, argvs)):
        proc = run_gh(["api", "rate_limit", *flags])
    assert (proc.returncode, argvs, _quotas()) == (
        0,
        [["api", "rate_limit", *flags]],
        {"core": (4830, _RESET), "graphql": (4321, _RESET)},
    )


# ── No burst ceiling stall (#1118) ──────────────────────────────────────────


def test_sixty_one_reads_do_not_stall_behind_a_fixed_burst_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify 61 consecutive gh reads do not stall behind a fixed burst ceiling.

    Before removing ratelimit, the 61st call triggers sleep_and_retry, asking for
    the remainder of the 60s window (~59s) and raising AssertionError.
    """
    limiter = get_github_rate_limiter()
    limiter.update_quota("core", remaining=5000, limit=5000, reset_epoch=time.time() + 60.0)

    runner_calls: list[list[str]] = []
    answer = subprocess.CompletedProcess(["gh", "api", "repos/o/r"], 0, "{}", "")

    def fake_runner(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        runner_calls.append(cmd)
        return answer

    recorded_sleeps: list[float] = []

    def fake_sleep(seconds: float) -> None:
        if seconds >= 1.0:
            raise AssertionError(f"Unexpected sleep >= 1.0s: {seconds}")
        recorded_sleeps.append(seconds)

    monkeypatch.setattr(time, "sleep", fake_sleep)
    with patch("devops_cli.github.rate_limiter.run_subprocess", side_effect=fake_runner):
        for _ in range(61):
            run_gh(["api", "repos/o/r"])

    assert len(runner_calls) == 61
    assert len(recorded_sleeps) == 61


def test_parallel_callers_stay_spaced_across_threads() -> None:
    """Two threads calling run_gh stay spaced by quota spacing across threads."""
    barrier = threading.Barrier(2)
    recorded_sleeps: list[float] = []
    sleep_lock = threading.Lock()
    answer = subprocess.CompletedProcess(["gh", "pr", "list"], 0, "[]", "")

    def recording_sleep(seconds: float) -> None:
        with sleep_lock:
            recorded_sleeps.append(seconds)

    def worker() -> None:
        barrier.wait()
        run_gh(["pr", "list"])

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess", return_value=answer),
        patch("time.sleep", side_effect=recording_sleep),
    ):
        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    assert len(recorded_sleeps) == 2
    larger = max(recorded_sleeps)
    smaller = min(recorded_sleeps)
    assert larger - smaller >= 0.5


def test_paginate_without_endpoint_calls_acquire() -> None:
    """Non-exempt gh command without an endpoint still calls acquire before starting gh."""
    answer = subprocess.CompletedProcess(["gh", "api", "--paginate"], 0, "[]", "")
    with (
        patch("devops_cli.github.rate_limiter.run_subprocess", return_value=answer) as runner,
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as mock_acquire,
    ):
        proc = run_gh(["api", "--paginate"])

    assert proc.returncode == 0
    assert mock_acquire.call_count == 1
    assert runner.call_count == 1
