"""Test suite for devops gh CLI command group."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest
from fastmcp.exceptions import ToolError
from typer.testing import CliRunner, Result

from devops_cli.ai.mcp.server import gh_project_reconcile
from devops_cli.commands.gh import app, milestones_app
from devops_cli.github.projects import load_project_template
from devops_cli.roadmap.stores.store import GitHubState, ItemField
from devops_cli.telemetry.instruments import GITHUB_REQUESTS_TOTAL
from tests.support.fakes.github import GitHubApiFake, github_json, next_page
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.gh_process import answer_origin, gh_argv, mentions
from tests.support.paths import REPO_ROOT
from tests.support.project_reconcile_fake import REPO, ProjectGitHub, card, issue

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.support.fakes.clock import ClockFake
    from tests.support.fakes.otlp import FakeCollector
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

runner = CliRunner()


def _board_with_every_view() -> str:
    """`gh api graphql`'s reply for a repository that links the template's board, which has
    every view the template names."""
    template = load_project_template()
    board = {
        "id": "PVT_2",
        "number": 2,
        "title": template.name,
        "views": {"nodes": [{"name": view.name} for view in template.views]},
    }
    return json.dumps({"data": {"repository": {"projectsV2": {"nodes": [board]}}}})


def test_gh_labels_list(gh_edge: ProcessFake) -> None:
    """devops gh label list outputs label records."""
    labels = [
        {"name": "type/feature", "color": "0E8A16", "description": "Feature addition"},
        {"name": "type/bug", "color": "D73A4A", "description": "Bug fix"},
    ]
    gh_edge.answer(["gh", "label", "list"], ProcessAnswer(stdout=json.dumps(labels)))
    result = runner.invoke(app, ["label", "list"])
    assert result.exit_code == 0
    assert "type/feature" in result.output
    assert "type/bug" in result.output


def test_gh_labels_sync_dry_run(gh_edge: ProcessFake) -> None:
    """devops gh label sync --dry-run previews label reconciliations without mutations."""
    result = runner.invoke(app, ["label", "sync", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY RUN" in result.output or "dry-run" in result.output.lower() or "5" in result.output
    assert gh_argv(gh_edge) == []


def test_gh_labels_sync_exits_nonzero_when_unauthenticated(
    tmp_path: Path, gh_edge: ProcessFake
) -> None:
    """`devops gh label sync` fails when gh cannot list or create labels (#961).

    With no token and gh logged out, the label list came back empty, every create failed
    unseen, and the command still printed "Label sync complete" and exited 0.
    """
    labels_file = tmp_path / "labels.yml"
    labels_file.write_text("- name: type/bug\n  color: D73A4A\n", encoding="utf-8")
    gh_edge.answer(["gh", "label"], ProcessAnswer(returncode=1, stderr="gh auth login required"))

    result = runner.invoke(app, ["label", "sync", "-f", str(labels_file), "-R", "o/r"])

    assert (
        result.exit_code,
        "Label sync complete" in result.output,
        "gh auth login required" in result.output,
    ) == (1, False, True)


def test_gh_labels_list_asks_for_every_label(gh_edge: ProcessFake) -> None:
    """`devops gh label list` asks gh for more than its default 30 labels."""
    gh_edge.answer(["gh", "label", "list"], ProcessAnswer(stdout='[{"name": "type/bug"}]'))
    runner.invoke(app, ["label", "list", "-R", "o/r"])
    argv = gh_argv(gh_edge)[0]
    # Without --limit, gh lists 30.
    assert (int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 30) > 30


def test_gh_milestones_list(roadmap_store: InMemoryRoadmapStore) -> None:
    """devops gh milestones list prints each milestone with its number and progress rate."""
    roadmap_store.seed_milestone("Q4 hardening")
    roadmap_store.seed_issue("Done", state=GitHubState.CLOSED, milestone="Q4 hardening")

    result = runner.invoke(milestones_app, ["list", "-R", "example/repo"])
    assert (result.exit_code, "Q4 hardening" in result.output, "100.0%" in result.output) == (
        0,
        True,
        True,
    )


def test_gh_views_list() -> None:
    """devops gh views list displays all 4 standardized project views."""
    result = runner.invoke(app, ["views", "list"])
    assert result.exit_code == 0
    assert "Sprint Kanban" in result.output
    assert "Roadmap Timeline" in result.output
    assert "Triage & Quality Table" in result.output
    assert "Value vs Effort Priority Matrix" in result.output


def test_gh_views_spec() -> None:
    """devops gh views spec outputs JSON schema for GitHub Projects v2 views."""
    result = runner.invoke(app, ["views", "spec"])
    assert result.exit_code == 0
    assert "Sprint Kanban" in result.output
    assert "layout" in result.output


def _pages_status_output(gh_edge: ProcessFake, build_type: str, path: str) -> Result:
    """The result of `devops gh pages status` for a site of the build type with the source
    branch `main` at the path."""
    payload = {
        "status": "built",
        "html_url": "https://dan-petty.github.io/devops-cli/",
        "build_type": build_type,
        "source": {"branch": "main", "path": path},
        "https_enforced": True,
    }
    gh_edge.answer(
        ["gh", "api", "repos/dan-petty/devops-cli/pages"],
        ProcessAnswer(stdout=json.dumps(payload)),
    )
    return runner.invoke(app, ["pages", "status", "--repo", "dan-petty/devops-cli"])


def test_gh_pages_status(gh_edge: ProcessFake) -> None:
    """devops gh pages status outputs site deployment panel. For a workflow build it names the
    workflow and no source branch, which GitHub does not use for that build (#5212)."""
    result = _pages_status_output(gh_edge, "workflow", "/docs")
    assert result.exit_code == 0
    assert "BUILT" in result.output
    assert "https://dan-petty.github.io/devops-cli/" in result.output
    assert "Build Type: workflow" in result.output
    assert "a GitHub Actions workflow deploys the site" in result.output
    assert "Source Branch" not in result.output


def test_gh_pages_status_of_a_legacy_build_names_the_source_branch(gh_edge: ProcessFake) -> None:
    """devops gh pages status names the source branch and its path for a legacy build (#5212)."""
    result = _pages_status_output(gh_edge, "legacy", "/")
    assert result.exit_code == 0
    assert "Source Branch: main (path: /)" in result.output
    assert "Build Type: legacy" in result.output
    assert "GitHub Actions workflow" not in result.output


def test_gh_pages_builds(gh_edge: ProcessFake) -> None:
    """devops gh pages builds lists build history records."""
    builds = [
        {
            "status": "built",
            "commit": "b861fc4b957de816aec9b5a650f049efe0251381",
            "duration": 45802,
            "error": {"message": None},
            "created_at": "2026-09-09T14:25:58Z",
            "updated_at": "2026-09-09T14:26:43Z",
        }
    ]
    gh_edge.answer(mentions("pages/builds"), ProcessAnswer(stdout=json.dumps(builds)))
    result = runner.invoke(app, ["pages", "builds", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code == 0
    assert "BUILT" in result.output
    assert "b861fc4" in result.output


def test_gh_pages_verify(tmp_path: Path) -> None:
    """devops gh pages verify passes on valid configuration."""
    (tmp_path / "zensical.toml").write_text(
        '[project]\nsite_name = "My Project"\nsite_url = "https://example.github.io/test/"\n'
        'repo_url = "https://github.com/example/test"\n',
        encoding="utf-8",
    )
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "index.md").write_text("# Hello World\n", encoding="utf-8")
    result = runner.invoke(app, ["pages", "verify", "--dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "compliant" in result.output.lower()


def test_gh_issues_list(gh_edge: ProcessFake) -> None:
    """devops gh issue list outputs open issues."""
    listed = [
        {
            "number": 77,
            "title": "feat(rag): dedicated library vector tier",
            "state": "OPEN",
            "milestone": {"title": "2026-11"},
            "labels": [{"name": "type/feature"}, {"name": "scope/ai"}],
            "assignees": [{"login": "dan-petty"}],
        }
    ]
    gh_edge.answer(["gh", "issue", "list"], ProcessAnswer(stdout=json.dumps(listed)))
    result = runner.invoke(app, ["issue", "list", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code == 0
    assert "#77" in result.output
    assert "feat(rag)" in result.output


def _rest_issue(**fields: Any) -> dict[str, Any]:
    """An issue as GitHub's REST API sends it, with `fields` set over a full one."""
    return {
        "number": 9999,
        "title": "feat(github): a title that is longer than the fifty characters of a list row",
        "state": "open",
        "url": "https://api.github.com/repos/octo/repo/issues/9999",
        "html_url": "https://github.com/octo/repo/issues/9999",
        "milestone": {"title": "2026-12"},
        "labels": [{"name": "type/feature"}, {"name": "source/agent"}],
        "assignees": [{"login": "octocat"}],
        "created_at": "2026-10-27T10:00:00Z",
        "updated_at": "2026-10-28T11:30:00Z",
        "body": "First line.\n\nSecond line.",
        **fields,
    }


def test_gh_issues_view_prints_the_whole_issue(github_api: GitHubApiFake) -> None:
    """`devops gh issue view` prints the full title, each field and every line of the body."""
    github_api.route("GET", "/repos/octo/repo/issues/9999", github_json(_rest_issue()))
    result = runner.invoke(app, ["issue", "view", "9999", "-R", "octo/repo"])
    lines = result.output.splitlines()
    assert (result.exit_code, len(github_api.sent), lines[0]) == (
        0,
        1,
        f"#9999 {_rest_issue()['title']}",
    )
    assert {
        "State: open",
        "URL: https://github.com/octo/repo/issues/9999",
        "Milestone: 2026-12",
        "Labels: type/feature, source/agent",
        "Assignees: octocat",
        "Created: 2026-10-27T10:00:00Z",
        "Updated: 2026-10-28T11:30:00Z",
        "First line.",
        "Second line.",
    } <= set(lines)


def test_gh_issues_view_shows_a_dash_for_each_empty_field(github_api: GitHubApiFake) -> None:
    """An issue with no milestone, label, assignee or body prints a dash for each."""
    bare = _rest_issue(milestone=None, labels=[], assignees=[], body=None)
    github_api.route("GET", "/repos/octo/repo/issues/9999", github_json(bare))
    result = runner.invoke(app, ["issue", "view", "9999", "-R", "octo/repo"])
    lines = result.output.splitlines()
    assert (
        result.exit_code,
        {"Milestone: —", "Labels: —", "Assignees: —"} <= set(lines),
        lines[-1],
    ) == (0, True, "—")


def test_gh_issues_view_prints_markup_as_written(github_api: GitHubApiFake) -> None:
    """Rich markup in a title is text, not style."""
    github_api.route(
        "GET",
        "/repos/octo/repo/issues/9999",
        github_json(_rest_issue(title="fix [bold]x[/bold]")),
    )
    result = runner.invoke(app, ["issue", "view", "9999", "-R", "octo/repo"])
    assert (result.exit_code, "#9999 fix [bold]x[/bold]" in result.output) == (0, True)


def test_gh_issues_view_exits_1_naming_a_missing_issue(github_api: GitHubApiFake) -> None:
    """A 404 exits 1, names the repository and the number, and prints no issue."""
    github_api.route(
        "GET", "/repos/octo/repo/issues/9999", github_json({"message": "Not Found"}, status=404)
    )
    result = runner.invoke(app, ["issue", "view", "9999", "-R", "octo/repo"])
    text = _flat(result.output)
    assert (result.exit_code, "octo/repo/issues/9999" in text, "State:" in text) == (1, True, False)


def test_gh_issues_view_exits_1_naming_the_command_for_a_pull_request(
    github_api: GitHubApiFake,
) -> None:
    """A pull request number exits 1 and names `devops pr view`."""
    pull = _rest_issue(number=12, pull_request={"url": "https://example.com/pull/12"})
    github_api.route("GET", "/repos/octo/repo/issues/12", github_json(pull))
    result = runner.invoke(app, ["issue", "view", "12", "-R", "octo/repo"])
    text = _flat(result.output)
    assert (result.exit_code, "devops pr view 12" in text, "State:" in text) == (1, True, False)


def test_gh_issues_create(gh_edge: ProcessFake) -> None:
    """devops gh issue create hands the title, body, milestone and label to gh."""
    gh_edge.answer(
        ["gh", "issue", "create"],
        ProcessAnswer(stdout="https://github.com/dan-petty/devops-cli/issues/99\n"),
    )
    result = runner.invoke(
        app,
        [
            "issue",
            "create",
            "--repo",
            "dan-petty/devops-cli",
            "--title",
            "fix(cli): bug fix",
            "--body",
            "details",
            "--milestone",
            "2026-11",
            "--label",
            "type/bug",
        ],
    )
    assert result.exit_code == 0
    assert "#99" in result.output
    assert gh_argv(gh_edge) == [
        [
            "issue",
            "create",
            "--repo",
            "dan-petty/devops-cli",
            "--title",
            "fix(cli): bug fix",
            "--body",
            "details",
            "--milestone",
            "2026-11",
            "--label",
            "type/bug",
        ]
    ]


def test_gh_issues_triage_reports_the_items_and_the_candidates(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """An Item is checked for its type/* and scope/* labels, and an open issue with no
    priority/* label is reported once, as awaiting intake (#742, #2399)."""
    compliant = roadmap_store.seed_issue(
        "compliant", labels=("type/bug", "scope/cli", "priority/p2-medium")
    )
    unscoped = roadmap_store.seed_issue("unscoped", labels=("type/bug", "priority/p3-low"))
    candidate = roadmap_store.seed_issue("candidate", labels=("type/bug",))
    result = runner.invoke(app, ["issue", "triage", "--repo", "dan-petty/devops-cli"])
    output = _flat(result.output)
    assert (
        result.exit_code,
        "1 (33.3%)" in output,
        f"Missing scope/* 1 #{unscoped}" in output,
        f"Awaiting Intake 1 #{candidate}" in output,
        f"#{compliant}" in output,
        "Missing Priority" in output,
        "missing required taxonomy labels." in output,
    ) == (0, True, True, True, False, False, True)


def test_gh_issues_triage_does_not_hide_a_failed_read(
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """A rate limit on the read of the issues fails the command."""
    from devops_cli.exceptions.git import GitHubRateLimitError

    limited = GitHubRateLimitError("API rate limit exceeded")
    with patch.object(roadmap_store, "candidates", side_effect=limited):
        result = runner.invoke(app, ["issue", "triage", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code != 0


def test_gh_issues_status(roadmap_store: InMemoryRoadmapStore) -> None:
    """devops gh issue status outputs category counts."""
    roadmap_store.seed_milestone("2026-11")
    roadmap_store.seed_issue(
        "feat(rag): one",
        labels=("type/feature",),
        milestone="2026-11",
        fields={ItemField.PRIORITY: "P1-High"},
    )
    for title in ("feat(rag): two", "feat(rag): three"):
        roadmap_store.seed_issue(
            title,
            labels=("type/feature",),
            milestone="2026-11",
            fields={ItemField.PRIORITY: "P2-Medium"},
        )
    result = runner.invoke(app, ["issue", "status", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code == 0
    assert "Total Open" in result.output
    assert "2026-11" in result.output


def test_gh_project_list(gh_edge: ProcessFake) -> None:
    """devops gh project list displays remote project boards."""
    projects = [
        {
            "number": 2,
            "title": "Roadmap Board",
            "state": "open",
            "node_id": "PVT_123",
            "html_url": "https://github.com/orgs/test/projects/2",
        }
    ]
    gh_edge.answer(
        ["gh", "api", "users/test/projectsV2"], ProcessAnswer(stdout=json.dumps(projects))
    )
    result = runner.invoke(app, ["project", "list", "--owner", "test"])
    assert result.exit_code == 0
    assert "Roadmap Board" in result.output
    assert "OPEN" in result.output


def test_gh_project_audit(gh_edge: ProcessFake) -> None:
    """devops gh project audit outputs alignment results."""
    gh_edge.answer(["gh", "api", "graphql"], ProcessAnswer(stdout=_board_with_every_view()))
    result = runner.invoke(app, ["project", "audit", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code == 0
    assert "COMPLIANT" in result.output


def test_gh_views_audit(gh_edge: ProcessFake) -> None:
    """devops gh views audit displays view compliance table."""
    gh_edge.answer(["gh", "api", "graphql"], ProcessAnswer(stdout=_board_with_every_view()))
    result = runner.invoke(app, ["views", "audit", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code == 0
    assert "Project Views Compliance" in result.output


def _flat(output: str) -> str:
    """CLI output with Rich's line wrapping undone."""
    return " ".join(output.split())


def _reconcile_cli(
    fake: ProjectGitHub,
    gh_and_api: tuple[GitHubApiFake, ProcessFake],
    *args: str,
) -> Result:
    """`devops gh project reconcile -n 2 --repo o/r` against `fake`, served at the `gh` process
    edge and the GitHub session's HTTP edge."""
    api, gh = gh_and_api
    fake.install(gh, api)
    return runner.invoke(app, ["project", "reconcile", "-n", "2", "--repo", REPO, *args])


def _board_with_changes(count: int = 5) -> ProjectGitHub:
    """A board of `count` cards that each need one change, and one open issue off the board."""
    cards = [card(n) for n in range(1, count + 1)]
    return ProjectGitHub(
        cards,
        [issue(n, labels=["status/in-progress"]) for n in range(1, count + 1)] + [issue(10_000)],
    )


def _board_with_five_changes() -> ProjectGitHub:
    return _board_with_changes(5)


def test_gh_project_reconcile_plan_lists_every_change_with_what_decided_it(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    """`--plan` reads and lists the changes with their sources, makes none, and exits 0."""
    fake = _board_with_five_changes()
    result = _reconcile_cli(fake, github_api_and_gh, "--plan")
    assert (
        result.exit_code,
        "label status/in-progress" in result.output,
        "Would change 5 of 5 items on project #2 (5 field changes)." in _flat(result.output),
        "not on the board" in _flat(result.output),
        fake.edits,
    ) == (0, True, True, False, [])


def test_a_complete_live_run_prints_changed_and_exits_0(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    fake = _board_with_five_changes()
    result = _reconcile_cli(fake, github_api_and_gh)
    assert (
        result.exit_code,
        "Changed 5 of 5 items on project #2 (5 field changes)." in _flat(result.output),
        len(fake.edits),
    ) == (0, True, 5)


@pytest.mark.parametrize(
    ("changes", "fail_edits", "expected"),
    [
        pytest.param(
            27,
            (),
            "Stopped early (mutation budget of 25 reached): 2 planned changes remain.",
            id="fail_edits0",
        ),
        pytest.param(5, (2,), "4 planned changes remain.", id="fail_edits1"),
    ],
)
def test_a_run_that_stops_early_prints_the_stop_line_and_exits_1(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    changes: int,
    fail_edits: tuple[int, ...],
    expected: str,
) -> None:
    """The mutation budget or a failed write stops the run: exit 1 and the stop line."""
    fake = _board_with_changes(changes)
    fake.fail_edits = fail_edits
    result = _reconcile_cli(fake, github_api_and_gh)
    assert (result.exit_code, expected in _flat(result.output), fake.adds) == (1, True, [])


def test_a_failed_writes_error_is_printed_as_gh_wrote_it(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    """gh's error is remote text: brackets in it are printed, not read as console markup that
    would raise and lose the stop line."""
    fake = _board_with_five_changes()
    fake.fail_edits = (2,)
    fake.write_error = "boom [/bold] [red]"
    result = _reconcile_cli(fake, github_api_and_gh)
    assert (
        result.exit_code,
        "failed: boom [/bold] [red]): 4 planned changes remain." in _flat(result.output),
        result.exception is None or isinstance(result.exception, SystemExit),
    ) == (1, True, True)


def test_the_mcp_tool_returns_the_stop_line_after_the_exit_status(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    api, gh = github_api_and_gh
    _board_with_changes(27).install(gh, api)
    with pytest.raises(ToolError) as stopped:
        gh_project_reconcile(project_number=2, repo=REPO)
    message = _flat(str(stopped.value))
    assert (
        message.startswith("Command exited with status 1:"),
        "Stopped early (mutation budget of 25 reached): 2 planned changes remain." in message,
    ) == (True, True)


@pytest.mark.parametrize("mode", [["--plan"], []])
def test_reconcile_below_the_floor_does_not_start_and_exits_1(
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake], mode: list[str]
) -> None:
    fake = _board_with_five_changes()
    fake.server.remaining = 101
    result = _reconcile_cli(fake, github_api_and_gh, *mode)
    assert (
        result.exit_code,
        "100 points left until 00:00 UTC" in _flat(result.output),
        "hange" in result.output,
        fake.edits,
    ) == (1, True, False, [])


def test_reconcile_exits_1_naming_the_quota_read_when_github_cant_report_it(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    """No GraphQL entry in the ledger and `gh api rate_limit` failing: the real `run_gh` refuses
    before sending the budget query, and the command names the read and prints no plan."""
    process_fake.answer(["gh", "api", "rate_limit"], ProcessAnswer(returncode=1, stderr="HTTP 502"))
    result = runner.invoke(app, ["project", "reconcile", "-n", "2", "--repo", REPO, "--plan"])
    assert (
        result.exit_code,
        "Failed to refresh rate limits from GitHub API: HTTP 502" in _flat(result.output),
        "Would change" in result.output,
        "Changed" in result.output,
    ) == (1, True, False, False)


@pytest.mark.parametrize("how", ["flag", "environment"])
def test_reconcile_dry_run_makes_no_request(
    how: str, monkeypatch: pytest.MonkeyPatch, process_fake: ProcessFake
) -> None:
    """`--dry-run`, or the dry run the environment asks for, sends nothing, reads included, and
    lists the requests a run makes: finding the board when no number is given, the budget
    query, the board's pages and Status options, the listings and the writes."""
    args = ["project", "reconcile", "--repo", REPO, "--state", "open"]
    if how == "flag":
        args.append("--dry-run")
    else:
        monkeypatch.setenv("DEVOPS_CLI_DRY_RUN", "true")
    result = runner.invoke(app, args)
    text = _flat(result.output)
    assert (
        result.exit_code,
        process_fake.calls,
        "no request was made" in text,
        "to find the board named 'devops-cli-roadmap'" in text,
        "RoadmapBoardBudget" in text,
        "the next page of board <board>'s items" in text,
        "gh project field-list '<board>' --owner o" in text,
        "repos/o/r/issues?state=open&per_page=100" in text,
        "repos/o/r/pulls?state=open&per_page=100" in text,
        "gh project item-edit '<board>' --owner o --url '<item url>'" in text,
    ) == (0, [], True, True, True, True, True, True, True, True)


def test_dry_run_and_plan_together_are_refused() -> None:
    result = runner.invoke(app, ["project", "reconcile", "-n", "2", "--dry-run", "--plan"])
    assert (result.exit_code, "--dry-run and --plan" in result.output) == (1, True)


def _checkout(tmp_path: Path, with_template: bool = True) -> Path:
    """A fake checkout holding the repository's project template, and a subdirectory of it."""
    (tmp_path / ".git").mkdir()
    if with_template:
        template = REPO_ROOT / ".github" / "project-template.json"
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "project-template.json").write_text(template.read_text())
    subdirectory = tmp_path / "src" / "pkg"
    subdirectory.mkdir(parents=True)
    return subdirectory


def test_project_commands_resolve_the_template_from_a_subdirectory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """#1010: the template is read at the repository root, wherever the command runs."""
    monkeypatch.chdir(_checkout(tmp_path))
    sync = runner.invoke(app, ["project", "sync", "--dry-run", "--repo", REPO])
    reconcile = runner.invoke(app, ["project", "reconcile", "--dry-run", "--repo", REPO])
    assert (
        sync.exit_code,
        "board 'DevOps CLI — Enterprise Development & Release Roadmap'" in _flat(sync.output),
        reconcile.exit_code,
        "to find the board named 'devops-cli-roadmap'" in _flat(reconcile.output),
    ) == (0, True, 0, True)


def test_reconcile_with_a_project_number_does_not_load_the_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> None:
    monkeypatch.chdir(_checkout(tmp_path, with_template=False))
    fake = _board_with_five_changes()
    planned = _reconcile_cli(fake, github_api_and_gh, "--plan")
    dry_run = runner.invoke(app, ["project", "reconcile", "-n", "2", "--repo", REPO, "--dry-run"])
    assert (planned.exit_code, dry_run.exit_code) == (0, 0)


def test_a_missing_template_is_reported_in_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(_checkout(tmp_path, with_template=False))
    result = runner.invoke(app, ["project", "sync", "--dry-run", "--repo", REPO])
    assert (
        result.exit_code,
        "Project template file not found" in _flat(result.output),
        "Traceback" in result.output,
        result.exception is None or isinstance(result.exception, SystemExit),
    ) == (1, True, False, True)


def test_gh_project_reconcile_refuses_a_missing_board(gh_edge: ProcessFake) -> None:
    """Without a matching board, reconcile must not guess a board number."""
    gh_edge.answer(
        ["gh", "api", "graphql"],
        ProcessAnswer(stdout='{"data": {"repository": {"projectsV2": {"nodes": []}}}}'),
    )
    for kind in ("users", "orgs"):
        gh_edge.answer(
            ["gh", "api", f"{kind}/dan-petty/projectsV2"],
            ProcessAnswer(returncode=1, stderr="HTTP 404"),
        )
    gh_edge.answer(
        ["gh", "project", "list"], ProcessAnswer(stdout='{"projects": [], "totalCount": 0}')
    )
    result = runner.invoke(app, ["project", "reconcile", "--repo", "dan-petty/devops-cli"])
    edits = [argv for argv in gh_argv(gh_edge) if argv[:2] == ["project", "item-edit"]]
    assert (result.exit_code, edits, "--project-number" in result.output) == (1, [], True)


def test_gh_pr_threads_alias(gh_edge: ProcessFake) -> None:
    """devops gh pr threads list functions as an alias to devops pr threads list."""
    no_threads = {
        "data": {"repository": {"pullRequest": {"reviewThreads": {"nodes": [], "pageInfo": {}}}}}
    }
    gh_edge.answer(mentions("GetReviewThreads"), ProcessAnswer(stdout=json.dumps(no_threads)))
    result = runner.invoke(app, ["pr", "threads", "list", "83", "--repo", "dan-petty/devops-cli"])
    assert result.exit_code == 0
    assert "No review threads found" in result.output


def test_gh_rate_limit_table(process_fake: ProcessFake) -> None:
    """devops gh rate-limit starts one gh child and displays formatted rate limit table."""
    reset = int(time.time()) + 10
    mock_payload = {
        "resources": {
            "core": {"limit": 5000, "used": 10, "remaining": 4990, "reset": reset},
            "graphql": {"limit": 5000, "used": 1000, "remaining": 4000, "reset": reset},
            "search": {"limit": 30, "used": 2, "remaining": 28, "reset": reset},
            "code_scanning_autofix": {"limit": 10, "used": 1, "remaining": 9, "reset": reset},
        }
    }
    process_fake.answer(["gh", "api", "rate_limit"], ProcessAnswer(stdout=json.dumps(mock_payload)))
    result = runner.invoke(app, ["rate-limit"])
    assert result.exit_code == 0
    assert [call.argv for call in process_fake.calls] == [("gh", "api", "rate_limit")]
    assert "GitHub API Rate Limits" in result.output
    for res_name in mock_payload["resources"]:
        assert res_name in result.output
    assert "Rate Limiter Activity" in result.output


def test_gh_runs_list(gh_edge: ProcessFake) -> None:
    """devops gh run list renders recent workflow runs table."""
    mock_runs = json.dumps(
        [
            {
                "databaseId": 12345678,
                "name": "CI Quality Gate",
                "status": "completed",
                "conclusion": "success",
                "headBranch": "feat/181",
                "event": "push",
                "url": "https://example.com/org/repo/actions/runs/12345678",
            }
        ]
    )
    answer_origin(gh_edge, "owner/repo")
    gh_edge.answer(["gh", "run", "list"], ProcessAnswer(stdout=mock_runs))
    result = runner.invoke(app, ["run", "list"])
    assert result.exit_code == 0
    assert "CI Quality Gate" in result.output
    assert "12345678" in result.output


def test_gh_runs_view_failed_logs(gh_edge: ProcessFake) -> None:
    """devops gh run view with --log-failed fetches failed workflow logs."""
    answer_origin(gh_edge, "owner/repo")
    gh_edge.answer(
        ["gh", "run", "view"], ProcessAnswer(stdout="Error: Step failed with exit code 1")
    )
    result = runner.invoke(app, ["run", "view", "12345678", "--log-failed"])
    assert result.exit_code == 0
    assert "Step failed" in result.output
    args = gh_argv(gh_edge)[0]
    assert "run" in args
    assert "view" in args
    assert "12345678" in args
    assert "--log-failed" in args


def test_gh_issues_edit_success(gh_edge: ProcessFake) -> None:
    """devops gh issue edit patches issue title, body, and state via stdin."""
    answer_origin(gh_edge, "owner/repo")
    result = runner.invoke(
        app,
        [
            "issue",
            "edit",
            "185",
            "--title",
            "Updated Title",
            "--body",
            "Updated Body",
            "--state",
            "closed",
        ],
    )
    assert result.exit_code == 0
    assert "updated successfully" in result.output
    patch_call = next(call for call in gh_edge.calls if "PATCH" in call.argv)
    assert "PATCH" in patch_call.argv
    assert any("issues/185" in c for c in patch_call.argv)
    assert "--input" in patch_call.argv
    payload = json.loads(patch_call.stdin)
    assert payload["title"] == "Updated Title"
    assert payload["body"] == "Updated Body"
    assert payload["state"] == "closed"


def test_gh_issues_edit_error_masked(gh_edge: ProcessFake) -> None:
    """devops gh issue edit masks secret tokens in error output."""
    answer_origin(gh_edge, "owner/repo")
    gh_edge.answer(
        ["gh", "api", "--method", "PATCH"],
        ProcessAnswer(
            returncode=1,
            stderr="HTTP 401: Bad credentials token ghp_secrettoken1234567890abcdefghijklmn",
        ),
    )
    result = runner.invoke(app, ["issue", "edit", "185", "--title", "New Title"])
    assert result.exit_code == 1
    assert "ghp_secrettoken" not in result.output


def test_gh_issues_edit_no_changes(gh_edge: ProcessFake) -> None:
    """devops gh issue edit warns when no changes are specified."""
    answer_origin(gh_edge, "owner/repo")
    result = runner.invoke(app, ["issue", "edit", "185"])
    assert result.exit_code == 0
    assert "No changes specified" in result.output


def test_gh_rate_limit_error_masked(process_fake: ProcessFake, clock: ClockFake) -> None:
    """devops gh rate-limit masks secrets on error."""
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(returncode=1, stderr="Error ghp_secrettoken1234567890abcdefghijklmn"),
    )
    result = runner.invoke(app, ["rate-limit"])
    assert result.exit_code == 1
    assert "ghp_secrettoken" not in result.output


def test_gh_runs_list_error_masked(gh_edge: ProcessFake) -> None:
    """devops gh run list masks secrets on error."""
    answer_origin(gh_edge, "owner/repo")
    gh_edge.answer(
        ["gh", "run", "list"],
        ProcessAnswer(returncode=1, stderr="Error ghp_secrettoken1234567890abcdefghijklmn"),
    )
    result = runner.invoke(app, ["run", "list"])
    assert result.exit_code == 1
    assert "ghp_secrettoken" not in result.output


def test_gh_runs_view_error_masked(gh_edge: ProcessFake) -> None:
    """devops gh run view masks secrets on error."""
    answer_origin(gh_edge, "owner/repo")
    gh_edge.answer(
        ["gh", "run", "view"],
        ProcessAnswer(returncode=1, stderr="Error ghp_secrettoken1234567890abcdefghijklmn"),
    )
    result = runner.invoke(app, ["run", "view", "123456"])
    assert result.exit_code == 1
    assert "ghp_secrettoken" not in result.output


def test_a_run_log_is_masked_before_the_run_view_helper_returns_it() -> None:
    """The helper masks the output of a successful `gh run view` itself, so a caller that prints
    the text without the console's own masking leaks no secret (#1883). The runner it is given
    receives the run-log timeout."""
    from devops_cli.config.defaults import DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS
    from devops_cli.github.run_view import RunViewResult, fetch_workflow_run_view

    asked: list[tuple[list[str], dict[str, object]]] = []

    def runner(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        asked.append((cmd, kwargs))
        return subprocess.CompletedProcess(
            cmd, 0, stdout="Job log ghp_secrettoken1234567890abcdefghijklmn\n", stderr=""
        )

    result = fetch_workflow_run_view(123, job="456", runner=runner)
    assert result == RunViewResult(0, "Job log <masked-github-token>\n", "")
    assert asked == [
        (
            ["run", "view", "123", "--job", "456"],
            {"check": False, "timeout": DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS},
        )
    ]


def test_gh_runs_view_prints_a_run_log_masked_and_gives_gh_the_run_log_timeout(
    gh_edge: ProcessFake,
) -> None:
    """`devops gh run view` prints the log of a successful run with a secret masked, and gives
    gh the run-log timeout, which is longer than the timeout of one request (#1883)."""
    from devops_cli.config.defaults import DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS

    gh_edge.answer(
        ["gh", "run", "view"],
        ProcessAnswer(stdout="Job log ghp_secrettoken1234567890abcdefghijklmn\n"),
    )
    result = runner.invoke(app, ["run", "view", "123456", "--log", "--repo", "owner/repo"])
    view = next(call for call in gh_edge.calls if call.argv[1:3] == ("run", "view"))
    assert (result.exit_code, result.output, view.timeout) == (
        0,
        "Job log <masked-github-token>\n",
        DEFAULT_GH_RUN_LOG_TIMEOUT_SECONDS,
    )


def test_gh_rate_limit_json(process_fake: ProcessFake) -> None:
    """devops gh rate-limit --format json starts one gh child and outputs valid json."""
    reset = int(time.time()) + 10
    mock_payload = {
        "resources": {
            "core": {"limit": 5000, "used": 1, "remaining": 4999, "reset": reset},
            "graphql": {"limit": 5000, "used": 10, "remaining": 4990, "reset": reset},
            "code_scanning_autofix": {"limit": 10, "used": 1, "remaining": 9, "reset": reset},
        }
    }
    process_fake.answer(["gh", "api", "rate_limit"], ProcessAnswer(stdout=json.dumps(mock_payload)))
    result = runner.invoke(app, ["rate-limit", "--format", "json"])
    assert result.exit_code == 0
    assert [call.argv for call in process_fake.calls] == [("gh", "api", "rate_limit")]
    parsed = json.loads(result.output)
    assert set(parsed["resources"].keys()) == set(mock_payload["resources"].keys())
    assert "total_throttles" in parsed
    assert "total_wait_seconds" in parsed


def test_gh_rate_limit_invalid_format(gh_edge: ProcessFake) -> None:
    """devops gh rate-limit --format invalid exits with error."""
    result = runner.invoke(app, ["rate-limit", "--format", "xml"])
    assert result.exit_code == 1
    assert "Unsupported format" in result.output


def test_gh_runs_list_json(gh_edge: ProcessFake) -> None:
    """devops gh run list --format json outputs serialized json list."""
    mock_runs = json.dumps([{"databaseId": 1234, "name": "CI", "status": "completed"}])
    answer_origin(gh_edge, "owner/repo")
    gh_edge.answer(["gh", "run", "list"], ProcessAnswer(stdout=mock_runs))
    result = runner.invoke(app, ["run", "list", "--format", "json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert len(parsed) == 1
    assert parsed[0]["databaseId"] == 1234


def test_gh_runs_list_options(gh_edge: ProcessFake) -> None:
    """devops gh run list forwards branch and repo flags."""
    gh_edge.answer(["gh", "run", "list"], ProcessAnswer(stdout="[]"))
    result = runner.invoke(app, ["run", "list", "--branch", "feat/test", "--repo", "custom/repo"])
    assert result.exit_code == 0
    cmd = gh_argv(gh_edge)[0]
    assert "--branch" in cmd
    assert "feat/test" in cmd
    assert "--repo" in cmd
    assert "custom/repo" in cmd


def test_gh_runs_view_full_log_and_job(gh_edge: ProcessFake) -> None:
    """devops gh run view forwards --log, --job, and --repo."""
    gh_edge.answer(["gh", "run", "view"], ProcessAnswer(stdout="Job log content\n"))
    result = runner.invoke(
        app, ["run", "view", "999", "--log", "--job", "build", "--repo", "custom/repo"]
    )
    assert result.exit_code == 0
    assert "Job log content" in result.output
    cmd = gh_argv(gh_edge)[0]
    assert "--log" in cmd
    assert "--job" in cmd
    assert "build" in cmd
    assert "--repo" in cmd
    assert "custom/repo" in cmd


def test_gh_api_basic(gh_edge: ProcessFake) -> None:
    """devops gh api executes request and outputs result."""
    gh_edge.answer(
        ["gh", "api", "repos/test/repo"], ProcessAnswer(stdout='{"name": "test-repo"}\n')
    )
    result = runner.invoke(app, ["api", "repos/test/repo"])
    assert result.exit_code == 0
    assert "test-repo" in result.output
    assert gh_argv(gh_edge) == [["api", "repos/test/repo"]]


def test_gh_api_masks_a_token_of_a_json_reply_and_keeps_the_reply_valid_json(
    gh_edge: ProcessFake,
) -> None:
    """The contents reply of a private repository has a `download_url` with a `token=` query
    parameter. The printed reply hides the token, and a caller still parses it (#2569)."""
    url = "https://raw.example.com/octo/private/main/f.txt"
    reply = json.dumps({"name": "f.txt", "download_url": f"{url}?token=AGJ4EXAMPLE1234567890"})
    gh_edge.answer(
        ["gh", "api", "repos/octo/private/contents/f.txt"], ProcessAnswer(stdout=reply + "\n")
    )
    result = runner.invoke(app, ["api", "repos/octo/private/contents/f.txt"])

    assert result.exit_code == 0
    assert json.loads(result.output) == {
        "name": "f.txt",
        "download_url": f"{url}?token=<masked-token>",
    }
    assert gh_argv(gh_edge) == [["api", "repos/octo/private/contents/f.txt"]]


def test_gh_api_options_and_cache(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """devops gh api forwards HTTP method, pagination, jq, templates, and caching flags."""
    gh_edge.answer(["gh", "api"], ProcessAnswer(stdout="Filtered Output\n"))
    result = runner.invoke(
        app,
        [
            "api",
            "repos/test/repo/issues",
            "-X",
            "POST",
            "--paginate",
            "-q",
            ".title",
            "-t",
            "{{.title}}",
            "--cache",
            "--cache-ttl",
            "25.0",
            "-f",
            "title=BugReport",
        ],
    )
    assert result.exit_code == 0
    assert "Filtered Output" in result.output
    args = gh_argv(gh_edge)[0]
    assert "api" in args
    assert "-X" in args
    assert "POST" in args
    assert "--paginate" in args
    assert "-q" in args
    assert ".title" in args
    assert "-t" in args
    assert "{{.title}}" in args
    assert "-f" in args
    assert "title=BugReport" in args
    # A cached read starts gh once while the time to live lasts, and again after it.
    read = ["api", "repos/test/cached", "--cache", "--cache-ttl", "25.0"]
    runner.invoke(app, read)
    clock.shift(20)
    runner.invoke(app, read)
    reads_within_ttl = sum(1 for argv in gh_argv(gh_edge) if "repos/test/cached" in argv)
    clock.shift(10)
    runner.invoke(app, read)
    reads_after_ttl = sum(1 for argv in gh_argv(gh_edge) if "repos/test/cached" in argv)
    assert (reads_within_ttl, reads_after_ttl) == (1, 2)


def test_gh_api_hands_gh_its_paginate_and_jq_flags_unchanged(gh_edge: ProcessFake) -> None:
    """`devops gh api --paginate -q` reaches gh as typed: gh follows the `Link` pages and applies
    the filter itself, and what it prints is printed (#983)."""
    from devops_cli.config.constants import CONST_GH_CLI

    argv = ["api", "repos/:owner/:repo/issues", "--paginate", "-q", ".[].number"]
    gh_edge.answer(["gh", *argv], ProcessAnswer(stdout="1\n2\n3\n"))
    result = runner.invoke(app, argv)
    assert (result.exit_code, result.output, gh_argv(gh_edge)) == (0, "1\n2\n3\n", [argv])
    assert gh_edge.calls[-1].argv[0] == CONST_GH_CLI


_OPEN_ISSUES = "/repos/octo/repo/issues?state=open&per_page=1"


def _route_issue_pages(github_api: GitHubApiFake, pages: list[list[dict[str, Any]]]) -> None:
    """The open issues of octo/repo on linked pages, one page for each list of `pages`."""
    urls = [_OPEN_ISSUES] + [
        f"/repositories/1/issues?state=open&per_page=1&page={n}" for n in range(2, len(pages) + 1)
    ]
    for page, url, after in zip(pages, urls, [*urls[1:], None], strict=True):
        github_api.route("GET", url, github_json(page, headers=next_page(after) if after else None))


def test_gh_api_paginate_counts_each_page_it_reads(
    github_api: GitHubApiFake, otlp: FakeCollector
) -> None:
    """`devops gh api --paginate` of a REST GET reads each page through the GitHub session, so
    each of the 4 pages counts one request with its status, and the items of the pages print as
    one JSON array (#4737)."""
    _route_issue_pages(github_api, [[{"number": n}] for n in range(1, 5)])

    result = runner.invoke(app, ["api", _OPEN_ISSUES.removeprefix("/"), "--paginate"])

    assert (result.exit_code, json.loads(result.output)) == (
        0,
        [{"number": n} for n in range(1, 5)],
    )
    assert otlp.points(GITHUB_REQUESTS_TOTAL.name) == [
        (
            {"resource": "core", "method": "GET", "status": "200", "repo": "other", "row": "other"},
            4.0,
        )
    ]


def test_gh_api_paginate_runs_the_jq_filter_on_each_page(github_api: GitHubApiFake) -> None:
    """With `--jq`, the filter runs on each page, as gh runs it (#4737)."""
    _route_issue_pages(github_api, [[{"number": 1}, {"number": 2}], [{"number": 3}]])

    argv = ["api", _OPEN_ISSUES.removeprefix("/"), "--paginate", "--jq", "length, .[].number"]
    result = runner.invoke(app, argv)

    assert (result.exit_code, result.output) == (0, "2\n1\n2\n1\n3\n")


def test_gh_api_paginate_reads_pages_of_100_as_gh_does(github_api: GitHubApiFake) -> None:
    """An endpoint with no `per_page` is read in pages of 100, as gh adds `per_page=100`: 150
    labels take 2 requests, and `--jq length` prints one line for each page, as gh prints
    them (#5100)."""
    first, second = (
        "/repos/octo/repo/labels?per_page=100",
        "/repositories/1/labels?per_page=100&page=2",
    )
    labels = [{"id": n} for n in range(150)]
    github_api.route("GET", first, github_json(labels[:100], headers=next_page(second)))
    github_api.route("GET", second, github_json(labels[100:]))

    result = runner.invoke(app, ["api", "repos/octo/repo/labels", "--paginate", "--jq", "length"])

    assert (result.exit_code, result.output, github_api.requested) == (
        0,
        "100\n50\n",
        [
            "GET https://api.github.com/repos/octo/repo/labels?per_page=100",
            "GET https://api.github.com/repositories/1/labels?per_page=100&page=2",
        ],
    )


def test_gh_api_paginate_keeps_the_per_page_of_the_endpoint(github_api: GitHubApiFake) -> None:
    """An endpoint that sets `per_page` is read with its own page size only (#5100)."""
    github_api.route("GET", "/repos/octo/repo/labels?per_page=50", github_json([{"id": 1}]))

    argv = ["api", "repos/octo/repo/labels?per_page=50", "--paginate", "--jq", "length"]
    result = runner.invoke(app, argv)

    assert (result.exit_code, result.output, github_api.requested) == (
        0,
        "1\n",
        ["GET https://api.github.com/repos/octo/repo/labels?per_page=50"],
    )


def test_gh_api_paginate_dry_run_plans_pages_of_100(github_api: GitHubApiFake) -> None:
    """A dry run plans the first page with the `per_page=100` that the read sends (#5100)."""
    result = runner.invoke(app, ["api", "repos/octo/repo/labels", "--paginate", "--dry-run"])

    assert (
        result.exit_code,
        "/repos/octo/repo/labels?per_page=100" in _flat(result.output),
        github_api.sent,
    ) == (0, True, [])


def test_gh_api_paginate_exits_1_naming_a_listing_github_does_not_find(
    github_api: GitHubApiFake,
) -> None:
    """A page that GitHub answers with 404 exits 1 and names the endpoint (#4737)."""
    github_api.route("GET", _OPEN_ISSUES, github_json({"message": "Not Found"}, status=404))

    result = runner.invoke(app, ["api", _OPEN_ISSUES.removeprefix("/"), "--paginate"])

    assert (result.exit_code, "octo/repo/issues" in _flat(result.output)) == (1, True)


def test_gh_api_paginate_dry_run_plans_the_session_read(github_api: GitHubApiFake) -> None:
    """A dry run of `devops gh api --paginate` lists the GET of the first page, which repeats
    for each page, and sends no request (#4737)."""
    result = runner.invoke(app, ["api", _OPEN_ISSUES.removeprefix("/"), "--paginate", "--dry-run"])

    assert (result.exit_code, "GET" in result.output, github_api.sent) == (0, True, [])


def test_gh_api_prints_the_number_a_jq_filter_selects_from_the_rate_limit(
    process_fake: ProcessFake,
) -> None:
    """`devops gh api rate_limit --jq '.resources.graphql.remaining'` prints the number that gh
    selects and exits 0. gh runs once (#1886)."""
    from devops_cli.config.constants import CONST_GH_CLI

    process_fake.answer(["gh", "api", "rate_limit"], ProcessAnswer(stdout="4321\n"))
    jq = ".resources.graphql.remaining"
    result = runner.invoke(app, ["api", "rate_limit", "--jq", jq])
    assert (result.exit_code, result.output, [list(c.argv) for c in process_fake.calls]) == (
        0,
        "4321\n",
        [[CONST_GH_CLI, "api", "rate_limit", "-q", jq]],
    )


@pytest.mark.parametrize(
    ("flags", "timeout_default"),
    [
        pytest.param(["--paginate"], "DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS", id="paginated"),
        pytest.param([], "DEFAULT_GH_SUBPROCESS_TIMEOUT_SECONDS", id="one-page"),
    ],
)
def test_gh_api_gives_a_paginated_walk_the_listing_timeout(
    flags: list[str], timeout_default: str, gh_edge: ProcessFake
) -> None:
    """gh walks every `Link` page of a `--paginate` call in one process, so the whole walk gets
    the listing's timeout rather than one request's."""
    from devops_cli.config import defaults

    gh_edge.answer(["gh", "api", "repos/:owner/:repo/issues"], ProcessAnswer(stdout="[]\n"))
    result = runner.invoke(app, ["api", "repos/:owner/:repo/issues", *flags])
    listing = next(call for call in gh_edge.calls if "repos/:owner/:repo/issues" in call.argv)
    assert (result.exit_code, listing.timeout) == (0, getattr(defaults, timeout_default))


def test_gh_api_error_masked(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """devops gh api masks sensitive tokens on request failure."""
    gh_edge.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(
            returncode=1,
            stderr="HTTP 403: API rate limit exceeded token ghp_secretkey1234567890abcdefghijkl",
        ),
    )
    result = runner.invoke(app, ["api", "rate_limit"])
    assert result.exit_code == 1
    assert "GitHub API request failed" in result.output
    assert "ghp_secretkey" not in result.output


@pytest.mark.parametrize(
    "argv",
    [["issue", "list", "-R", "octo/repo"], ["label", "sync", "-R", "octo/repo"]],
    ids=["issues-list", "labels-sync"],
)
def test_gh_commands_report_no_identity_without_a_traceback(
    argv: list[str], tmp_path: Path, no_github_identity: None
) -> None:
    """Without a gh login, `devops gh` prints the unauthenticated error and exits 1."""
    labels = tmp_path / "labels.yml"
    labels.write_text("- name: bug\n  color: d73a4a\n", encoding="utf-8")
    extra = ["--file", str(labels)] if argv[0] == "labels" else []
    result = runner.invoke(app, [*argv, *extra])
    assert (result.exit_code, type(result.exception), "gh auth login" in result.output) == (
        1,
        SystemExit,
        True,
    )


def test_gh_issues_list_reports_a_refused_token_as_the_unauthenticated_error(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    """`gh api rate_limit` fails `HTTP 401: Bad credentials` before `gh issue list` is paced:
    the command prints the unauthenticated error, without a traceback, exits 1 and sends no
    listing (#983)."""
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=1, stderr="HTTP 401: Bad credentials")
    )
    result = runner.invoke(app, ["issue", "list", "-R", "octo/repo"])
    text = _flat(result.output)
    assert (
        result.exit_code,
        type(result.exception),
        "gh has no GitHub login that GitHub accepts (HTTP 401: Bad credentials)" in text,
        "gh auth login" in text,
        "Failed to refresh rate limits" in text,
        "Traceback" in result.output,
        [list(call.argv) for call in process_fake.calls],
    ) == (1, SystemExit, True, True, False, False, [["gh", "api", "rate_limit"]])


def test_gh_issues_list_reports_a_refresh_that_timed_out_as_the_unread_error(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    """`gh api rate_limit` runs past its timeout before `gh issue list` is paced: the command
    prints the unread error, without a traceback, exits 1 and sends no listing (#983)."""
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(side_effect=subprocess.TimeoutExpired(["gh", "api", "rate_limit"], 10.0)),
    )
    result = runner.invoke(app, ["issue", "list", "-R", "octo/repo"])
    assert (
        result.exit_code,
        type(result.exception),
        "Failed to refresh rate limits from GitHub API: gh api rate_limit timed out after 10 "
        "seconds" in _flat(result.output),
        "Traceback" in result.output,
    ) == (1, SystemExit, True, False)


def test_views_sync_prints_gh_s_scope_list_as_gh_wrote_it(gh_edge: ProcessFake) -> None:
    """gh names the missing scope as `[read:project]`, which Rich would read as a markup tag and
    drop; the warning prints gh's text as written (#983)."""
    gh_edge.answer(
        ["gh", "project", "list"],
        ProcessAnswer(
            returncode=1,
            stderr="error: your authentication token is missing required scopes [read:project]\n"
            "To request it, run:  gh auth refresh -s read:project",
        ),
    )
    result = runner.invoke(app, ["views", "sync", "-R", "octo/repo"])
    assert (result.exit_code, "[read:project]" in _flat(result.output)) == (0, True)


# The command names of gh 2.x that a `devops gh` command mirrors (#4835).
GH_NOUNS = ("issue", "pr", "run", "label", "secret", "project", "api", "status")


@pytest.mark.parametrize("noun", GH_NOUNS)
def test_a_devops_gh_command_that_mirrors_gh_has_the_gh_name(
    noun: str, cli: Callable[..., Result]
) -> None:
    """An agent types the gh name, so `devops gh <noun>` is a command for each gh noun (#4835)."""
    assert cli("gh", noun, "--help").exit_code == 0


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("issues", "issue"),
        ("runs", "run"),
        ("labels", "label"),
        ("secrets", "secret"),
        ("rate_limit", "rate-limit"),
    ],
)
def test_an_old_name_is_a_usage_error_that_names_the_new_one(
    old: str, new: str, cli: Callable[..., Result]
) -> None:
    """The old name is not an alias: it exits 2 and Click suggests the new name (#4835)."""
    result = cli("gh", old, "list")
    assert (
        result.exit_code,
        f"No such command '{old}'. Did you mean '{new}'" in _flat(result.output),
    ) == (
        2,
        True,
    )
