"""Minimal type stubs for botocore.exceptions."""

from typing import Any

class BotoCoreError(Exception): ...

class ClientError(BotoCoreError):
    response: dict[str, Any]
    def __init__(self, error_response: dict[str, Any], operation_name: str) -> None: ...

class EndpointConnectionError(BotoCoreError):
    def __init__(self, *, endpoint_url: str, **kwargs: Any) -> None: ...

class ConnectTimeoutError(BotoCoreError):
    def __init__(self, *, endpoint_url: str, **kwargs: Any) -> None: ...

class ReadTimeoutError(BotoCoreError):
    def __init__(self, *, endpoint_url: str, **kwargs: Any) -> None: ...
