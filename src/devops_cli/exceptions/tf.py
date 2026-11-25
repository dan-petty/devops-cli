"""Errors of `devops tf` agent access and GitHub rate-budget guards (#5320)."""

from __future__ import annotations

from devops_cli.exceptions.base import DevOpsCLIError


class TFError(DevOpsCLIError):
    """Base exception for OpenTofu wrapper guard failures."""

    error_code = "TF_ERROR"


class TFAccessRefusedError(TFError):
    """An agent attempted apply, destroy, or state mutation without explicit `apply` access."""

    error_code = "TF_ACCESS_REFUSED"

    def __init__(self, message: str, *, key: str) -> None:
        super().__init__(message, details={"key": key})


class TFBudgetError(TFError):
    """Remaining GitHub REST core quota is below the pre-plan safety floor."""

    error_code = "TF_BUDGET_BELOW_FLOOR"

    def __init__(self, message: str, *, remaining: int, floor: int) -> None:
        super().__init__(message, details={"remaining": remaining, "floor": floor})


__all__ = [
    "TFAccessRefusedError",
    "TFBudgetError",
    "TFError",
]
