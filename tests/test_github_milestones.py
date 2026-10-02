"""Test suite for GitHub Milestones extraction, synchronization, and progress tracking."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.gh import milestones_app
from devops_cli.github.milestones import (
    MilestoneSpec,
    calculate_milestone_progress,
    diff_milestones,
    extract_roadmap_milestones,
    sync_repository_milestones,
)
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, Release

runner = CliRunner()
# Not this checkout's origin, so a command that ignored `--repo` would open the wrong store.
REPO = "example/scratch"


def test_extract_roadmap_milestones(tmp_path: Path) -> None:
    """extract_roadmap_milestones parses markdown milestone headings into MilestoneSpec objects."""
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text(
        "# Roadmap\n\n"
        "### Core Foundation (v0.0.1 - Completed)\n"
        "- [x] Feature A\n\n"
        "### Valkey Management (v0.2.12 - Scheduled)\n"
        "- [ ] Task 1\n\n"
        "### Library Ingestion (v0.2.13 - Scheduled)\n"
        "- [ ] Task 2\n",
        encoding="utf-8",
    )

    specs = extract_roadmap_milestones(roadmap)
    assert len(specs) >= 2
    titles = [s.title for s in specs]
    assert "v0.2.12" in titles
    assert "v0.2.13" in titles
    valkey_spec = next(s for s in specs if s.title == "v0.2.12")
    assert valkey_spec.description == "Valkey Management"
    assert "Scheduled" not in valkey_spec.description

    core_spec = next(s for s in specs if s.title == "v0.0.1")
    assert core_spec.description == "Core Foundation"
    assert "Completed" not in core_spec.description
    assert core_spec.state == "closed"


def test_diff_milestones() -> None:
    """diff_milestones matches desired milestones to Releases by version, with or without the v."""
    desired = [
        MilestoneSpec(title="v0.2.12", description="Valkey"),
        MilestoneSpec(title="v0.2.13", description="Library"),
    ]
    existing = [Release(number=1, title="0.2.12", description="Valkey")]

    to_create, existing_matches = diff_milestones(desired, existing)
    assert (
        [spec.title for spec in to_create],
        [release.number for release in existing_matches],
    ) == (
        ["v0.2.13"],
        [1],
    )


def test_sync_repository_milestones_dry_run() -> None:
    """A dry-run sync counts the Releases it would create and creates none."""
    store = InMemoryRoadmapStore()
    desired = [MilestoneSpec(title="v0.2.15", description="Scanner Framework")]

    res = sync_repository_milestones(store, desired, dry_run=True)
    assert (res.created_count, res.dry_run, store.releases()) == (1, True, [])


def test_sync_repository_milestones_creates_missing_and_updates_changed_releases() -> None:
    """A sync creates the missing Releases and edits those whose description or state differs."""
    store = InMemoryRoadmapStore()
    store.create_release("v0.2.14", description="Old name")
    store.create_release("v0.2.16", description="Same")
    desired = [
        MilestoneSpec(title="v0.2.14", description="Scanner Framework", state=GitHubState.CLOSED),
        MilestoneSpec(title="v0.2.15", description="Next"),
        MilestoneSpec(title="v0.2.16", description="Same"),
    ]

    res = sync_repository_milestones(store, desired)
    assert (
        res.created,
        res.updated,
        res.existing_count,
        [(r.title, r.description, r.state) for r in store.releases()],
    ) == (
        ["v0.2.15"],
        ["v0.2.14"],
        2,
        [
            ("v0.2.14", "Scanner Framework", GitHubState.CLOSED),
            ("v0.2.15", "Next", GitHubState.OPEN),
            ("v0.2.16", "Same", GitHubState.OPEN),
        ],
    )


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes closed ratio and health metrics."""
    release = Release(number=11, title="v0.2.11", open_issues=2, closed_issues=8)

    progress = calculate_milestone_progress(release)
    assert (progress.total_issues, progress.percent_complete, progress.is_complete) == (
        10,
        80.0,
        False,
    )


def test_cli_milestones_close_command(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones close closes the Release of a version, and exits 1 for an unknown one."""
    roadmap_store.create_release("v0.2.11")

    closed = runner.invoke(milestones_app, ["close", "0.2.11", "--repo", REPO])
    missing = runner.invoke(milestones_app, ["close", "v9.9.9", "--repo", REPO])
    release = roadmap_store.release("v0.2.11")
    assert (
        closed.exit_code,
        f"Successfully closed milestone '0.2.11' in {REPO}" in closed.output,
        release.state if release else None,
        missing.exit_code,
        "No Release 'v9.9.9' exists" in missing.output,
        roadmap_store_repos,
    ) == (0, True, GitHubState.CLOSED, 1, True, [REPO, REPO])


def test_validate_roadmap_path_helpers(tmp_path: Path) -> None:
    """Verify _is_safe_roadmap_path and _validate_roadmap_path prevent directory traversal."""
    import pytest

    from devops_cli.exceptions.git import GitHubOperationError
    from devops_cli.github.milestones import _is_safe_roadmap_path, _validate_roadmap_path

    # Safe vs unsafe path predicates
    assert (
        _is_safe_roadmap_path(Path("docs/ROADMAP.md")),
        _is_safe_roadmap_path(Path("docs/ROADMAP_2.md")),
        _is_safe_roadmap_path(tmp_path / "ROADMAP.md"),
        _is_safe_roadmap_path(Path("../ROADMAP.md")),
        _is_safe_roadmap_path(Path("docs/../ROADMAP.md")),
        _is_safe_roadmap_path(Path("docs/ROADMAP..md")),
        _is_safe_roadmap_path(Path("docs/../../ROADMAP.md")),
    ) == (True, True, True, False, False, True, False)

    # Traversal raises GitHubOperationError
    with pytest.raises(GitHubOperationError, match="Path traversal detected"):
        _validate_roadmap_path(Path("../ROADMAP.md"))

    with pytest.raises(GitHubOperationError, match="Path traversal detected"):
        _validate_roadmap_path(Path("foo/../bar.md"))

    # Missing file raises GitHubOperationError
    with pytest.raises(GitHubOperationError, match="Roadmap file not found"):
        _validate_roadmap_path(tmp_path / "nonexistent.md")

    # Valid file passes validation
    sample = tmp_path / "valid_roadmap.md"
    sample.write_text("# Roadmap\n", encoding="utf-8")
    assert _validate_roadmap_path(sample) == sample


def test_cli_labels_list() -> None:
    """devops gh labels list prints table of labels or info if empty."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch("devops_cli.commands.gh._get_repo_labels", return_value=[]):
        res = runner.invoke(app, ["labels", "list"])
        assert res.exit_code == 0
        assert "No remote repository labels found" in res.output

    with patch(
        "devops_cli.commands.gh._get_repo_labels",
        return_value=[{"name": "type/bug", "color": "d73a4a", "description": "Bug"}],
    ):
        res = runner.invoke(app, ["labels", "list"])
        assert res.exit_code == 0
        assert "type/bug" in res.output


def test_cli_labels_sync(tmp_path: Path) -> None:
    """devops gh labels sync reconciles labels with dry-run and shim support."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    labels_file = tmp_path / "labels.yml"
    labels_file.write_text(
        "- name: type/bug\n  color: d73a4a\n  description: Defect\n", encoding="utf-8"
    )

    runner = CliRunner()
    mock_client = MagicMock()
    mock_client.get_labels.return_value = []
    with (
        patch("devops_cli.commands.gh._get_github_client", return_value=mock_client),
        patch("devops_cli.commands.gh._get_repo_labels", return_value=[]),
    ):
        res = runner.invoke(app, ["labels", "sync", "--file", str(labels_file), "--dry-run"])
        assert res.exit_code == 0
        assert "DRY RUN" in res.output


def test_cli_labels_audit() -> None:
    """devops gh labels audit detects PRs with missing taxonomy."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    # Compliant PRs
    with patch(
        "devops_cli.commands.gh._get_repo_prs",
        return_value=[
            {
                "number": 1,
                "title": "feat: test",
                "labels": [{"name": "type/feature"}, {"name": "scope/cli"}],
            }
        ],
    ):
        res = runner.invoke(app, ["labels", "audit"])
        assert res.exit_code == 0
        assert "comply with taxonomy" in res.output

    # Non-compliant PRs
    with patch(
        "devops_cli.commands.gh._get_repo_prs",
        return_value=[{"number": 2, "title": "fix: bug", "labels": []}],
    ):
        res = runner.invoke(app, ["labels", "audit"])
        assert res.exit_code == 0
        assert "Pull Request Taxonomy Audit Findings" in res.output


def test_cli_milestones_list(roadmap_store: InMemoryRoadmapStore) -> None:
    """devops gh milestones list shows an empty notice, then the Releases in the state asked for."""
    empty = runner.invoke(milestones_app, ["list", "--repo", REPO])
    roadmap_store.create_release("v0.2.13")
    roadmap_store.create_release("v0.2.12", state=GitHubState.CLOSED)

    listed = runner.invoke(milestones_app, ["list", "--repo", REPO])
    open_only = runner.invoke(milestones_app, ["list", "--state", "open", "--repo", REPO])
    assert (
        (empty.exit_code, "No milestones found" in empty.output),
        (listed.exit_code, listed.output.index("v0.2.12") < listed.output.index("v0.2.13")),
        ("v0.2.13" in open_only.output, "v0.2.12" in open_only.output),
    ) == ((0, True), (0, True), (True, False))


def test_cli_milestones_list_refuses_an_unknown_state(roadmap_store: InMemoryRoadmapStore) -> None:
    """devops gh milestones list exits 1 for a state filter that is not open, closed or all."""
    res = runner.invoke(milestones_app, ["list", "--state", "merged", "--repo", REPO])
    assert (res.exit_code, "Unsupported state 'merged'" in res.output) == (1, True)


def test_cli_milestones_list_names_a_failed_read(
    unreadable_github_roadmap: list[list[str]],
) -> None:
    """When GitHub can't be read, list exits 1 and names the read instead of finding nothing."""
    res = runner.invoke(milestones_app, ["list", "--repo", REPO])
    assert (
        res.exit_code,
        f"Could not read milestones in {REPO} (exit 1)" in res.output,
        "No milestones found" in res.output,
        unreadable_github_roadmap,
    ) == (
        1,
        True,
        False,
        [["api", "--paginate", f"repos/{REPO}/milestones?state=all&per_page=100"]],
    )


def test_cli_milestones_status(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones status shows a Release's progress, and exits 1 for an unknown one."""
    roadmap_store.create_release("v0.2.13")
    for state in [GitHubState.OPEN] * 2 + [GitHubState.CLOSED] * 8:
        roadmap_store.seed_issue("Work", state=state, release="v0.2.13")

    found = runner.invoke(milestones_app, ["status", "0.2.13", "--repo", REPO])
    missing = runner.invoke(milestones_app, ["status", "v9.9.9", "--repo", REPO])
    assert (
        found.exit_code,
        "80.0%" in found.output,
        missing.exit_code,
        "not found" in missing.output,
        roadmap_store_repos,
    ) == (0, True, 1, True, [REPO, REPO])


def test_cli_milestones_sync(
    tmp_path: Path, roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones sync previews with --dry-run, then creates the roadmap's Releases."""
    roadmap = tmp_path / "ROADMAP.md"
    roadmap.write_text("# Roadmap\n### Test Milestone (v0.9.0 - Scheduled)\n", encoding="utf-8")

    dry = runner.invoke(
        milestones_app, ["sync", "--roadmap", str(roadmap), "--dry-run", "-R", REPO]
    )
    dry_releases = roadmap_store.releases()
    live = runner.invoke(milestones_app, ["sync", "--roadmap", str(roadmap), "-R", REPO])
    assert (
        (dry.exit_code, "1 created" in dry.output, dry_releases),
        (live.exit_code, [(r.title, r.description) for r in roadmap_store.releases()]),
        roadmap_store_repos,
    ) == ((0, True, []), (0, [("v0.9.0", "Test Milestone")]), [REPO, REPO])


def test_gh_helper_subprocess_fallbacks() -> None:
    """Test _get_repo_labels and _get_repo_prs with subprocess JSON output."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.commands.gh import _get_repo_labels, _get_repo_prs

    with patch("devops_cli.commands.gh.run_gh") as mock_sub:
        # labels
        mock_sub.return_value = MagicMock(returncode=0, stdout=json.dumps([{"name": "test"}]))
        assert len(_get_repo_labels("dan-petty/devops-cli")) == 1

        # prs
        mock_sub.return_value = MagicMock(
            returncode=0, stdout=json.dumps([{"number": 10, "title": "feat: test"}])
        )
        assert len(_get_repo_prs("dan-petty/devops-cli")) == 1
