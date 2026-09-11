"""Documentation subsystem exceptions for devops-cli."""

from __future__ import annotations

from typing import Any

from devops_cli.config.constants import (
    CONST_ERROR_CODE_DOC_COMPACTION,
    CONST_EXIT_FAILURE,
)
from devops_cli.exceptions.base import DevOpsCLIError


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
            err_details["series"] = series[:256] if isinstance(series, str) else series
        if target_file:
            err_details["target_file"] = (
                target_file[:256] if isinstance(target_file, str) else target_file
            )
        if details:
            for key, val in details.items():
                err_details[key] = val[:256] if isinstance(val, str) else val
        super().__init__(message, exit_code=exit_code, error_code=error_code, details=err_details)
