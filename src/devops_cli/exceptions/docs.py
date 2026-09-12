"""Documentation subsystem exceptions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_DOC_COMPACTION,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


def _bound_detail_value(val: Any, max_len: int = 256) -> Any:
    """Recursively bound string lengths in nested dictionaries, lists, and primitives."""
    if isinstance(val, str):
        return val[:max_len]
    if isinstance(val, dict):
        return {
            (str(k)[:max_len] if isinstance(k, str) else str(k)): _bound_detail_value(v, max_len)
            for k, v in val.items()
        }
    if isinstance(val, list):
        return [_bound_detail_value(item, max_len) for item in val]
    if isinstance(val, tuple):
        return tuple(_bound_detail_value(item, max_len) for item in val)
    return val


class DocCompactionError(DevOpsCLIError):
    """Exception raised when documentation compaction fails."""

    def __init__(
        self,
        message: str,
        *,
        series: str | None = None,
        target_file: str | None = None,
        exit_code: int = CONST_EXIT_FAILURE,
        error_code: str = CONST_ERROR_CODE_DOC_COMPACTION,
        details: dict[str, Any] | None = None,
    ) -> None:
        err_details: dict[str, Any] = {}
        if series:
            err_details["series"] = _bound_detail_value(series)
        if target_file:
            err_details["target_file"] = _bound_detail_value(target_file)
        if details:
            for key, val in details.items():
                bound_key = str(key)[:256]
                err_details[bound_key] = _bound_detail_value(val)
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)
