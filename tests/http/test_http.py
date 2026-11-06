"""Tests for shared HTTP utilities and client configurations."""

from __future__ import annotations

import pytest

from devops_cli.http.client import request_timeout
from devops_cli.http.egress import EgressLevel
from devops_cli.http.entry import async_http_client, http_client


def test_http_client_options() -> None:
    """Test request_timeout and http_client with varied timeout specifications."""
    t1 = request_timeout(read=30.0)
    assert t1.read == 30.0

    from devops_cli.config.defaults import DEFAULT_CONNECT_TIMEOUT_SECONDS

    c1 = http_client(EgressLevel.PUBLIC, read_timeout=15.0)
    assert c1.timeout.read == 15.0
    assert c1.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS

    c2 = http_client(EgressLevel.PUBLIC, timeout=10.0)
    assert c2.timeout.read == 10.0
    assert c2.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS

    c3 = http_client(EgressLevel.PUBLIC, timeout=t1)
    assert c3.timeout.read == 30.0
    assert c3.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS

    ac1 = async_http_client(EgressLevel.PUBLIC, timeout=12.0)
    assert ac1.timeout.read == 12.0
    assert ac1.timeout.connect == DEFAULT_CONNECT_TIMEOUT_SECONDS


def test_http_client_invalid_timeout_type() -> None:
    """Verify HTTPTimeoutTypeError (and TypeError/ValidationError) is raised when unsupported timeout types are passed."""
    from devops_cli.exceptions.validation import ValidationError
    from devops_cli.http.client import HTTPTimeoutTypeError

    with pytest.raises(HTTPTimeoutTypeError, match="timeout must be") as exc_info1:
        http_client(EgressLevel.PUBLIC, timeout="invalid-string")  # type: ignore[arg-type]
    assert "timeout must be" in str(exc_info1.value)
    assert isinstance(exc_info1.value, TypeError)
    assert isinstance(exc_info1.value, ValidationError)

    with pytest.raises(HTTPTimeoutTypeError, match="read_timeout must be") as exc_info2:
        http_client(EgressLevel.PUBLIC, read_timeout="invalid-string")  # type: ignore[arg-type]
    assert "read_timeout must be" in str(exc_info2.value)
    assert isinstance(exc_info2.value, TypeError)
    assert isinstance(exc_info2.value, ValidationError)
