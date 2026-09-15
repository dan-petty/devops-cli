"""Unit tests for GitHub rate limiter and request pacing subsystem.

Verifies the simple delay formula:
    request delay = time in seconds until next quota reset for this subcommand / remaining requests
and mandatory pause enforcement.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Generator
from pathlib import Path
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
    # 1000 tokens remaining, 3000s left -> 3.0s delay (without threshold)
    assert calculate_request_delay(time_until_reset=3000.0, remaining=1000) == 3.0

    # 5000 tokens remaining, 3600s left -> 0.72s delay (without threshold)
    assert calculate_request_delay(time_until_reset=3600.0, remaining=5000) == pytest.approx(0.72)

    # Reset already reached (time_left == 0) -> 0.0s delay
    assert calculate_request_delay(time_until_reset=0.0, remaining=10) == 0.0
    # Negative time_until_reset must raise ValueError
    with pytest.raises(ValueError, match="time_until_reset must be non-negative"):
        calculate_request_delay(time_until_reset=-10.0, remaining=10)
    assert calculate_request_delay(time_until_reset=0.0, remaining=0) == 0.0


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


def test_calculate_request_delay_percent_used_threshold() -> None:
    """Verify that requests under the no-delay percent used threshold have delay == 0.0."""
    # 500 out of 5000 tokens used (10% used) with 25% threshold -> 0.0s delay
    delay = calculate_request_delay(
        time_until_reset=3600.0, remaining=4500, limit=5000, no_delay_percent_used_threshold=25.0
    )
    assert delay == 0.0

    # 1500 out of 5000 tokens used (30% used) with 25% threshold -> pacing delay applied
    delay = calculate_request_delay(
        time_until_reset=3500.0, remaining=3500, limit=5000, no_delay_percent_used_threshold=25.0
    )
    assert delay == 1.0  # 3500s / 3500 tokens = 1.0s

    # Negative threshold raises ValueError
    with pytest.raises(ValueError, match="no_delay_percent_used_threshold must be non-negative"):
        calculate_request_delay(
            time_until_reset=100.0, remaining=50, limit=100, no_delay_percent_used_threshold=-1.0
        )
    # Negative limit raises ValueError
    with pytest.raises(ValueError, match="rate limit must be non-negative"):
        calculate_request_delay(time_until_reset=100.0, remaining=50, limit=-10)


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
    assert state.remaining is None
    assert state.limit is None
    assert state.reset_epoch == 0.0

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


def test_rate_limiter_acquire_no_pause_when_delay_zero(tmp_path: Path) -> None:
    """Verify acquire does not pause when delay is 0.0."""
    cache_file = tmp_path / "gh_quota.json"
    limiter = GitHubRateLimiter(persist_path=cache_file)
    now = time.time()
    limiter.update_quota("core", remaining=5000, limit=5000, reset_epoch=now + 3600.0)
    with patch("time.sleep") as mock_sleep:
        delay = limiter.acquire("core")
        assert delay == 0.0
        mock_sleep.assert_not_called()


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
        assert res.returncode == 0
        quota = limiter.get_quota("graphql")
        assert quota.remaining == 3200
        assert quota.limit == 5000
        assert quota.reset_epoch > 0


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

    assert _parse_reset_epoch(None) == 0.0
    assert _parse_reset_epoch("") == 0.0
    assert _parse_reset_epoch("invalid-date-string") == 0.0
    assert _parse_reset_epoch("2026-09-15T12:00:00Z") > 0.0


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


def test_rate_limiter_constructor_negative_threshold() -> None:
    """Verify constructor raises ValueError on negative threshold."""
    with pytest.raises(ValueError, match="no_delay_percent_used_threshold must be non-negative"):
        GitHubRateLimiter(no_delay_percent_used_threshold=-1.0)


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
