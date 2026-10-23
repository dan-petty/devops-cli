"""Milestone progress metrics: a milestone is a planning bucket, ordered by its due date."""

from __future__ import annotations

from pydantic import BaseModel

from devops_cli.roadmap.store import GitHubState, Milestone


class MilestoneProgress(BaseModel):
    """Progress, health, and issue completion metrics for a milestone."""

    number: int
    title: str
    open_issues: int = 0
    closed_issues: int = 0
    total_issues: int = 0
    percent_complete: float = 0.0
    is_complete: bool = False
    state: str = "open"
    due_on: str | None = None


def calculate_milestone_progress(milestone: Milestone) -> MilestoneProgress:
    """Compute a milestone's completion percentage and progress metrics."""
    total = milestone.open_issues + milestone.closed_issues
    closed = milestone.state is GitHubState.CLOSED

    if total > 0:
        percent = round((milestone.closed_issues / total) * 100.0, 2)
    elif closed:
        percent = 100.0
    else:
        percent = 0.0

    return MilestoneProgress(
        number=milestone.number,
        title=milestone.title,
        open_issues=milestone.open_issues,
        closed_issues=milestone.closed_issues,
        total_issues=total,
        percent_complete=percent,
        is_complete=percent >= 100.0 or closed,
        state=milestone.state.value,
        due_on=milestone.due_on.isoformat() if milestone.due_on else None,
    )
