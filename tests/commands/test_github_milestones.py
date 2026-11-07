"""Test suite for GitHub Milestones progress tracking and the milestone commands."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app as gh_app
from devops_cli.commands.gh import milestones_app
from devops_cli.exceptions.git import GitHubUnreadError
from devops_cli.github.milestones import calculate_milestone_progress
from devops_cli.roadmap.stores.store import GitHubState, Milestone, get_roadmap_store
from tests.support.fakes.github import API, GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

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


def test_cli_labels_list(gh_edge: ProcessFake) -> None:
    """devops gh labels list prints table of labels or info if empty."""
    gh_edge.answer(["gh", "label", "list"], ProcessAnswer(stdout="[]"))
    res = runner.invoke(gh_app, ["labels", "list", "-R", "o/empty"])
    assert res.exit_code == 0
    assert "No remote repository labels found" in res.output

    labels = [{"name": "type/bug", "color": "d73a4a", "description": "Bug"}]
    gh_edge.answer(["gh", "label", "list"], ProcessAnswer(stdout=json.dumps(labels)))
    res = runner.invoke(gh_app, ["labels", "list", "-R", "o/labelled"])
    assert res.exit_code == 0
    assert "type/bug" in res.output


def test_cli_labels_sync(tmp_path: Path, gh_edge: ProcessFake) -> None:
    """devops gh labels sync reconciles labels through the gh label client; a dry run creates none."""
    labels_file = tmp_path / "labels.yml"
    labels_file.write_text(
        "- name: type/bug\n  color: d73a4a\n  description: Defect\n", encoding="utf-8"
    )

    res = runner.invoke(
        gh_app, ["labels", "sync", "--file", str(labels_file), "--dry-run", "-R", "o/r"]
    )
    assert (res.exit_code, "Plan for synchronizing labels in o/r" in res.output) == (0, True)
    # A dry run makes no external request.
    assert gh_edge.calls == []


def test_cli_labels_audit(gh_edge: ProcessFake) -> None:
    """devops gh labels audit detects PRs with missing taxonomy."""
    # Compliant PRs
    compliant = [
        {
            "number": 1,
            "title": "feat: test",
            "labels": [{"name": "type/feature"}, {"name": "scope/cli"}],
        }
    ]
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=json.dumps(compliant)))
    res = runner.invoke(gh_app, ["labels", "audit", "-R", "o/compliant"])
    assert res.exit_code == 0
    assert "comply with taxonomy" in res.output

    # Non-compliant PRs
    gh_edge.answer(
        ["gh", "pr", "list"],
        ProcessAnswer(stdout=json.dumps([{"number": 2, "title": "fix: bug", "labels": []}])),
    )
    res = runner.invoke(gh_app, ["labels", "audit", "-R", "o/broken"])
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


def test_cli_milestones_list_names_a_failed_read(github_api: GitHubApiFake) -> None:
    """When GitHub can't be read, list exits 1 and names the read instead of finding nothing.
    The GitHub store reads the milestones through the process's session, which GitHub answers
    with a 502 through its retries: the session's unread error names the listing and the
    status (#983)."""
    listing = f"/repos/{REPO}/milestones?state=all&per_page=100"
    github_api.route("GET", listing, github_json({"message": "Server Error"}, status=502))
    res = runner.invoke(milestones_app, ["list", "--repo", REPO])
    with pytest.raises(GitHubUnreadError) as raised:
        get_roadmap_store(REPO).milestones()
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


def test_gh_helper_subprocess_fallbacks(gh_edge: ProcessFake) -> None:
    """The label and pull request listings read the JSON that gh prints."""
    gh_edge.answer(["gh", "label", "list"], ProcessAnswer(stdout=json.dumps([{"name": "test"}])))
    labels = runner.invoke(gh_app, ["labels", "list", "-R", "dan-petty/devops-cli"])

    prs = json.dumps([{"number": 10, "title": "feat: test", "labels": []}])
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=prs))
    audit = runner.invoke(gh_app, ["labels", "audit", "-R", "dan-petty/devops-cli"])

    assert (
        labels.exit_code,
        "test" in labels.output,
        audit.exit_code,
        "#10" in audit.output,
    ) == (0, True, 0, True)
