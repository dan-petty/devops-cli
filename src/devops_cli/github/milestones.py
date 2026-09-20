"""GitHub Milestones extraction from roadmap, synchronization, and progress metrics."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.defaults import DEFAULT_MAX_AST_FILE_SIZE_BYTES
from devops_cli.exceptions.git import GitHubOperationError

logger = logging.getLogger(__name__)


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

        state = "closed" if status.lower() == "completed" else "open"
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
                    "number": getattr(item, "number", None),
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


def _is_milestone_update_needed(curr: dict[str, Any], spec: MilestoneSpec) -> bool:
    """Determine if an existing milestone requires description or state mutation."""
    curr_desc = str(curr.get("description") or "").strip()
    spec_desc = str(spec.description or "").strip()
    curr_state = str(curr.get("state") or "open").lower()
    spec_state = str(spec.state or "open").lower()
    if spec_desc and curr_desc != spec_desc:
        return True
    return curr_state != spec_state


def find_milestones_to_update(
    desired: list[MilestoneSpec], existing: list[dict[str, Any]]
) -> list[tuple[int, MilestoneSpec]]:
    """Identify existing milestones whose description or state differs from desired spec."""
    existing_map: dict[str, dict[str, Any]] = {
        item.get("title", ""): item for item in existing if isinstance(item, dict)
    }
    to_update: list[tuple[int, MilestoneSpec]] = []
    for spec in desired:
        curr = existing_map.get(spec.title)
        if not curr or "number" not in curr:
            continue
        if _is_milestone_update_needed(curr, spec):
            to_update.append((int(curr["number"]), spec))
    return to_update


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
    to_update = find_milestones_to_update(desired, existing)

    result = MilestoneSyncResult(
        created_count=len(to_create),
        updated_count=len(to_update),
        existing_count=len(existing_matches),
        dry_run=dry_run,
        created=[s.title for s in to_create],
        updated=[spec.title for _, spec in to_update],
    )

    if dry_run:
        return result

    for spec in to_create:
        _apply_milestone_creation(client, repo, spec)

    for num, spec in to_update:
        edit_repository_milestone(client, repo, num, description=spec.description, state=spec.state)

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


def _resolve_milestone_target_number(
    client: Any, repo: str, version_or_title_or_number: str | int
) -> int | None:
    """Resolve a version string, title, or integer into a milestone number."""
    if isinstance(version_or_title_or_number, int):
        return version_or_title_or_number
    cleaned = str(version_or_title_or_number).strip()
    if cleaned.isdigit():
        return int(cleaned)

    get_fn = getattr(client, "get_milestones", None)
    raw = []
    if callable(get_fn):
        try:
            raw = get_fn(repo, state="all")
        except TypeError:
            raw = get_fn(state="all")

    existing = _extract_milestones_from_raw(raw)
    candidates = {cleaned, cleaned.lstrip("v"), f"v{cleaned.lstrip('v')}"}
    matched = next((m for m in existing if m.get("title") in candidates), None)
    if matched and "number" in matched:
        return int(matched["number"])
    return None


def edit_repository_milestone(
    client: Any,
    repo: str,
    version_or_title_or_number: str | int,
    title: str | None = None,
    description: str | None = None,
    state: str | None = None,
    due_on: str | None = None,
) -> bool:
    """Edit an existing milestone's title, description, state, or due date."""
    target_num = _resolve_milestone_target_number(client, repo, version_or_title_or_number)
    if target_num is None:
        return False

    func = getattr(client, "edit_milestone", None)
    if not callable(func):
        return False

    kwargs: dict[str, Any] = {}
    if title is not None:
        kwargs["title"] = title
    if description is not None:
        kwargs["description"] = description
    if state is not None:
        kwargs["state"] = state
    if due_on is not None:
        kwargs["due_on"] = due_on

    try:
        func(repo, target_num, **kwargs)
        return True
    except TypeError:
        try:
            func(target_num, **kwargs)
            return True
        except Exception:
            return False


def close_repository_milestone(client: Any, repo: str, version_or_title: str) -> bool:
    """Close a repository milestone matching the given version or title string."""
    func = getattr(client, "close_milestone", None)
    if callable(func):
        try:
            return bool(func(repo, version_or_title))
        except TypeError:
            return bool(func(version_or_title))

    get_fn = getattr(client, "get_milestones", None)
    if callable(get_fn):
        try:
            raw = get_fn(repo, state="all")
        except TypeError:
            raw = get_fn(state="all")
        existing = _extract_milestones_from_raw(raw)
        target = version_or_title.strip()
        candidates = {target, target.lstrip("v"), f"v{target.lstrip('v')}"}
        matched = next((m for m in existing if m.get("title") in candidates), None)
        if matched and "number" in matched:
            edit_fn = getattr(client, "edit_milestone", None)
            if callable(edit_fn):
                edit_fn(repo, int(matched["number"]), state="closed")
                return True
    return edit_repository_milestone(client, repo, version_or_title, state="closed")
