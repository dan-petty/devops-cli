"""Lifecycle states and transition invariants for review findings (#871)."""

from __future__ import annotations

from collections.abc import Iterable
from enum import StrEnum
from typing import Any

from devops_cli.config.constants import CONST_EXIT_FAILURE
from devops_cli.exceptions.base import DevOpsCLIError


class ReviewStateError(DevOpsCLIError, ValueError):
    """Exception raised for invalid review finding state or state transition."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(
            message,
            exit_code=CONST_EXIT_FAILURE,
            error_code="REVIEW_STATE_ERROR",
            **kwargs,
        )


class FindingState(StrEnum):
    """Lifecycle states for an admitted review finding."""

    OPEN = "OPEN"
    SUPPRESSED = "SUPPRESSED"
    FIXED = "FIXED"
    CONFIRMED = "CONFIRMED"


_VALID_TRANSITIONS: dict[FindingState, frozenset[FindingState]] = {
    FindingState.OPEN: frozenset(
        {FindingState.SUPPRESSED, FindingState.FIXED, FindingState.CONFIRMED}
    ),
    FindingState.SUPPRESSED: frozenset(
        {FindingState.OPEN, FindingState.FIXED, FindingState.CONFIRMED}
    ),
    FindingState.FIXED: frozenset({FindingState.OPEN}),
    FindingState.CONFIRMED: frozenset({FindingState.FIXED}),
}


def can_transition(source: FindingState, target: FindingState) -> bool:
    """Return whether a state transition is structurally permitted."""
    if source == target:
        return True
    return target in _VALID_TRANSITIONS.get(source, frozenset())


def _resolve_finding_state(state_val: Any) -> FindingState:
    """Resolve raw state attribute to canonical FindingState."""
    if isinstance(state_val, FindingState):
        return state_val
    if isinstance(state_val, str):
        try:
            return FindingState(state_val.upper().strip())
        except ValueError as err:
            raise ReviewStateError(f"Invalid finding state '{state_val}'") from err
    raise ReviewStateError(f"Finding has missing or invalid state: {state_val}")


def _validate_finding_state_fields(state: FindingState, f: Any) -> None:
    """Validate attribute combinations for a given finding lifecycle state."""
    suppression_reason = getattr(f, "suppression_reason", None)
    suppressed_by_change = getattr(f, "suppressed_by_change", False)
    confirmed_by = getattr(f, "confirmed_by", None)

    if state == FindingState.SUPPRESSED:
        if not suppression_reason and not getattr(f, "inline_marker", None):
            raise ReviewStateError(
                "SUPPRESSED finding must record a suppression reason or inline marker"
            )
    elif state == FindingState.CONFIRMED:
        if not confirmed_by or not str(confirmed_by).strip():
            raise ReviewStateError("CONFIRMED finding must record who confirmed it")
    elif state == FindingState.OPEN:
        if confirmed_by:
            raise ReviewStateError("OPEN finding cannot record confirmed_by")
        if suppression_reason and not suppressed_by_change:
            raise ReviewStateError(
                "OPEN finding cannot record active suppression reason without suppressed_by_change"
            )


def assert_finding_state_invariants(findings: Iterable[Any]) -> None:
    """Assert lifecycle state invariants across admitted findings.

    Invariants:
    1. A SUPPRESSED finding must record an unexpired reason or an inline suppression marker.
    2. A CONFIRMED finding must record who confirmed it (person or replayed observation).
    3. An OPEN finding carries neither suppression reason nor confirmed_by.
    4. State must be one of the canonical FindingState values.
    """
    for f in findings:
        state = _resolve_finding_state(getattr(f, "state", None))
        _validate_finding_state_fields(state, f)
