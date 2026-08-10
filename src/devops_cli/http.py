"""Shared HTTP client timeout settings."""

from __future__ import annotations

import httpx2

from devops_cli.defaults import (
    HTTP_CONNECT_TIMEOUT_SECONDS,
    HTTP_POOL_TIMEOUT_SECONDS,
    HTTP_READ_TIMEOUT_SECONDS,
    HTTP_WRITE_TIMEOUT_SECONDS,
)


def request_timeout(*, read: float | None = None) -> httpx2.Timeout:
    """Build a timeout object with a strict 1-second connection timeout."""
    return httpx2.Timeout(
        connect=HTTP_CONNECT_TIMEOUT_SECONDS,
        read=HTTP_READ_TIMEOUT_SECONDS if read is None else read,
        write=HTTP_WRITE_TIMEOUT_SECONDS,
        pool=HTTP_POOL_TIMEOUT_SECONDS,
    )
