"""GitHub Milestones extraction from roadmap, synchronization, and progress metrics."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.exceptions.git import GitHubOperationError


class MilestoneSpec(BaseModel):
    """Specification for a release milestone."""

    title: str
    description: str = ""
    state: str = "open"
    due_on: str | None = None


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


class MilestoneSyncResult(BaseModel):
    """Summary of a milestone synchronization operation."""

    created_count: int = 0
    existing_count: int = 0
    dry_run: bool = False
    created: list[str] = Field(default_factory=list)


def extract_roadmap_milestones(
    roadmap_path: Path = Path("docs/ROADMAP.md"),
) -> list[MilestoneSpec]:
    """Parse markdown headings from ROADMAP.md into MilestoneSpec objects."""
    if not roadmap_path.is_file():
        raise GitHubOperationError(
            f"Roadmap file not found: {roadmap_path}",
            operation="extract_roadmap_milestones",
            details={"path": str(roadmap_path)},
        )

    content = roadmap_path.read_text(encoding="utf-8")
    # Matches: ### Core Foundation (v0.0.1 - Completed) or ### Valkey (v0.2.12 - Scheduled)
    pattern = re.compile(
        r"^###\s+(.+?)\s+\((v\d+\.\d+\.\d+)(?:\s*-\s*([^)]+))?\)",
        re.MULTILINE,
    )

    specs: list[MilestoneSpec] = []
    for match in pattern.finditer(content):
        name = match.group(1).strip()
        version = match.group(2).strip()
        status = (match.group(3) or "").strip()

        state = "closed" if status.lower() == "completed" else "open"
        description = f"{name} ({status})" if status else name

        specs.append(
            MilestoneSpec(
                title=version,
                description=description,
                state=state,
            )
        )

    return specs


def diff_milestones(
    desired: list[MilestoneSpec], existing: list[dict[str, Any]]
) -> tuple[list[MilestoneSpec], list[dict[str, Any]]]:
    """Partition desired milestones into new creations and existing matches."""
    existing_map: dict[str, dict[str, Any]] = {
        item.get("title", ""): item for item in existing if isinstance(item, dict)
    }

    to_create: list[MilestoneSpec] = [spec for spec in desired if spec.title not in existing_map]
    existing_matches: list[dict[str, Any]] = [
        existing_map[spec.title] for spec in desired if spec.title in existing_map
    ]

    return to_create, existing_matches


def _extract_milestones_from_raw(raw_milestones: Any) -> list[dict[str, Any]]:
    """Extract standard milestone dictionaries from heterogeneous client objects."""
    results: list[dict[str, Any]] = []
    for item in raw_milestones or []:
        if isinstance(item, dict):
            results.append(item)
        elif hasattr(item, "title"):
            due = getattr(item, "due_on", None)
            due_str = (
                due.isoformat()
                if due and hasattr(due, "isoformat")
                else (str(due) if due else None)
            )
            results.append(
                {
                    "title": item.title,
                    "state": getattr(item, "state", "open"),
                    "description": getattr(item, "description", "") or "",
                    "open_issues": getattr(item, "open_issues", 0),
                    "closed_issues": getattr(item, "closed_issues", 0),
                    "due_on": due_str,
                }
            )
    return results


def _apply_milestone_creation(client: Any, repo: str, spec: MilestoneSpec) -> None:
    """Safely apply create milestone mutation on client."""
    func = getattr(client, "create_milestone", None)
    if not callable(func):
        return

    kwargs: dict[str, Any] = {
        "title": spec.title,
        "description": spec.description,
        "state": spec.state,
    }
    if spec.due_on:
        kwargs["due_on"] = spec.due_on

    try:
        func(repo, **kwargs)
    except TypeError:
        func(**kwargs)


def sync_repository_milestones(
    client: Any, repo: str, desired: list[MilestoneSpec], dry_run: bool = False
) -> MilestoneSyncResult:
    """Reconcile remote repository milestones with desired specs."""
    try:
        raw_existing = client.get_milestones(repo)
    except TypeError:
        raw_existing = client.get_milestones()

    existing = _extract_milestones_from_raw(raw_existing)
    to_create, existing_matches = diff_milestones(desired, existing)

    result = MilestoneSyncResult(
        created_count=len(to_create),
        existing_count=len(existing_matches),
        dry_run=dry_run,
        created=[s.title for s in to_create],
    )

    if dry_run:
        return result

    for spec in to_create:
        _apply_milestone_creation(client, repo, spec)

    return result


def calculate_milestone_progress(milestone_data: dict[str, Any]) -> MilestoneProgress:
    """Compute completion percentage and progress metrics from milestone data."""
    open_cnt = int(milestone_data.get("open_issues", 0) or 0)
    closed_cnt = int(milestone_data.get("closed_issues", 0) or 0)
    total = open_cnt + closed_cnt
    state = str(milestone_data.get("state", "open")).lower()

    if total > 0:
        percent = round((closed_cnt / total) * 100.0, 2)
    elif state == "closed":
        percent = 100.0
    else:
        percent = 0.0

    is_complete = percent >= 100.0 or state == "closed"

    return MilestoneProgress(
        title=str(milestone_data.get("title", "")),
        open_issues=open_cnt,
        closed_issues=closed_cnt,
        total_issues=total,
        percent_complete=percent,
        is_complete=is_complete,
        state=state,
        due_on=milestone_data.get("due_on"),
    )
