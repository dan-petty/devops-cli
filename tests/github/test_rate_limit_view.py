"""Tests for GitHub rate limit view and parsing helpers."""

from __future__ import annotations

import time

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limit_view import (
    format_rate_limit_rows,
    format_reset_time,
    parse_rate_limit_payload,
)


def test_format_reset_time_ready() -> None:
    past = time.time() - 10
    result = format_reset_time(past)
    assert "(ready)" in result


def test_format_reset_time_future() -> None:
    future = time.time() + 125
    result = format_reset_time(future)
    assert "in 2m" in result


def test_parse_rate_limit_payload_valid() -> None:
    raw = '{"resources": {"core": {"limit": 5000, "used": 10, "remaining": 4990, "reset": 1234567890}}}'
    data = parse_rate_limit_payload(raw)
    assert "resources" in data
    assert "core" in data["resources"]


def test_parse_rate_limit_payload_invalid_json() -> None:
    with pytest.raises(GitHubOperationError, match="Failed to parse rate limit response"):
        parse_rate_limit_payload("invalid json")


def test_parse_rate_limit_payload_not_dict() -> None:
    with pytest.raises(GitHubOperationError, match="expected JSON object"):
        parse_rate_limit_payload("[]")


def test_parse_rate_limit_payload_missing_resources() -> None:
    with pytest.raises(GitHubOperationError, match="missing 'resources' object"):
        parse_rate_limit_payload('{"other": 1}')


def test_format_rate_limit_rows() -> None:
    resources = {
        "core": {"limit": 5000, "used": 10, "remaining": 4990, "reset": time.time() + 60},
        "search": {"limit": 30, "used": 2, "remaining": 28, "reset": None},
    }
    rows = format_rate_limit_rows(resources)
    assert len(rows) == 2
    assert rows[0][0] == "core"
    assert rows[0][1] == "5000"
    assert rows[1][0] == "search"
    assert rows[1][4] == "-"
