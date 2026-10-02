"""Release (milestone) progress metrics."""

from __future__ import annotations

from pydantic import BaseModel

from devops_cli.roadmap.store import GitHubState, Release


class MilestoneProgress(BaseModel):
    """Progress, health, and issue completion metrics for a milestone."""

    title: str
    open_issues: int = 0
    closed_issues: int = 0
    total_issues: int = 0
    percent_complete: float = 0.0
    is_complete: bool = False
    state: str = "open"
    due_on: str | None = None


def calculate_milestone_progress(release: Release) -> MilestoneProgress:
    """Compute a Release's completion percentage and progress metrics."""
    total = release.open_issues + release.closed_issues
    closed = release.state is GitHubState.CLOSED

    if total > 0:
        percent = round((release.closed_issues / total) * 100.0, 2)
    elif closed:
        percent = 100.0
    else:
        percent = 0.0

    return MilestoneProgress(
        title=release.title,
        open_issues=release.open_issues,
        closed_issues=release.closed_issues,
        total_issues=total,
        percent_complete=percent,
        is_complete=percent >= 100.0 or closed,
        state=release.state.value,
        due_on=release.due_on.isoformat() if release.due_on else None,
    )
