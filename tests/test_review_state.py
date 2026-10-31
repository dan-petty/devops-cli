"""Tests for finding lifecycle states and SavedFinding state fields (#2414)."""

from devops_cli.ai.review_schema import SavedFinding
from devops_cli.review.state import (
    FindingState,
    can_transition,
)


def test_can_transition_confirmed_to_open() -> None:
    """Transition from CONFIRMED to OPEN is permitted for overturning human verdicts."""
    assert can_transition(FindingState.CONFIRMED, FindingState.OPEN) is True


def test_saved_finding_has_state_and_confirmed_by() -> None:
    """SavedFinding defaults to OPEN state with no confirmed_by adjudicator."""
    sf = SavedFinding(location="src/app.py:10", title="Test finding")
    assert sf.state == FindingState.OPEN
    assert sf.confirmed_by is None

    # Model validation accepts explicit state and confirmed_by
    sf_confirmed = SavedFinding(
        location="src/app.py:10",
        title="Test finding",
        state=FindingState.CONFIRMED,
        confirmed_by="human",
    )
    assert sf_confirmed.state == FindingState.CONFIRMED
    assert sf_confirmed.confirmed_by == "human"

    # String values coerce to canonical FindingState
    sf_coerced = SavedFinding(
        location="src/app.py:10",
        title="Test finding",
        state="CONFIRMED",
        confirmed_by="human",
    )
    assert sf_coerced.state == FindingState.CONFIRMED
