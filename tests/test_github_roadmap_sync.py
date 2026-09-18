"""Unit tests for Roadmap to GitHub Issues synchronization engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from devops_cli.commands.gh import app
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.issues import GitHubIssue
from devops_cli.github.roadmap_sync import (
    RoadmapItem,
    _clean_item_title,
    _derive_scope,
    _extract_existing_issue_number,
    _extract_priority,
    _find_task_file_for_item,
    _is_issue_matching_item,
    extract_roadmap_items,
    sync_roadmap_to_issues,
)

runner = CliRunner()


def test_roadmap_item_slug_and_normalization() -> None:
    """RoadmapItem computes url-safe slugs and preserves metadata."""
    item1 = RoadmapItem(
        milestone="v0.2.20",
        milestone_title="Core Stabilization",
        milestone_status="Active",
        raw_title="Fix (P0 - Critical) Bug in Auth (#254)",
        title="Fix Bug in Auth",
    )
    item2 = RoadmapItem(
        milestone="v0.2.21",
        milestone_title="AI Architecture",
        milestone_status="Scheduled",
        raw_title="Extremely Long Deliverable Title That Exceeds Sixty Characters In Length Overall",
        title="Extremely Long Deliverable Title That Exceeds Sixty Characters In Length Overall",
    )
    assert (item1.slug, len(item2.slug) <= 60) == ("fix-bug-in-auth", True)


def test_extract_priority_and_derive_scope() -> None:
    """Extraction helpers parse priorities and domain scopes correctly."""
    p0 = _extract_priority("Critical fix (P0 - Blocker)")
    p1 = _extract_priority("Feature work (P1 - High)")
    p2 = _extract_priority("Minor tweak (P2 - Medium)")
    p3 = _extract_priority("Backlog chore (P3 - Low)")
    p_default = _extract_priority("Unspecified priority item")

    s_gh = _derive_scope("Automated PM sprint board sync")
    s_ai = _derive_scope("MCTS heuristic exploration tree")
    s_k8s = _derive_scope("Kubernetes helm chart validation")
    s_sec = _derive_scope("Vault secret rotation and trivy scan")
    s_rev = _derive_scope("Code review finding deduplication")
    s_docs = _derive_scope("Compaction and roadmap guide")
    s_tel = _derive_scope("Jaeger tracing telemetry probe")
    s_cli = _derive_scope("General workstation command ergonomics")

    assert (
        p0,
        p1,
        p2,
        p3,
        p_default,
        s_gh,
        s_ai,
        s_k8s,
        s_sec,
        s_rev,
        s_docs,
        s_tel,
        s_cli,
    ) == (
        "priority/p0-critical",
        "priority/p1-high",
        "priority/p2-medium",
        "priority/p3-low",
        "priority/p1-high",
        "scope/github",
        "scope/ai",
        "scope/k8s",
        "scope/security",
        "scope/review",
        "scope/docs",
        "scope/telemetry",
        "scope/cli",
    )


def test_clean_item_title_and_issue_number() -> None:
    """Title cleaning strips tags and extracts issue numbers accurately."""
    raw1 = "**Forward-Looking PM Engine** (P0 - High) (Issue #254): Automatic sync."
    raw2 = "Universal trailing --dry-run option (#252)"
    raw3 = "Vanilla deliverable without issue"

    clean1 = _clean_item_title(raw1)
    clean2 = _clean_item_title(raw2)
    clean3 = _clean_item_title(raw3)

    num1 = _extract_existing_issue_number(raw1)
    num2 = _extract_existing_issue_number(raw2)
    num3 = _extract_existing_issue_number(raw3)

    assert (
        clean1,
        clean2,
        clean3,
        num1,
        num2,
        num3,
    ) == (
        "**Forward-Looking PM Engine** Automatic sync.",
        "Universal trailing --dry-run option",
        "Vanilla deliverable without issue",
        254,
        252,
        None,
    )


def test_extract_roadmap_items_synthetic(tmp_path: Path) -> None:
    """Parser extracts sections, checkboxes, and metadata from synthetic roadmap."""
    content = (
        "# Strategic Roadmap\n\n"
        "## Release Milestones (Chronological Order)\n\n"
        "### Core Engine (v0.2.20 - Active Release Candidate)\n\n"
        "- [x] **Universal dry-run option** (P1 - High): Trailing option support (#252).\n"
        "  - *Context & Rationale*: Ensures dry-run safety.\n"
        "  - Standardize option across all subcommands.\n\n"
        "- [ ] **Forward-looking PM engine** (P0 - High): Proactive roadmap expansion.\n"
        "  - *Context & Rationale*: Roadmap to issue bridge.\n"
        "  - Implement roadmap sync command.\n\n"
        "### Future Expansion (v0.2.21 - Scheduled)\n\n"
        "- [ ] **MCTS Planning Harness** (P1 - Medium): Tree search engine.\n"
        "  - Multi-agent coordination.\n\n"
        "## Value vs. Effort Prioritization Matrix\n\n"
        "| Series | Status |\n"
    )
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(content, encoding="utf-8")

    items = extract_roadmap_items(roadmap_file)
    assert len(items) == 3

    item0, item1, item2 = items[0], items[1], items[2]
    assert (
        item0.is_completed,
        item0.milestone,
        item0.existing_issue_number,
        item1.is_completed,
        item1.milestone,
        item1.priority,
        item2.is_completed,
        item2.milestone,
    ) == (
        True,
        "v0.2.20",
        252,
        False,
        "v0.2.20",
        "priority/p0-critical",
        False,
        "v0.2.21",
    )


def test_extract_roadmap_items_missing_sections(tmp_path: Path) -> None:
    """Parser returns empty list if roadmap lacks expected section headers."""
    bad_roadmap = tmp_path / "BAD_ROADMAP.md"
    bad_roadmap.write_text("# Incomplete Document\nSome content\n", encoding="utf-8")
    assert extract_roadmap_items(bad_roadmap) == []


def test_extract_roadmap_items_live_file() -> None:
    """Live docs/ROADMAP.md parses successfully with active and scheduled milestones."""
    items = extract_roadmap_items(Path("docs/ROADMAP.md"))
    assert len(items) >= 5

    milestones = {i.milestone for i in items}
    assert ("v0.2.20" in milestones, any(not i.is_completed for i in items)) == (True, True)


def test_is_issue_matching_item() -> None:
    """Issue matching predicates identify exact numbers, substrings, and word sets."""
    item = RoadmapItem(
        milestone="v0.2.20",
        milestone_title="Release",
        milestone_status="Active",
        raw_title="Forward-Looking PM Engine (#254)",
        title="Forward-Looking PM Engine",
        existing_issue_number=254,
    )
    issue_num_match = GitHubIssue(
        number=254,
        title="feat(pm): other title",
        state="open",
        url="https://example.com/issues/254",
    )
    issue_title_match = GitHubIssue(
        number=300,
        title="feat(pm): forward-looking pm engine implementation",
        state="open",
        url="https://example.com/issues/300",
    )
    issue_word_match = GitHubIssue(
        number=301,
        title="chore: forward looking engine operational hardening",
        state="open",
        url="https://example.com/issues/301",
    )
    issue_unrelated = GitHubIssue(
        number=302,
        title="fix(k8s): resolve minikube ingress crash",
        state="open",
        url="https://example.com/issues/302",
    )

    assert (
        _is_issue_matching_item(issue_num_match, item),
        _is_issue_matching_item(issue_title_match, item),
        _is_issue_matching_item(issue_word_match, item),
        _is_issue_matching_item(issue_unrelated, item),
    ) == (True, True, True, False)


def test_find_task_file_for_item(tmp_path: Path) -> None:
    """Local task file detector discovers matching files by slug prefix."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    matching_file = tasks_dir / "task-254-forward-looking-pm-engine.md"
    matching_file.write_text("# Task 254", encoding="utf-8")

    item_match = RoadmapItem(
        milestone="v0.2.20",
        milestone_title="Release",
        milestone_status="Active",
        raw_title="Forward-Looking PM Engine",
        title="Forward-Looking PM Engine",
    )
    item_no_match = RoadmapItem(
        milestone="v0.2.20",
        milestone_title="Release",
        milestone_status="Active",
        raw_title="Unrelated Capability",
        title="Unrelated Capability",
    )

    found = _find_task_file_for_item(tasks_dir, item_match)
    not_found = _find_task_file_for_item(tasks_dir, item_no_match)
    missing_dir = _find_task_file_for_item(tmp_path / "nonexistent", item_match)

    assert (
        found == matching_file,
        not_found is None,
        missing_dir is None,
    ) == (True, True, True)


@patch("devops_cli.github.roadmap_sync.get_repository_issues")
def test_sync_roadmap_dry_run(mock_get_issues: MagicMock, tmp_path: Path) -> None:
    """Dry-run mode calculates eligible deliverables without remote API calls or writes."""
    mock_get_issues.return_value = []
    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(
        "# Strategic Roadmap\n\n"
        "## Release Milestones (Chronological Order)\n\n"
        "### Active (v0.2.20 - Active Release Candidate)\n\n"
        "- [ ] **Autonomous Verification Engine** (P1 - High): Auto test generation.\n"
        "  - Context & Rationale: Automated feedback.\n\n"
        "## Value vs. Effort Prioritization Matrix\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    result = sync_roadmap_to_issues(
        repo="dan-petty/devops-cli",
        roadmap_path=roadmap_file,
        tasks_dir=tasks_dir,
        dry_run=True,
    )

    assert (
        result.dry_run,
        result.total_roadmap_items,
        result.eligible_uncompleted,
        result.created_count,
        len(result.task_files_created),
    ) == (True, 1, 1, 1, 0)


@patch("devops_cli.github.roadmap_sync.get_repository_issues")
def test_sync_roadmap_milestone_and_deduplication(
    mock_get_issues: MagicMock, tmp_path: Path
) -> None:
    """Sync filters by milestone and skips items already tracked in GitHub Issues."""
    existing = GitHubIssue(
        number=101,
        title="feat(cli): autonomous verification engine",
        state="open",
        url="https://example.com/issues/101",
    )
    mock_get_issues.return_value = [existing]

    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(
        "# Strategic Roadmap\n\n"
        "## Release Milestones (Chronological Order)\n\n"
        "### Active (v0.2.20 - Active Release Candidate)\n\n"
        "- [ ] **Autonomous Verification Engine** (P1 - High): Auto test generation.\n\n"
        "### Scheduled (v0.2.21 - Scheduled)\n\n"
        "- [ ] **Constellation Graph** (P2 - Medium): Visualization.\n\n"
        "## Value vs. Effort Prioritization Matrix\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    # Filter to v0.2.20 where the item is already tracked
    res_tracked = sync_roadmap_to_issues(
        repo="dan-petty/devops-cli",
        roadmap_path=roadmap_file,
        tasks_dir=tasks_dir,
        milestone_filter="v0.2.20",
        dry_run=True,
    )
    assert (
        res_tracked.eligible_uncompleted,
        res_tracked.already_tracked,
        res_tracked.created_count,
    ) == (1, 1, 0)

    # Filter to v0.2.21 where the item is untracked
    res_untracked = sync_roadmap_to_issues(
        repo="dan-petty/devops-cli",
        roadmap_path=roadmap_file,
        tasks_dir=tasks_dir,
        milestone_filter="v0.2.21",
        dry_run=True,
    )
    assert (
        res_untracked.eligible_uncompleted,
        res_untracked.already_tracked,
        res_untracked.created_count,
    ) == (1, 0, 1)


@patch("devops_cli.github.roadmap_sync.create_repository_issue")
@patch("devops_cli.github.roadmap_sync.get_repository_issues")
def test_sync_roadmap_live_execution(
    mock_get_issues: MagicMock,
    mock_create_issue: MagicMock,
    tmp_path: Path,
) -> None:
    """Live mode creates GitHub Issue and local task file upon success."""
    mock_get_issues.return_value = []
    mock_create_issue.return_value = GitHubIssue(
        number=999,
        title="feat(ai): autonomous verification engine",
        state="open",
        url="https://example.com/issues/999",
    )

    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(
        "# Strategic Roadmap\n\n"
        "## Release Milestones (Chronological Order)\n\n"
        "### Active (v0.2.20 - Active Release Candidate)\n\n"
        "- [ ] **Autonomous Verification Engine** (P1 - High): Auto test generation.\n"
        "  - Key bullet point.\n\n"
        "## Value vs. Effort Prioritization Matrix\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    result = sync_roadmap_to_issues(
        repo="dan-petty/devops-cli",
        roadmap_path=roadmap_file,
        tasks_dir=tasks_dir,
        dry_run=False,
    )

    created_task_file = tasks_dir / "task-999-autonomous-verification-engine.md"
    assert (
        result.created_count,
        len(result.task_files_created),
        created_task_file.is_file(),
    ) == (1, 1, True)
    assert "# Task 999" in created_task_file.read_text(encoding="utf-8")


@patch("devops_cli.github.roadmap_sync.create_repository_issue")
@patch("devops_cli.github.roadmap_sync.get_repository_issues")
def test_sync_roadmap_error_handling(
    mock_get_issues: MagicMock,
    mock_create_issue: MagicMock,
    tmp_path: Path,
) -> None:
    """GitHub API errors during issue creation are caught gracefully."""
    mock_get_issues.return_value = []
    mock_create_issue.side_effect = GitHubOperationError("API rate limit exceeded")

    roadmap_file = tmp_path / "ROADMAP.md"
    roadmap_file.write_text(
        "# Strategic Roadmap\n\n"
        "## Release Milestones (Chronological Order)\n\n"
        "### Active (v0.2.20 - Active Release Candidate)\n\n"
        "- [ ] **Error Prone Capability** (P1 - High): Testing error resilience.\n\n"
        "## Value vs. Effort Prioritization Matrix\n",
        encoding="utf-8",
    )
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    result = sync_roadmap_to_issues(
        repo="dan-petty/devops-cli",
        roadmap_path=roadmap_file,
        tasks_dir=tasks_dir,
        dry_run=False,
    )

    assert (result.created_count, len(result.task_files_created)) == (0, 0)


@patch("devops_cli.github.roadmap_sync.get_repository_issues")
def test_cli_gh_issues_sync_roadmap_cmd(mock_get_issues: MagicMock, tmp_path: Path) -> None:
    """CLI subcommand devops gh issues sync-roadmap executes cleanly with --dry-run."""
    mock_get_issues.return_value = []
    res = runner.invoke(app, ["issues", "sync-roadmap", "--milestone", "v0.2.20", "--dry-run"])
    assert (res.exit_code, "Total Roadmap Items" in res.output, "Dry-Run" in res.output) == (
        0,
        True,
        True,
    )
