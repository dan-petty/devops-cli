"""Automated Roadmap to GitHub Issues and Tasks synchronization engine.

Extracts uncompleted deliverables from docs/ROADMAP.md, queries existing GitHub issues
and local task tracking files to prevent duplicates, creates typed GitHub issues with
taxonomy labels, and generates corresponding local task files.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_ROADMAP_PRIORITY_TAGS,
    CONST_ROADMAP_SCOPE_KEYWORDS,
)
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.issues import (
    GitHubIssue,
    create_repository_issue,
    get_repository_issues,
)
from devops_cli.github.milestones import _validate_roadmap_path
from devops_cli.output import write_text_file

logger = logging.getLogger(__name__)


class RoadmapItem(BaseModel):
    """Normalized deliverable item parsed from strategic roadmap."""

    milestone: str
    milestone_title: str
    milestone_status: str
    raw_title: str
    title: str
    priority: str = "priority/p1-high"
    scope: str = "scope/cli"
    labels: list[str] = Field(default_factory=list)
    context: str = ""
    sub_bullets: list[str] = Field(default_factory=list)
    is_completed: bool = False
    existing_issue_number: int | None = None

    @property
    def slug(self) -> str:
        """Generate URL-safe lowercase slug from deliverable title."""
        cleaned = re.sub(r"[^a-z0-9]+", "-", self.title.lower()).strip("-")
        return cleaned[:60].rstrip("-")


class RoadmapSyncResult(BaseModel):
    """Summary of roadmap-to-issues synchronization execution."""

    total_roadmap_items: int = 0
    eligible_uncompleted: int = 0
    already_tracked: int = 0
    created_count: int = 0
    dry_run: bool = False
    created_issues: list[dict[str, Any]] = Field(default_factory=list)
    task_files_created: list[str] = Field(default_factory=list)


def _extract_priority(text: str) -> str:
    """Extract standard priority tag from item text or title."""
    lower = text.lower()
    for priority, tags in CONST_ROADMAP_PRIORITY_TAGS.items():
        if any(tag in lower for tag in tags):
            return priority
    return "priority/p1-high"


def _derive_scope(title: str) -> str:
    """Derive standard scope taxonomy label from item title."""
    lower = title.lower()
    words = set(re.findall(r"\b[a-z0-9_-]+\b", lower))
    for scope, keywords in CONST_ROADMAP_SCOPE_KEYWORDS.items():
        if words & keywords:
            return scope
    return "scope/cli"


def _extract_existing_issue_number(title: str) -> int | None:
    """Extract referenced issue number from deliverable title if present."""
    match = re.search(r"(?:#|Issue\s+#?)(\d+)", title, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _clean_item_title(raw_title: str) -> str:
    """Strip priority, command tags, and issue numbers from raw item title."""
    cleaned = re.sub(r"\([pP][0-3]\s*-\s*[^)]+\)", "", raw_title)
    cleaned = re.sub(r"\(Issue\s*#?\d+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(#\d+\)", "", cleaned)
    cleaned = re.sub(r"\(PR\s*#?\d+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*:\s*", " ", cleaned)
    return " ".join(cleaned.split()).strip(" :-,")


def _parse_single_roadmap_item(
    item_header: str,
    body_lines: list[str],
    milestone: str,
    milestone_title: str,
    milestone_status: str,
) -> RoadmapItem:
    """Parse an item header line and its indented body lines into a RoadmapItem."""
    is_completed = item_header.startswith("- [x]") or item_header.startswith("- [X]")
    match = re.search(r"- \[[ xX]\] \*\*(.+?)\*\*(?::\s*(.*))?", item_header)
    raw_title = match.group(1).strip() if match else item_header[6:].strip()
    direct_desc = match.group(2).strip() if match and match.group(2) else ""

    clean_title = _clean_item_title(raw_title)
    priority = _extract_priority(item_header + " " + " ".join(body_lines))
    scope = _derive_scope(clean_title)
    issue_num = _extract_existing_issue_number(item_header)

    labels = ["type/feature", scope, priority]

    context = direct_desc
    sub_bullets: list[str] = []
    for line in body_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("- *Context & Rationale*:"):
            context = stripped.replace("- *Context & Rationale*:", "").strip()
        sub_bullets.append(stripped.lstrip("- *").strip())

    return RoadmapItem(
        milestone=milestone,
        milestone_title=milestone_title,
        milestone_status=milestone_status,
        raw_title=raw_title,
        title=clean_title,
        priority=priority,
        scope=scope,
        labels=labels,
        context=context,
        sub_bullets=sub_bullets,
        is_completed=is_completed,
        existing_issue_number=issue_num,
    )


def _parse_subsection_items(
    subsection_text: str,
    milestone: str,
    milestone_title: str,
    milestone_status: str,
) -> list[RoadmapItem]:
    """Parse milestone subsection lines into a list of RoadmapItems."""
    items: list[RoadmapItem] = []
    lines = subsection_text.splitlines()
    current_header: str | None = None
    current_body: list[str] = []

    for line in lines:
        if line.startswith("- [ ]") or line.startswith("- [x]") or line.startswith("- [X]"):
            if current_header:
                items.append(
                    _parse_single_roadmap_item(
                        current_header, current_body, milestone, milestone_title, milestone_status
                    )
                )
                current_body = []
            current_header = line
        elif current_header:
            current_body.append(line)

    if current_header:
        items.append(
            _parse_single_roadmap_item(
                current_header, current_body, milestone, milestone_title, milestone_status
            )
        )

    return items


_ROADMAP_SUBSECTION_REGEX = re.compile(
    r"^###\s+(.+?)\s+\((v\d+\.\d+\.\d+)(?:\s*-\s*([^)]+))?\)",
    re.MULTILINE,
)


def extract_roadmap_items(
    roadmap_path: Path = Path("docs/ROADMAP.md"),
) -> list[RoadmapItem]:
    """Parse Section 2 of ROADMAP.md into a list of typed RoadmapItem models."""
    valid_path = _validate_roadmap_path(roadmap_path)
    content = valid_path.read_text(encoding="utf-8")

    sec2_match = re.search(r"## Release Milestones \(Chronological Order\)\n\n", content)
    sec3_match = re.search(r"\n## Value vs\. Effort Prioritization Matrix", content)
    if not sec2_match or not sec3_match:
        return []

    sec2_text = content[sec2_match.end() : sec3_match.start()]
    matches = list(_ROADMAP_SUBSECTION_REGEX.finditer(sec2_text))
    items: list[RoadmapItem] = []

    for index, match in enumerate(matches):
        m_title = match.group(1).strip()
        m_version = match.group(2).strip()
        m_status = (match.group(3) or "Scheduled").strip()

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(sec2_text)
        sub_text = sec2_text[start:end]

        sub_items = _parse_subsection_items(sub_text, m_version, m_title, m_status)
        items.extend(sub_items)

    return items


def _is_issue_matching_item(issue: GitHubIssue, item: RoadmapItem) -> bool:
    """Predicate determining if an existing issue corresponds to a roadmap item."""
    if item.existing_issue_number and issue.number == item.existing_issue_number:
        return True

    clean_issue = re.sub(
        r"^(?:feat|fix|refactor|docs)\([^)]*\):\s*", "", issue.title, flags=re.IGNORECASE
    ).lower()
    clean_item = item.title.lower()
    if clean_item in clean_issue or clean_issue in clean_item:
        return True

    issue_words = set(re.findall(r"[a-z0-9]{4,}", clean_issue))
    item_words = set(re.findall(r"[a-z0-9]{4,}", clean_item))
    overlap = issue_words & item_words
    return len(overlap) >= 3


def _find_task_file_for_item(tasks_dir: Path, item: RoadmapItem) -> Path | None:
    """Check if a local task tracking file already exists for this roadmap item."""
    if not tasks_dir.is_dir():
        return None
    slug_prefix = item.slug[:25]
    for task_file in tasks_dir.glob("task-*.md"):
        if slug_prefix in task_file.stem:
            return task_file
    return None


def _is_item_already_tracked(
    item: RoadmapItem,
    existing_issues: list[GitHubIssue],
    tasks_dir: Path,
) -> bool:
    """Check if roadmap item is already tracked in GitHub Issues or docs/agent/tasks/."""
    if _find_task_file_for_item(tasks_dir, item) is not None:
        return True
    return any(_is_issue_matching_item(iss, item) for iss in existing_issues)


def _generate_task_file_content(
    issue_number: int,
    item: RoadmapItem,
    repo: str,
) -> str:
    """Generate Markdown content for a new local task tracking file."""
    labels_md = ", ".join(f"`{lbl}`" for lbl in item.labels)
    deliverables_md = (
        "\n".join(f"- {b}" for b in item.sub_bullets)
        if item.sub_bullets
        else f"- {item.context or item.title}"
    )
    return (
        f"# Task {issue_number}: {item.title}\n\n"
        f"**Issue**: [#{issue_number}](https://github.com/{repo}/issues/{issue_number})\n"
        f"**PR**: None (Draft)\n"
        f"**Status**: Backlog\n"
        f"**Milestone**: `{item.milestone}`\n"
        f"**Priority**: `{item.priority}`\n"
        f"**Scope**: {labels_md}\n\n"
        f"---\n\n"
        f"## 1. Description & Objectives\n\n"
        f"{item.context or item.title}\n\n"
        f"#### Key Deliverables:\n"
        f"{deliverables_md}\n"
        f"- Unit and integration test coverage with structural tuple equality assertions.\n"
        f"- Maintain cyclomatic complexity $M \\le 10$ and nesting depth $\\le 5$.\n"
        f"- 100% passing across all 10 CI quality gates (`uv run devops ci`).\n"
    )


def _generate_issue_body(item: RoadmapItem, repo: str) -> str:
    """Generate structured markdown body for a new GitHub issue."""
    deliverables_md = (
        "\n".join(f"- {b}" for b in item.sub_bullets)
        if item.sub_bullets
        else f"- {item.context or item.title}"
    )
    return (
        f"## Context & Rationale\n"
        f"{item.context or item.title}\n\n"
        f"## Scope & Deliverables\n"
        f"{deliverables_md}\n\n"
        f"## Strategic Alignment\n"
        f"- **Milestone**: `{item.milestone}` ({item.milestone_title})\n"
        f"- **Roadmap Reference**: [`docs/ROADMAP.md`](https://github.com/{repo}/blob/main/docs/ROADMAP.md)\n"
    )


def _process_sync_item(
    repo: str,
    item: RoadmapItem,
    tasks_dir: Path,
    dry_run: bool,
    result: RoadmapSyncResult,
) -> None:
    """Create GitHub Issue and task file for a single roadmap item."""
    scope_tag = item.scope.replace("scope/", "")
    issue_title = f"feat({scope_tag}): {item.title.lower()}"
    issue_body = _generate_issue_body(item, repo)

    if dry_run:
        result.created_count += 1
        result.created_issues.append(
            {
                "number": 0,
                "title": issue_title,
                "milestone": item.milestone,
                "labels": item.labels,
                "dry_run": True,
            }
        )
        return

    try:
        created = create_repository_issue(
            repo,
            title=issue_title,
            body=issue_body,
            milestone=item.milestone,
            labels=item.labels,
        )
    except GitHubOperationError as exc:
        logger.warning("Failed to create issue for %r: %s", item.title, exc)
        return

    result.created_count += 1
    result.created_issues.append(
        {
            "number": created.number,
            "title": created.title,
            "milestone": item.milestone,
            "labels": item.labels,
            "url": created.url,
        }
    )

    if created.number > 0:
        task_filename = f"task-{created.number}-{item.slug}.md"
        task_path = tasks_dir / task_filename
        content = _generate_task_file_content(created.number, item, repo)
        write_text_file(task_path, content)
        result.task_files_created.append(str(task_path))


def sync_roadmap_to_issues(
    repo: str,
    roadmap_path: Path = Path("docs/ROADMAP.md"),
    tasks_dir: Path = Path("docs/agent/tasks"),
    milestone_filter: str | None = None,
    dry_run: bool = False,
    limit: int = 50,
) -> RoadmapSyncResult:
    """Reconcile roadmap deliverables with GitHub Issues and per-task tracking files."""
    all_items = extract_roadmap_items(roadmap_path)
    uncompleted = [i for i in all_items if not i.is_completed]
    if milestone_filter:
        uncompleted = [i for i in uncompleted if i.milestone == milestone_filter]

    existing_issues = get_repository_issues(repo, state="all", limit=200)

    result = RoadmapSyncResult(
        total_roadmap_items=len(all_items),
        eligible_uncompleted=len(uncompleted),
        dry_run=dry_run,
    )

    for item in uncompleted:
        if result.created_count >= limit:
            break

        if _is_item_already_tracked(item, existing_issues, tasks_dir):
            result.already_tracked += 1
            continue

        _process_sync_item(repo, item, tasks_dir, dry_run, result)

    return result
