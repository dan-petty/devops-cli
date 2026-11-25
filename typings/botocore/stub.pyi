"""Minimal type stubs for botocore.stub."""

from types import TracebackType
from typing import Any

ANY: Any

class Stubber:
    def __init__(self, client: Any) -> None: ...
    def __enter__(self) -> Stubber: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...
    def activate(self) -> None: ...
    def deactivate(self) -> None: ...
    def assert_no_pending_responses(self) -> None: ...
    def add_response(
        self,
        method: str,
        service_response: dict[str, Any],
        expected_params: dict[str, Any] | None = None,
    ) -> None: ...
    def add_client_error(
        self,
        method: str,
        service_error_code: str = ...,
        service_message: str = ...,
        http_status_code: int = ...,
        service_error_meta: dict[str, Any] | None = None,
        response_meta: dict[str, Any] | None = None,
        expected_params: dict[str, Any] | None = None,
    ) -> None: ...
