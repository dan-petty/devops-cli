"""GitHub Milestones extraction from roadmap, synchronization, and progress metrics."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.store import GitHubState, Release, RoadmapStore, find_release

logger = logging.getLogger(__name__)


class MilestoneSpec(BaseModel):
    """Specification for a release milestone."""

    title: str
    description: str = ""
    state: GitHubState = GitHubState.OPEN
    due_on: date | None = None


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
    updated_count: int = 0
    existing_count: int = 0
    dry_run: bool = False
    created: list[str] = Field(default_factory=list)
    updated: list[str] = Field(default_factory=list)


_ROADMAP_HEADING_PATTERN = re.compile(
    r"^###\s+(.+?)\s+\((v\d+\.\d+\.\d+)(?:\s*-\s*([^)]+))?\)",
    re.MULTILINE,
)


def _is_safe_roadmap_path(roadmap_path: Path) -> bool:
    """Predicate determining if roadmap path is free from directory traversal patterns."""
    from devops_cli.core.paths import is_forbidden_system_path, validate_no_path_traversal

    try:
        validate_no_path_traversal(roadmap_path, label="Roadmap path")
        resolved = roadmap_path.resolve()
        if is_forbidden_system_path(resolved):
            return False
        if roadmap_path.is_symlink():
            return False
        return True
    except Exception as exc:
        logger.debug("Roadmap path %s not safe: %s", roadmap_path, exc)
        return False


def _validate_roadmap_path(roadmap_path: Path) -> Path:
    """Validate roadmap path containment and file presence."""
    if not _is_safe_roadmap_path(roadmap_path):
        raise GitHubOperationError(
            f"Path traversal detected in roadmap path: {roadmap_path}",
            operation="extract_roadmap_milestones",
            details={"path": str(roadmap_path)},
        )
    if not roadmap_path.is_file():
        raise GitHubOperationError(
            f"Roadmap file not found: {roadmap_path}",
            operation="extract_roadmap_milestones",
            details={"path": str(roadmap_path)},
        )
    return roadmap_path


def extract_roadmap_milestones(
    roadmap_path: Path = Path("docs/ROADMAP.md"),
) -> list[MilestoneSpec]:
    """Parse markdown headings from ROADMAP.md into MilestoneSpec objects."""
    valid_path = _validate_roadmap_path(roadmap_path)
    if valid_path.stat().st_size > DEFAULT_MAX_AST_FILE_SIZE_BYTES:
        raise GitHubOperationError(
            f"Roadmap file exceeds size limit: {valid_path}",
            operation="extract_roadmap_milestones",
            details={"path": str(valid_path)},
        )
    content = valid_path.read_text(encoding="utf-8")

    specs: list[MilestoneSpec] = []
    for match in _ROADMAP_HEADING_PATTERN.finditer(content):
        name = match.group(1).strip()
        version = match.group(2).strip()
        status = (match.group(3) or "").strip()

        state = GitHubState.CLOSED if status.lower() == "completed" else GitHubState.OPEN
        description = name

        specs.append(
            MilestoneSpec(
                title=version,
                description=description,
                state=state,
            )
        )

    return specs


def diff_milestones(
    desired: list[MilestoneSpec], existing: Sequence[Release]
) -> tuple[list[MilestoneSpec], list[Release]]:
    """Partition desired milestones into new Releases and the existing Releases they match."""
    matches = [(spec, find_release(existing, spec.title)) for spec in desired]
    to_create = [spec for spec, found in matches if found is None]
    existing_matches = [found for _, found in matches if found is not None]
    return to_create, existing_matches


def _is_milestone_update_needed(current: Release, spec: MilestoneSpec) -> bool:
    """Determine if an existing Release requires a description or state change."""
    spec_desc = spec.description.strip()
    if spec_desc and current.description.strip() != spec_desc:
        return True
    return current.state is not spec.state


def find_milestones_to_update(
    desired: list[MilestoneSpec], existing: Sequence[Release]
) -> list[tuple[Release, MilestoneSpec]]:
    """Identify existing Releases whose description or state differs from the desired spec."""
    matches = ((find_release(existing, spec.title), spec) for spec in desired)
    return [
        (found, spec)
        for found, spec in matches
        if found is not None and _is_milestone_update_needed(found, spec)
    ]


def sync_repository_milestones(
    store: RoadmapStore, desired: list[MilestoneSpec], dry_run: bool = False
) -> MilestoneSyncResult:
    """Reconcile the repository's Releases with desired specs, matching them by version."""
    existing = store.releases()
    to_create, existing_matches = diff_milestones(desired, existing)
    to_update = find_milestones_to_update(desired, existing)

    result = MilestoneSyncResult(
        created_count=len(to_create),
        updated_count=len(to_update),
        existing_count=len(existing_matches),
        dry_run=dry_run,
        created=[spec.title for spec in to_create],
        updated=[spec.title for _, spec in to_update],
    )
    if dry_run:
        return result

    for spec in to_create:
        store.create_release(
            spec.title, description=spec.description, due_on=spec.due_on, state=spec.state
        )
    for release, spec in to_update:
        store.edit_release(release.title, description=spec.description or None, state=spec.state)
    return result


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
