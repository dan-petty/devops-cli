"""Minimal type stubs for botocore.config."""

from collections.abc import Mapping
from typing import Any

class Config:
    region_name: str | None
    signature_version: str | None
    s3: Mapping[str, Any] | None
    def __init__(
        self,
        region_name: str | None = None,
        signature_version: str | None = None,
        s3: Mapping[str, Any] | None = None,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        retries: Mapping[str, Any] | None = None,
    ) -> None: ...
