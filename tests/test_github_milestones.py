"""Test suite for GitHub Milestones progress tracking and the milestone commands."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from devops_cli.commands.gh import milestones_app
from devops_cli.github.milestones import calculate_milestone_progress
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, Release

runner = CliRunner()
# Not this checkout's origin, so a command that ignored `--repo` would open the wrong store.
REPO = "example/scratch"


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
        f"Could not read milestones (page 1) in {REPO} (exit 1)" in res.output,
        "No milestones found" in res.output,
        unreadable_github_roadmap,
    ) == (
        1,
        True,
        False,
        [["api", f"repos/{REPO}/milestones?state=all&per_page=100&page=1"]],
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
