"""Test suite for GitHub Milestones progress tracking and the milestone commands."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import milestones_app
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.milestones import calculate_milestone_progress
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, Milestone, RoadmapStore
from tests.support.fakes.github import API, GitHubApiFake, github_json

runner = CliRunner()
# Not this checkout's origin, so a command that ignored `--repo` would open the wrong store.
REPO = "example/scratch"


def test_calculate_milestone_progress() -> None:
    """calculate_milestone_progress computes closed ratio and health metrics."""
    milestone = Milestone(number=11, title="2026-11-05", open_issues=2, closed_issues=8)

    progress = calculate_milestone_progress(milestone)
    assert (
        progress.number,
        progress.total_issues,
        progress.percent_complete,
        progress.is_complete,
    ) == (11, 10, 80.0, False)


def test_cli_milestones_close_command(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones close closes the milestone a title or a number names, and exits 1
    for one that no milestone has. No title is read as a version."""
    titled = roadmap_store.seed_milestone("Q4 hardening")
    numbered = roadmap_store.seed_milestone("2026-11-05")

    by_title = runner.invoke(milestones_app, ["close", "Q4 hardening", "--repo", REPO])
    by_number = runner.invoke(milestones_app, ["close", str(numbered.number), "--repo", REPO])
    missing = runner.invoke(milestones_app, ["close", "Q4", "--repo", REPO])
    states = {m.number: m.state for m in roadmap_store.milestones()}
    assert (
        by_title.exit_code,
        f"Successfully closed milestone 'Q4 hardening' in {REPO}" in by_title.output,
        by_number.exit_code,
        states,
        missing.exit_code,
        "No milestone has the title or number 'Q4'" in " ".join(missing.output.split()),
        roadmap_store_repos,
    ) == (
        0,
        True,
        0,
        {titled.number: GitHubState.CLOSED, numbered.number: GitHubState.CLOSED},
        1,
        True,
        [REPO, REPO, REPO],
    )


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
    """devops gh labels sync reconciles labels through the gh label client; a dry run creates none."""
    from unittest.mock import MagicMock, patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    labels_file = tmp_path / "labels.yml"
    labels_file.write_text(
        "- name: type/bug\n  color: d73a4a\n  description: Defect\n", encoding="utf-8"
    )

    runner = CliRunner()
    listed = MagicMock(returncode=0, stdout="[]", stderr="")
    with patch("devops_cli.github.client.run_gh", return_value=listed) as run_gh:
        res = runner.invoke(
            app, ["labels", "sync", "--file", str(labels_file), "--dry-run", "-R", "o/r"]
        )
    assert (res.exit_code, "DRY RUN" in res.output, "1 to create" in res.output) == (0, True, True)
    # A dry run lists the labels and creates none.
    assert [call.args[0][:3] for call in run_gh.call_args_list] == [["gh", "label", "list"]]


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
    """devops gh milestones list shows an empty notice, then every milestone in the state asked
    for, by due date and then by number, whatever its title: one with no due date comes last."""
    empty = runner.invoke(milestones_app, ["list", "--repo", REPO])
    roadmap_store.seed_milestone("Someday")
    roadmap_store.seed_milestone("Q4 hardening", due_on=date(2026, 12, 1))
    roadmap_store.seed_milestone("Docs pass", due_on=date(2026, 11, 5), state=GitHubState.CLOSED)

    listed = runner.invoke(milestones_app, ["list", "--repo", REPO])
    open_only = runner.invoke(milestones_app, ["list", "--state", "open", "--repo", REPO])
    order = [listed.output.index(title) for title in ("Docs pass", "Q4 hardening", "Someday")]
    assert (
        (empty.exit_code, "No milestones found" in empty.output),
        (listed.exit_code, order == sorted(order)),
        ("Q4 hardening" in open_only.output, "Docs pass" in open_only.output),
    ) == ((0, True), (0, True), (True, False))


def test_cli_milestones_list_refuses_an_unknown_state(roadmap_store: InMemoryRoadmapStore) -> None:
    """devops gh milestones list exits 1 for a state filter that is not open, closed or all."""
    res = runner.invoke(milestones_app, ["list", "--state", "merged", "--repo", REPO])
    assert (res.exit_code, "Unsupported state 'merged'" in res.output) == (1, True)


def test_cli_milestones_list_names_a_failed_read(
    github_api: GitHubApiFake,
    github_roadmap_factory: Callable[..., RoadmapStore],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When GitHub can't be read, list exits 1 and names the read instead of finding nothing.
    The GitHub store reads the milestones through the process's session, which GitHub answers
    with a 502 through its retries: the session's unread error names the listing and the
    status (#983)."""
    from devops_cli.roadmap import store as roadmap_module

    listing = f"/repos/{REPO}/milestones?state=all&per_page=100"
    github_api.route("GET", listing, github_json({"message": "Server Error"}, status=502))
    monkeypatch.setattr(roadmap_module, "get_roadmap_store", github_roadmap_factory)
    res = runner.invoke(milestones_app, ["list", "--repo", REPO])
    with pytest.raises(GitHubUnreadError) as raised:
        github_roadmap_factory(REPO).milestones()
    assert (
        res.exit_code,
        f"GitHub gave no readable answer to GET {listing} (page 1) (HTTP 502)"
        in " ".join(res.output.split()),
        "No milestones found" in res.output,
        raised.value.details["status"],
        {url for url in github_api.requested},
    ) == (1, True, False, 502, {f"GET {API}{listing}"})


def test_cli_milestones_status(
    roadmap_store: InMemoryRoadmapStore, roadmap_store_repos: list[str]
) -> None:
    """devops gh milestones status shows a milestone's progress, and exits 1 for an unknown one."""
    roadmap_store.seed_milestone("2026-11-05")
    for state in [GitHubState.OPEN] * 2 + [GitHubState.CLOSED] * 8:
        roadmap_store.seed_issue("Work", state=state, milestone="2026-11-05")

    found = runner.invoke(milestones_app, ["status", "2026-11-05", "--repo", REPO])
    missing = runner.invoke(milestones_app, ["status", "2026-12-01", "--repo", REPO])
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
