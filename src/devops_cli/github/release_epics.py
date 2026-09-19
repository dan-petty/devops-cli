"""GitHub Release Epics / Tracking Issues generator, correlator, and synchronizer."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.github.issues import (
    GitHubIssue,
    create_repository_issue,
    edit_repository_issue,
    get_repository_issues,
)
from devops_cli.github.roadmap_sync import (
    RoadmapItem,
    _is_issue_matching_item,
    extract_roadmap_items,
)

logger = logging.getLogger(__name__)


class ReleaseEpicDeliverable(BaseModel):
    """Correlated deliverable item within a release epic."""

    title: str
    issue_number: int | None = None
    priority: str = "priority/p1-high"
    scope: str = "scope/cli"
    is_completed: bool = False


class ReleaseEpicSpec(BaseModel):
    """Specification for a release tracking epic."""

    milestone_version: str
    milestone_title: str
    milestone_status: str = "Scheduled"
    deliverables: list[ReleaseEpicDeliverable] = Field(default_factory=list)

    @property
    def total_count(self) -> int:
        """Total number of tracked deliverables."""
        return len(self.deliverables)

    @property
    def completed_count(self) -> int:
        """Number of completed deliverables."""
        return sum(1 for d in self.deliverables if d.is_completed)

    @property
    def percent_complete(self) -> float:
        """Percentage of deliverables marked completed."""
        if not self.deliverables:
            return 100.0
        return round((self.completed_count / self.total_count) * 100.0, 1)

    @property
    def is_all_completed(self) -> bool:
        """Whether every member deliverable is completed."""
        return bool(self.deliverables) and (self.completed_count == self.total_count)


class ReleaseEpicSyncResult(BaseModel):
    """Execution summary of release epics synchronization."""

    total_milestones: int = 0
    created_count: int = 0
    updated_count: int = 0
    unchanged_count: int = 0
    dry_run: bool = False
    epics: list[dict[str, Any]] = Field(default_factory=list)


def _format_deliverable_line(item: ReleaseEpicDeliverable) -> str:
    """Format a single deliverable line for markdown checklist."""
    check = "x" if item.is_completed else " "
    ref = f"#{item.issue_number}: " if item.issue_number else ""
    return f"- [{check}] {ref}{item.title} (`{item.priority}`, `{item.scope}`)"


def _render_choreography_checklist(spec: ReleaseEpicSpec) -> list[str]:
    """Render Phase 6 SDLC Release Choreography steps."""
    c = "x" if spec.is_all_completed else " "
    rc = "x" if spec.milestone_status.lower() == "completed" else " "
    return [
        "## Phase 6: SDLC Release Choreography",
        f"- [{c}] **Branch Synchronization**: Verify `release/{spec.milestone_version}` contains all merged deliverable PRs",
        f"- [{c}] **Gated CI Quality Gate**: 100% passing status on all validation checks (`uv run devops ci`)",
        f"- [{c}] **Security Audits & SBOM**: Generate SBOM and verify dependency security (`devops scan sbom`, `devops scan aibom`)",
        f"- [{rc}] **Release Pull Request**: Open release PR targeting `main` with generated release notes (`devops release pr`)",
        f"- [{rc}] **Multi-Persona Review Verification**: Complete automated reviews and squash-merge release PR into `main`",
        f"- [{rc}] **Git Release Tagging**: Push annotated tag `{spec.milestone_version}` (`devops release tag {spec.milestone_version}`)",
        f"- [{rc}] **Milestone Closure**: Close milestone `{spec.milestone_version}` on GitHub (`devops gh milestones close {spec.milestone_version}`)",
        f"- [{rc}] **Next Milestone Bootstrap**: Create and checkout next release branch for upcoming cycle",
    ]


def render_release_epic_body(spec: ReleaseEpicSpec) -> str:
    """Render full markdown dashboard body for a release tracking epic."""
    lines: list[str] = [
        f"# Release Epic: {spec.milestone_version} — {spec.milestone_title}",
        "",
        f"**Milestone**: `{spec.milestone_version}`  ",
        f"**Status**: `{spec.milestone_status}`  ",
        f"**Deliverable Progress**: {spec.completed_count}/{spec.total_count} completed ({spec.percent_complete}%)",
        "",
        "## Executive Summary",
        f"{spec.milestone_title}",
        "",
        "## Correlated Deliverables & Tasks",
    ]

    if spec.deliverables:
        lines.extend(_format_deliverable_line(d) for d in spec.deliverables)
    else:
        lines.append("- *(No specific deliverable items defined in roadmap)*")

    lines.append("")
    lines.extend(_render_choreography_checklist(spec))
    lines.append("")
    return "\n".join(lines)


def _resolve_item_issue_number(
    item: RoadmapItem, issues: list[GitHubIssue]
) -> tuple[int | None, bool]:
    """Resolve issue number and completion state for a roadmap deliverable."""
    if item.existing_issue_number:
        matching = next((iss for iss in issues if iss.number == item.existing_issue_number), None)
        if matching:
            return matching.number, (matching.state == "closed")
        return item.existing_issue_number, item.is_completed

    matching = next((iss for iss in issues if _is_issue_matching_item(iss, item)), None)
    if matching:
        return matching.number, (matching.state == "closed")

    return None, item.is_completed


def _build_single_epic_spec(
    m_ver: str,
    m_title: str,
    m_status: str,
    items: list[RoadmapItem],
    issues: list[GitHubIssue],
) -> ReleaseEpicSpec:
    """Build a ReleaseEpicSpec for a specific milestone version."""
    deliverables: list[ReleaseEpicDeliverable] = []
    for it in items:
        num, is_done = _resolve_item_issue_number(it, issues)
        deliverables.append(
            ReleaseEpicDeliverable(
                title=it.title,
                issue_number=num,
                priority=it.priority,
                scope=it.scope,
                is_completed=is_done,
            )
        )

    return ReleaseEpicSpec(
        milestone_version=m_ver,
        milestone_title=m_title,
        milestone_status=m_status,
        deliverables=deliverables,
    )


def build_release_epic_specs(
    roadmap_path: Path = Path("docs/ROADMAP.md"),
    issues: list[GitHubIssue] | None = None,
) -> list[ReleaseEpicSpec]:
    """Parse ROADMAP.md and build release epic specifications for all milestones."""
    all_items = extract_roadmap_items(roadmap_path)
    known_issues = issues or []

    grouped: dict[str, list[RoadmapItem]] = {}
    titles: dict[str, str] = {}
    statuses: dict[str, str] = {}

    for item in all_items:
        m = item.milestone
        if m not in grouped:
            grouped[m] = []
            titles[m] = item.milestone_title
            statuses[m] = item.milestone_status
        grouped[m].append(item)

    specs: list[ReleaseEpicSpec] = []
    for m_ver, items in grouped.items():
        spec = _build_single_epic_spec(
            m_ver,
            titles.get(m_ver, m_ver),
            statuses.get(m_ver, "Scheduled"),
            items,
            known_issues,
        )
        specs.append(spec)

    return specs


def find_existing_release_epic(
    issues: list[GitHubIssue], milestone_version: str
) -> GitHubIssue | None:
    """Locate an existing release epic issue for the specified milestone version."""
    cleaned = milestone_version.lstrip("v")
    prefixes = (
        f"release epic: v{cleaned}",
        f"release epic: {cleaned}",
    )
    for iss in issues:
        t_lower = iss.title.lower()
        if any(t_lower.startswith(prefix) for prefix in prefixes):
            return iss
    return None


def _is_epic_body_identical(old_body: str, new_body: str) -> bool:
    """Determine whether generated body is substantively identical to existing body."""
    return old_body.strip() == new_body.strip()


def sync_single_release_epic(
    repo: str,
    spec: ReleaseEpicSpec,
    existing_epic: GitHubIssue | None,
    dry_run: bool = False,
) -> tuple[str, int | None]:
    """Idempotently create or update a single release tracking epic."""
    title = f"Release Epic: {spec.milestone_version} — {spec.milestone_title}"
    body = render_release_epic_body(spec)

    if existing_epic:
        action = "unchanged"
        is_completed = spec.milestone_status.lower() == "completed"
        was_open = existing_epic.state.lower() == "open"

        if not _is_epic_body_identical(existing_epic.body, body):
            if not dry_run:
                edit_repository_issue(
                    repo=repo,
                    number=existing_epic.number,
                    title=title,
                    body=body,
                )
            action = "updated"

        if is_completed and was_open:
            if not dry_run:
                from devops_cli.github.issues import close_repository_issue

                close_repository_issue(repo, existing_epic.number)
            action = "updated"

        return action, existing_epic.number

    if not dry_run:
        labels = ["type/epic", "scope/release", "priority/p1-high"]
        created = create_repository_issue(
            repo=repo,
            title=title,
            body=body,
            milestone=spec.milestone_version,
            labels=labels,
        )
        if spec.milestone_status.lower() == "completed":
            from devops_cli.github.issues import close_repository_issue

            close_repository_issue(repo, created.number)
        return "created", created.number

    return "created", None


def sync_all_release_epics(
    repo: str,
    roadmap_path: Path = Path("docs/ROADMAP.md"),
    dry_run: bool = False,
    version_filter: str | None = None,
) -> ReleaseEpicSyncResult:
    """Synchronize release tracking epics for roadmap milestones."""
    try:
        issues = get_repository_issues(repo, state="all", limit=300)
    except Exception as exc:
        logger.warning("Failed to fetch repository issues: %s", exc)
        issues = []

    specs = build_release_epic_specs(roadmap_path, issues)
    if version_filter:
        cleaned_filter = f"v{version_filter.lstrip('v')}"
        specs = [s for s in specs if s.milestone_version == cleaned_filter]

    result = ReleaseEpicSyncResult(
        total_milestones=len(specs),
        dry_run=dry_run,
    )

    for spec in specs:
        existing = find_existing_release_epic(issues, spec.milestone_version)
        action, iss_num = sync_single_release_epic(repo, spec, existing, dry_run=dry_run)

        if action == "created":
            result.created_count += 1
        elif action == "updated":
            result.updated_count += 1
        else:
            result.unchanged_count += 1

        result.epics.append(
            {
                "version": spec.milestone_version,
                "action": action,
                "issue_number": iss_num,
                "deliverables": spec.total_count,
                "completed": spec.completed_count,
                "percent": spec.percent_complete,
            }
        )

    return result
