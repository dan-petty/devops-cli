"""Unit tests for GitHub rate limiter and request pacing subsystem.

Verifies the simple delay formula:
    request delay = time in seconds until next quota reset for this subcommand / remaining requests
and mandatory pause enforcement.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.exceptions.git import GitHubRateLimitError
from devops_cli.github.rate_limiter import (
    GitHubRateLimiter,
    QuotaState,
    calculate_request_delay,
    get_github_rate_limiter,
    reset_github_rate_limiter,
    run_gh,
)


@pytest.fixture(autouse=True)
def isolate_rate_limiter() -> Generator[None]:
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


def test_calculate_delay_rejects_negative_time_left() -> None:
    """Verify calculate_delay raises GitHubRateLimitError when reset_epoch is in the past."""

    limiter = GitHubRateLimiter()
    now = time.time()
    past_state = QuotaState(remaining=0, limit=5000, reset_epoch=now - 100.0)
    with patch.object(limiter, "_resolve_quota_state", return_value=past_state):
        with pytest.raises(GitHubRateLimitError, match="time until reset must be non-negative"):
            limiter.calculate_delay("core")


def test_rate_limiter_no_initial_quotas() -> None:
    """Verify rate limiter has no hardcoded initial quotas and raises error if refresh fails."""
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
        with pytest.raises(GitHubRateLimitError):
            limiter.calculate_delay("core")


def test_rate_limiter_mandatory_pause_enforcement() -> None:
    """Verify acquire institutes a mandatory pause using the calculated delay."""
    limiter = GitHubRateLimiter()
    now = time.time()

    # User scenario: 98 out of 100 tokens used (remaining = 2), 30s until reset
    limiter.update_quota("graphql", remaining=2, limit=100, reset_epoch=now + 30.0)

    with patch("time.sleep") as mock_sleep:
        delay = limiter.acquire("graphql")
        assert 14.0 <= delay <= 15.5  # ~15.0s
        mock_sleep.assert_called_once()
        actual_slept = mock_sleep.call_args[0][0]
        assert actual_slept == pytest.approx(15.0, abs=0.5)


def test_rate_limiter_mandatory_pause_when_quota_exhausted() -> None:
    """Verify acquire pauses for the full duration until reset when remaining <= 0."""
    limiter = GitHubRateLimiter()
    now = time.time()

    # 0 tokens remaining with 20s until reset
    limiter.update_quota("core", remaining=0, limit=5000, reset_epoch=now + 20.0)

    with patch("time.sleep") as mock_sleep:
        delay = limiter.acquire("core")
        assert 19.0 <= delay <= 20.0
        mock_sleep.assert_called_once()
        actual_slept = mock_sleep.call_args[0][0]
        assert actual_slept == pytest.approx(20.0, abs=0.5)


def test_rate_limiter_acquire_mandatory_pacing(tmp_path: Path) -> None:
    """Verify acquire always applies calculated pacing delay with zero threshold bypass."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()
    limiter.update_quota("core", remaining=3600, limit=5000, reset_epoch=now + 3600.0)
    with patch("time.sleep") as mock_sleep:
        delay = limiter.acquire("core")
        assert delay == pytest.approx(1.0, abs=0.1)
        mock_sleep.assert_called_once()
        actual_slept = mock_sleep.call_args[0][0]
        assert actual_slept == pytest.approx(1.0, abs=0.1)


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


def test_run_gh_rate_limit_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify run_gh retries with backoff on secondary rate limits."""
    limiter = get_github_rate_limiter()
    limiter.clear_cache()
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


def test_run_gh_rate_limit_endpoint_extracts_all_resources() -> None:
    """Verify /rate_limit endpoint response updates all resources directly without acquire sleep."""
    limiter = get_github_rate_limiter()
    output = (
        '{"resources": {'
        '"core": {"limit": 5000, "remaining": 4999, "reset": 1773551000},'
        '"graphql": {"limit": 5000, "remaining": 4500, "reset": 1773552000},'
        '"search": {"limit": 30, "remaining": 28, "reset": 1773550060}'
        "}}"
    )

    with (
        patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub,
        patch("time.sleep") as mock_sleep,
    ):
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "rate_limit"],
            returncode=0,
            stdout=output,
            stderr="",
        )
        res = run_gh(["api", "rate_limit"])
        assert res.returncode == 0
        # rate_limit inspection must not trigger pacing sleep
        mock_sleep.assert_not_called()

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


def test_run_gh_paginated_edge_cases(tmp_path: Path) -> None:
    """Verify pagination handler covers unpaginated fallback, empty list, and non-list responses."""
    # No endpoint in args
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "--paginate"], returncode=0, stdout="[]", stderr=""
        )
        res = run_gh(["api", "--paginate"])
        assert res.returncode == 0

    # Empty list terminates loop immediately
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "repos/owner/repo/pulls", "--paginate"],
            returncode=0,
            stdout="[]",
            stderr="",
        )
        res = run_gh(["api", "repos/owner/repo/pulls", "--paginate"])
        assert res.returncode == 0
        assert res.stdout == "[]"

    # Non-list response terminates loop and returns proc
    with patch("devops_cli.github.rate_limiter.run_subprocess") as mock_sub:
        mock_sub.return_value = subprocess.CompletedProcess(
            args=["gh", "api", "repos/owner/repo/pulls", "--paginate"],
            returncode=0,
            stdout='{"message": "Not found"}',
            stderr="",
        )
        res = run_gh(["api", "repos/owner/repo/pulls", "--paginate"])
        assert res.returncode == 0
        assert res.stdout == '{"message": "Not found"}'


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

    with patch("time.sleep"):
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
    assert "nonexistent_subcmd" not in limiter.get_all_quotas()


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


def test_rate_limiter_acquire_propagates_unresolvable_quota_error(tmp_path: Path) -> None:
    """Verify acquire propagates GitHubRateLimitError when quota state cannot be resolved."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=cache_file, min_interval=0.05)

    with (
        patch.object(
            limiter,
            "_resolve_quota_state",
            side_effect=GitHubRateLimitError("offline"),
        ),
        patch("time.sleep") as mock_sleep,
    ):
        with pytest.raises(GitHubRateLimitError, match="offline"):
            limiter.acquire("core")
        mock_sleep.assert_not_called()


def test_build_paginated_url_and_extraction() -> None:
    """Verify _build_paginated_url and _extract_page_per_page handle query params cleanly."""
    from urllib.parse import parse_qs, urlsplit

    from devops_cli.github.rate_limiter import (
        _build_paginated_url,
        _extract_page_per_page,
    )

    url_with_per_page = "repos/owner/repo/issues?state=all&per_page=100"
    url_p2 = _build_paginated_url(url_with_per_page, 2)
    qs_p2 = parse_qs(urlsplit(url_p2).query)

    url_plain = "repos/owner/repo/issues"
    url_plain_p3 = _build_paginated_url(url_plain, 3)
    qs_plain = parse_qs(urlsplit(url_plain_p3).query)

    url_existing_page = "repos/owner/repo/pulls?page=1&per_page=50"
    url_existing_p4 = _build_paginated_url(url_existing_page, 4)
    qs_existing = parse_qs(urlsplit(url_existing_p4).query)

    assert (
        _extract_page_per_page(url_with_per_page),
        _extract_page_per_page(url_plain),
        _extract_page_per_page("repos/owner/repo?per_page=25"),
        qs_p2.get("page"),
        qs_p2.get("state"),
        qs_p2.get("per_page"),
        qs_plain.get("page"),
        qs_existing.get("page"),
        qs_existing.get("per_page"),
    ) == (
        100,
        100,
        25,
        ["2"],
        ["all"],
        ["100"],
        ["3"],
        ["4"],
        ["50"],
    )


def test_run_gh_paginated_multipage_success(tmp_path: Path) -> None:
    """Verify _run_gh_paginated iterates across multiple pages and terminates correctly."""
    page_calls: list[list[str]] = []

    def mock_subprocess_runner(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        page_calls.append(cmd)
        from urllib.parse import parse_qs, urlsplit

        target_arg = next((arg for arg in cmd if "repos/owner/repo/issues" in arg), "")
        page_val = parse_qs(urlsplit(target_arg).query).get("page")
        if page_val == ["2"]:
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout='[{"id": 3}]', stderr=""
            )
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout='[{"id": 1}, {"id": 2}]', stderr=""
        )

    with (
        patch(
            "devops_cli.github.rate_limiter._extract_page_per_page",
            return_value=2,
        ),
        patch(
            "devops_cli.github.rate_limiter.run_subprocess",
            side_effect=mock_subprocess_runner,
        ),
        patch.object(get_github_rate_limiter(), "acquire", return_value=0.0),
    ):
        res = run_gh(["api", "--paginate", "repos/owner/repo/issues?per_page=2"])
        assert (res.returncode, res.stdout, len(page_calls)) == (
            0,
            '[{"id": 1}, {"id": 2}, {"id": 3}]',
            2,
        )


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


def test_rate_limiter_prune_expired_cache_ephemeral_and_disk(tmp_path: Path) -> None:
    """Verify prune_expired_cache purges expired entries from both memory and disk."""
    quota_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=quota_file)
    limiter.set_cached("valid_key", "valid_data", ttl=3600.0)
    limiter.set_cached("expired_key", "expired_data", ttl=0.01)
    time.sleep(0.05)

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
