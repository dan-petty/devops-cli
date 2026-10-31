"""Test suite for GitHub Projects v2 schema, views, and task synchronization."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from typer.testing import Result

import devops_cli.github.projects as projects_mod
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.projects import (
    ProjectField,
    ProjectFieldOption,
    ProjectTemplate,
    ProjectView,
    audit_project_drift,
    audit_remote_project_views,
    create_project_view,
    create_remote_project,
    fetch_existing_fields_by_name,
    find_project_via_cli,
    find_project_via_repo,
    find_project_via_rest,
    find_remote_project,
    get_remote_project_views,
    gh_read,
    link_project_to_repository,
    list_projects_via_cli,
    list_remote_projects,
    load_project_template,
    map_view_layout,
    provision_remote_project_fields,
    provision_single_field,
    read_board,
    read_failure,
    read_field_options,
    rename_default_view,
    resolve_project_owner_arg,
    sync_remote_project,
    sync_remote_project_views,
    verify_project_auth_scopes,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from tests.project_board_fake import BoardServer, budget_reply
from tests.project_reconcile_fake import (
    BOARD_TITLE,
    REPO,
    ProjectGitHub,
    card,
    issue,
    pull,
)
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake, github_json, next_page
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake


@pytest.fixture(autouse=True)
def _use_process_fake(process_fake: ProcessFake, clock: ClockFake) -> ProcessFake:
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:2] == ("gh", "api")),
        ProcessAnswer(returncode=1, stderr="HTTP 404: Not Found"),
    )

    def _rate_limit_answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 3600}
        out = json.dumps({"resources": {"core": quota, "graphql": quota}})
        return subprocess.CompletedProcess(list(call.argv), 0, out, "")

    process_fake.answer(
        lambda call: bool(call.argv and list(call.argv[:3]) == ["gh", "api", "rate_limit"]),
        ProcessAnswer(side_effect=_rate_limit_answer),
    )
    return process_fake


def test_load_project_template() -> None:
    """ProjectTemplate properly parses the declarative template schema."""
    template_path = Path(".github/project-template.json")
    assert template_path.exists()

    template = load_project_template(template_path)
    assert isinstance(template, ProjectTemplate)
    assert "DevOps CLI" in template.name
    assert len(template.fields) >= 4
    assert len(template.views) == 4

    view_names = [v.name for v in template.views]
    assert "Sprint Kanban" in view_names
    assert "Roadmap Timeline" in view_names
    assert "Triage & Quality Table" in view_names
    assert "Value vs Effort Priority Matrix" in view_names


_PROJECT_SCOPE_MISSING = (
    "error: your authentication token is missing required scopes [read:project]\n"
    "To request it, run:  gh auth refresh -s read:project"
)


@pytest.mark.parametrize(
    ("exit_code", "said", "error"),
    [
        pytest.param(1, _PROJECT_SCOPE_MISSING, GitHubScopeError, id="missing-scope"),
        pytest.param(1, "gh: Too Many Requests (HTTP 429)", GitHubRateLimitError, id="429"),
        pytest.param(
            1,
            "You have exceeded a secondary rate limit. Please retry your request again later.",
            GitHubRateLimitError,
            id="secondary-rate-limit",
        ),
        pytest.param(
            1,
            "HTTP 401: Bad credentials (https://api.github.com/graphql)",
            GitHubUnauthenticatedError,
            id="401",
        ),
        pytest.param(
            1,
            "You are not logged into any GitHub hosts. To log in, run: gh auth login",
            GitHubUnauthenticatedError,
            id="not-logged-in",
        ),
        pytest.param(
            4,
            "To get started with GitHub CLI, please run:  gh auth login",
            GitHubUnauthenticatedError,
            id="exit-4",
        ),
    ],
)
def test_verify_project_auth_scopes_raises_the_class_gh_s_failure_names(
    exit_code: int,
    said: str,
    error: type[GitHubOperationError],
    process_fake: ProcessFake,
) -> None:
    """The scope check raises what `classify_gh_failure` makes of `gh project list`'s failure
    (#983): a missing scope, a rate limit, a refused token or gh's exit 4, each with gh's text."""
    process_fake.answer(["gh", "project", "list"], ProcessAnswer(returncode=exit_code, stderr=said))
    with pytest.raises(GitHubOperationError) as raised:
        verify_project_auth_scopes()
    first_line = " ".join(said.splitlines()[0].split())
    assert (type(raised.value), first_line in raised.value.message) == (error, True)


def test_verify_project_auth_scopes_asks_for_the_project_scope_board_sync_needs(
    process_fake: ProcessFake,
) -> None:
    """gh names only the read scope `gh project list` was refused, but board sync creates
    boards, links, fields and views, so the advice is the `project` scope, which includes
    read:project; gh's own words stay in the details (#983)."""
    process_fake.answer(
        ["gh", "project", "list"],
        ProcessAnswer(returncode=1, stderr=_PROJECT_SCOPE_MISSING),
    )
    with pytest.raises(GitHubOperationError) as raised:
        verify_project_auth_scopes()
    assert (
        type(raised.value),
        "gh auth refresh -s project" in raised.value.message,
        "[read:project]" in raised.value.details["output"],
    ) == (GitHubScopeError, True, True)


def test_verify_project_auth_scopes_unrelated_error_ignored(
    process_fake: ProcessFake,
) -> None:
    """verify_project_auth_scopes does not misclassify unrelated errors containing 'project'."""
    process_fake.answer(
        ["gh", "project", "list"],
        ProcessAnswer(returncode=1, stderr="error: project not found"),
    )
    assert verify_project_auth_scopes() is None


def test_sync_dry_run_makes_no_request_and_reports_no_board(
    process_fake: ProcessFake,
) -> None:
    """A dry run calls no `run_gh` and reports no board number or count it did not read."""
    template = load_project_template(Path(".github/project-template.json"))
    res = sync_remote_project("dan-petty", "dan-petty/devops-cli", template, dry_run=True)
    assert (
        res.dry_run,
        res.project_number,
        res.fields_provisioned,
        res.reconcile,
        res.project_title,
    ) == (True, None, [], None, template.name)
    assert len(process_fake.calls) == 0


def test_cli_links_project(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """CLI devops gh project link invokes link_project_to_repository."""
    process_fake.answer(
        [
            "gh",
            "project",
            "link",
            "1",
            "--owner",
            "dan-petty",
            "--repo",
            "dan-petty/devops-cli",
        ],
        ProcessAnswer(returncode=0, stdout="Linked"),
    )
    res = cli("gh", "project", "link", "1", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 0
    assert "Linked project #1 to dan-petty/devops-cli" in res.output


def testmap_view_layout() -> None:
    """map_view_layout maps layout names to GraphQL enum strings."""
    assert map_view_layout("board") == "BOARD_LAYOUT"
    assert map_view_layout("roadmap") == "ROADMAP_LAYOUT"
    assert map_view_layout("table") == "TABLE_LAYOUT"
    assert map_view_layout("unknown") == "TABLE_LAYOUT"


def test_sync_remote_project_views(process_fake: ProcessFake) -> None:
    """sync_remote_project_views identifies existing views and provisions missing ones."""
    fake_template = ProjectTemplate(
        name="Test",
        views=[
            ProjectView(name="Existing View", layout="table"),
            ProjectView(name="New Board View", layout="board"),
        ],
    )
    process_fake.answer(["gh", "project", "list"], ProcessAnswer(returncode=0, stdout="[]"))
    views_payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "id": "PVT_123",
                            "number": 2,
                            "views": {
                                "nodes": [
                                    {
                                        "id": "v1",
                                        "name": "Existing View",
                                        "layout": "TABLE_LAYOUT",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        }
    }
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(returncode=0, stdout=json.dumps(views_payload)),
    )
    res = sync_remote_project_views("dan-petty", "devops-cli", fake_template)
    assert res["project_number"] == 2
    assert "Existing View" in res["existing"]
    assert "New Board View" in res["created"]


def test_cli_syncs_views(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """CLI devops gh views sync invokes sync_remote_project_views."""
    process_fake.answer(["gh", "project", "list"], ProcessAnswer(returncode=0, stdout="[]"))
    views_payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "id": "PVT_123",
                            "number": 2,
                            "views": {
                                "nodes": [
                                    {
                                        "id": "v1",
                                        "name": "Sprint Kanban",
                                        "layout": "BOARD_LAYOUT",
                                    },
                                    {
                                        "id": "v2",
                                        "name": "Roadmap Timeline",
                                        "layout": "ROADMAP_LAYOUT",
                                    },
                                    {
                                        "id": "v3",
                                        "name": "Triage & Quality Table",
                                        "layout": "TABLE_LAYOUT",
                                    },
                                    {
                                        "id": "v4",
                                        "name": "Value vs Effort Priority Matrix",
                                        "layout": "TABLE_LAYOUT",
                                    },
                                ]
                            },
                        }
                    ]
                }
            }
        }
    }
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(returncode=0, stdout=json.dumps(views_payload)),
    )
    res = cli("gh", "views", "sync", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 0
    assert "Project #2 views synchronized" in res.output
    assert "Repository Issues Views" in res.output


def test_cli_project_status_and_template_commands(cli: Callable[..., Any]) -> None:
    """CLI devops gh project status and template display declarative configuration."""
    res_status = cli("gh", "project", "status")
    assert res_status.exit_code == 0
    assert "GitHub Projects v2 Configuration" in res_status.output
    assert "Custom Fields" in res_status.output

    res_tpl = cli("gh", "project", "template")
    assert res_tpl.exit_code == 0
    assert "DevOps CLI" in res_tpl.output


def test_cli_project_sync_dry_run_names_no_board_number(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """`project sync --dry-run` reads nothing, so it prints no board number and says it adds no
    card."""
    res = cli("gh", "project", "sync", "--dry-run", "--repo", "o/r")
    assert (res.exit_code, "No request was made" in res.output, "#" in res.output) == (
        0,
        True,
        False,
    )
    assert len(process_fake.calls) == 0


def _wire(
    fake: ProjectGitHub,
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
    state: str = "open",
    preset_quota: bool = True,
) -> None:
    limiter = get_github_rate_limiter()
    if preset_quota:
        limiter.update_quota(
            "graphql",
            remaining=fake.server.remaining,
            limit=5000,
            reset_epoch=4_102_444_800.0,
        )
    limiter.update_quota("core", remaining=5000, limit=5000, reset_epoch=4_102_444_800.0)

    def gh_side_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if "rate_limit" in call.argv:
            fresh_quota = {"limit": 5000, "remaining": 5000, "reset": 4_102_444_800.0}
            payload = json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
            return subprocess.CompletedProcess(list(call.argv), 0, stdout=payload, stderr="")
        return fake(list(call.argv))

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh"),
        ProcessAnswer(side_effect=gh_side_effect),
    )

    for s in ("open", "closed", "all"):
        issues = [item for item in fake.issues if s == "all" or item["state"] == s]
        pulls = [item for item in fake.pulls if s == "all" or item["state"] == s]
        github_api.route("GET", f"/repos/{REPO}/issues?state={s}&per_page=100", github_json(issues))
        github_api.route("GET", f"/repos/{REPO}/pulls?state={s}&per_page=100", github_json(pulls))


def _sync_cli(
    fake: ProjectGitHub,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
) -> Result:
    """`devops gh project sync --repo o/r` against `fake` wired to process_fake and github_api."""
    template = tmp_path / "project-template.json"
    fields = [
        {"name": name, "type": "single_select", "options": [{"name": option}]}
        for name, option in (("Status", "New"), ("Priority", "P1-High"))
    ]
    template.write_text(json.dumps({"name": BOARD_TITLE, "fields": fields}))
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    _wire(fake, process_fake, github_api)
    return cli("gh", "project", "sync", "--repo", REPO, "--template", str(template))


def _board_with_five_changes(
    *, fail_edits: tuple[int, ...] = (), remaining: int = 5000
) -> ProjectGitHub:
    """Five cards needing five changes, one open issue and one open pull request off the
    board."""
    cards = [card(n) for n in range(1, 6)]
    issues = [issue(n, labels=["status/in-progress"]) for n in range(1, 6)] + [issue(10)]
    return ProjectGitHub(cards, issues, [pull(11)], fail_edits=fail_edits, remaining=remaining)


def test_sync_adds_no_card_and_exits_0_when_reconcile_completes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
) -> None:
    """A live sync against a board missing an open issue and an open pull request links the
    board, creates no field, makes every planned change and no `item-add`: a person adds
    cards, and a pull request gets no card."""
    fake = _board_with_five_changes()
    result = _sync_cli(fake, tmp_path, monkeypatch, cli, process_fake, github_api)
    text = " ".join(result.output.split())
    assert (
        result.exit_code,
        fake.adds,
        len(fake.links),
        len(fake.edits),
        "Provisioned fields: all up-to-date." in text,
        "awaiting intake" in text,
        "Changed 5 of 5 items on project #2 (5 field changes)." in text,
    ) == (0, [], 1, 5, True, False, True)


def test_sync_reports_reconciles_stop_and_exits_1(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
) -> None:
    """A live sync whose reconcile stops at a failed write prints reconcile's stop line and
    exits 1."""
    fake = _board_with_five_changes(fail_edits=(2,))
    result = _sync_cli(fake, tmp_path, monkeypatch, cli, process_fake, github_api)
    assert (
        result.exit_code,
        "Stopped early (the write of Status on #2 failed: GraphQL: the write failed): "
        "4 planned changes remain." in " ".join(result.output.split()),
        fake.adds,
    ) == (1, True, [])


def test_sync_whose_reconcile_does_not_start_exits_1_with_reconciles_line(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    cli: Callable[..., Any],
    process_fake: ProcessFake,
    github_api: GitHubApiFake,
) -> None:
    """Reconcile's refusal, here a low GraphQL budget, is sync's error too: one line, exit 1,
    no write and no warning that hides it."""
    fake = _board_with_five_changes(remaining=101)
    result = _sync_cli(fake, tmp_path, monkeypatch, cli, process_fake, github_api)
    assert (
        result.exit_code,
        "100 points left until 00:00 UTC" in " ".join(result.output.split()),
        "Traceback" in result.output,
        fake.edits,
    ) == (1, True, False, [])


def test_cli_project_link_reports_error(cli: Callable[..., Any], process_fake: ProcessFake) -> None:
    """CLI devops gh project link exits with code 1 when linkage fails."""
    process_fake.answer(
        [
            "gh",
            "project",
            "link",
            "99",
            "--owner",
            "dan-petty",
            "--repo",
            "dan-petty/devops-cli",
        ],
        ProcessAnswer(returncode=1, stderr="Failed to link project"),
    )
    res = cli("gh", "project", "link", "99", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 1
    assert "Failed to link project #99" in res.output


def test_cli_views_list_and_spec_commands(cli: Callable[..., Any]) -> None:
    """CLI devops gh views list and spec output formatted views and JSON schemas."""
    res_list = cli("gh", "views", "list")
    assert res_list.exit_code == 0
    assert "Sprint Kanban" in res_list.output
    assert "Roadmap Timeline" in res_list.output

    res_spec = cli("gh", "views", "spec")
    assert res_spec.exit_code == 0
    assert "Sprint Kanban" in res_spec.output
    assert '"layout":' in res_spec.output


def test_cli_views_sync_no_project_found(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """CLI devops gh views sync handles unlinked projects gracefully."""
    process_fake.answer(["gh", "project", "list"], ProcessAnswer(returncode=0, stdout="[]"))
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"data": {"repository": {"projectsV2": {"nodes": []}}}}),
        ),
    )
    res = cli("gh", "views", "sync", "--repo", "dan-petty/devops-cli")
    assert res.exit_code == 0
    assert "No linked project found" in res.output
    assert "milestone%3Acurrent" in res.output
    assert "sort%3Apriority-desc" in res.output


def test_find_and_create_remote_project(process_fake: ProcessFake) -> None:
    """find_remote_project and create_remote_project interact correctly with gh CLI."""
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh" and "rate_limit" not in call.argv),
        ProcessAnswer(returncode=1, stderr="error"),
    )
    with pytest.raises(GitHubOperationError) as raised:
        find_remote_project("dan-petty", "My Project")
    assert raised.value.error_code == "GITHUB_UNREAD"
    with pytest.raises(GitHubOperationError) as raised:
        create_remote_project("dan-petty", "My Project")
    assert raised.value.error_code in ("GITHUB_OPERATION_FAILED", "GITHUB_UNREAD")

    # Match found
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "list")),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"projects": [{"title": "My Project", "number": 3}]}),
        ),
    )
    process_fake.answer(
        lambda call: bool(
            call.argv and call.argv[:2] == ("gh", "api") and "rate_limit" not in call.argv
        ),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps([{"title": "My Project", "number": 3}]),
        ),
    )
    matched = find_remote_project("dan-petty", "my project")
    assert matched is not None
    assert matched["number"] == 3

    # Create remote project success
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "create")),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"title": "New Board", "number": 4}),
        ),
    )
    created = create_remote_project("dan-petty", "New Board")
    assert created["number"] == 4


def test_provision_remote_project_fields(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """provision_remote_project_fields provisions missing text and single-select fields."""
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", "owner")
    existing = {"fields": [{"name": "Status"}, {"name": "Assignees"}], "totalCount": 2}
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "field-list")),
        ProcessAnswer(returncode=0, stdout=json.dumps(existing)),
    )
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "field-create")),
        ProcessAnswer(returncode=0, stdout="{}"),
    )
    fields = [
        ProjectField(name="Status", type="single_select"),
        ProjectField(
            name="Priority",
            type="single_select",
            options=[ProjectFieldOption(name="P0"), ProjectFieldOption(name="P1")],
        ),
        ProjectField(name="Job record", type="text"),
    ]
    provisioned = provision_remote_project_fields(2, "owner", fields)
    assert provisioned == ["Priority", "Job record"]


def test_get_remote_project_views(process_fake: ProcessFake) -> None:
    """get_remote_project_views parses GraphQL repository response."""
    # Failure path
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(returncode=1, stderr="graphql err"),
    )
    pid, pnum, views = get_remote_project_views("dan-petty", "devops-cli")
    assert pid is None
    assert pnum is None
    assert views == []

    # Success path
    payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "id": "PVT_99",
                            "number": 5,
                            "views": {
                                "nodes": [
                                    {
                                        "id": "v_1",
                                        "name": "View 1",
                                        "layout": "TABLE_LAYOUT",
                                    }
                                ]
                            },
                        }
                    ]
                }
            }
        }
    }
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(returncode=0, stdout=json.dumps(payload)),
    )
    pid, pnum, views = get_remote_project_views("dan-petty", "devops-cli")
    assert pid == "PVT_99"
    assert pnum == 5
    assert len(views) == 1
    assert views[0]["name"] == "View 1"


def test_graphql_query_and_mutation_escaping(process_fake: ProcessFake) -> None:
    """Verify get_remote_project_views, create_project_view, and rename_default_view safely escape quotes."""
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"data": {"repository": {"projectsV2": {"nodes": []}}}}),
        ),
    )
    get_remote_project_views('owner"with"quotes', 'repo"with"quotes')
    called_cmd = process_fake.calls[-1].argv
    query_arg = next(arg for arg in called_cmd if arg.startswith("query="))
    assert r"\"owner\"with\"quotes\"" in query_arg or r"owner\"with\"quotes" in query_arg

    ok_create = create_project_view("PVT_1", 'Sprint "Special" Kanban', "BOARD")
    assert ok_create is True
    called_cmd = process_fake.calls[-1].argv
    mutation_arg = next(arg for arg in called_cmd if arg.startswith("query="))
    assert r"Sprint \"Special\" Kanban" in mutation_arg

    ok_rename = rename_default_view("V_1", 'Default "Renamed" View', "TABLE")
    assert ok_rename is True
    called_cmd = process_fake.calls[-1].argv
    mutation_arg = next(arg for arg in called_cmd if arg.startswith("query="))
    assert r"Default \"Renamed\" View" in mutation_arg


def test_list_remote_projects(process_fake: ProcessFake) -> None:
    """list_remote_projects parses gh project list json."""
    payload = {
        "projects": [
            {
                "number": 2,
                "title": "Roadmap Board",
                "closed": False,
                "id": "PVT_123",
                "url": "https://github.com/users/test/projects/2",
            }
        ]
    }
    process_fake.answer(
        ["gh", "project", "list"],
        ProcessAnswer(returncode=0, stdout=json.dumps(payload)),
    )
    projects = list_remote_projects("test")
    assert len(projects) == 1
    assert projects[0]["number"] == 2
    assert projects[0]["state"] == "open"


def test_audit_remote_project_views(process_fake: ProcessFake) -> None:
    """audit_remote_project_views matches template views against remote views."""
    template = ProjectTemplate(
        name="Test",
        views=[
            ProjectView(name="Sprint Kanban", layout="BOARD"),
            ProjectView(name="Roadmap Timeline", layout="ROADMAP"),
        ],
    )
    views_payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "id": "PVT_1",
                            "number": 2,
                            "views": {
                                "nodes": [{"name": "Sprint Kanban", "layout": "BOARD_LAYOUT"}]
                            },
                        }
                    ]
                }
            }
        }
    }
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(returncode=0, stdout=json.dumps(views_payload)),
    )
    res = audit_remote_project_views("owner", "repo", template)
    assert res["project_number"] == 2
    assert res["compliant"] is False
    assert "Roadmap Timeline" in res["missing_views"]
    assert "Sprint Kanban" in res["matching_views"]


def test_audit_project_drift(process_fake: ProcessFake) -> None:
    """audit_project_drift produces comprehensive status check."""
    template = ProjectTemplate(name="Test Board", short_name="test-board", views=[])
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "list")),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"projects": [{"title": "Test Board", "number": 2}]}),
        ),
    )
    views_payload = {
        "data": {
            "repository": {
                "projectsV2": {
                    "nodes": [
                        {
                            "id": "PVT_1",
                            "number": 2,
                            "views": {"nodes": []},
                        }
                    ]
                }
            }
        }
    }
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(returncode=0, stdout=json.dumps(views_payload)),
    )
    res = audit_project_drift("owner", "repo", template)
    assert res["project_found"] is True
    assert res["project_number"] == 2
    assert res["views_compliant"] is True


_SECONDARY_RATE_LIMIT = "gh: Please retry your request again later. (HTTP 403)"


def _fail_every_gh_command(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    said: str,
) -> None:
    """Fail every gh command of the projects module, with no login or owner cached."""
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh" and "rate_limit" not in call.argv),
        ProcessAnswer(returncode=exit_code, stderr=said),
    )
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})


@pytest.mark.parametrize(
    ("exit_code", "said", "error", "status"),
    [
        pytest.param(1, _SECONDARY_RATE_LIMIT, GitHubRateLimitError, 403, id="secondary"),
        pytest.param(1, _PROJECT_SCOPE_MISSING, GitHubScopeError, None, id="missing-scope"),
        pytest.param(
            1,
            "HTTP 401: Bad credentials (https://api.github.com/graphql)",
            GitHubUnauthenticatedError,
            401,
            id="401",
        ),
        pytest.param(
            4,
            "To get started with GitHub CLI, please run:  gh auth login",
            GitHubUnauthenticatedError,
            None,
            id="exit-4",
        ),
    ],
)
def test_the_cli_board_lookup_raises_the_class_gh_s_failure_names(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    said: str,
    error: type[GitHubOperationError],
    status: int | None,
) -> None:
    """`gh project list` failing on a rate limit, a missing scope, a refused token or gh's exit
    4 raises that class (#983), where the board lookup's own phrase list read all but a few rate
    limits as no board."""
    _fail_every_gh_command(process_fake, monkeypatch, exit_code, said)
    with pytest.raises(GitHubOperationError) as raised:
        find_project_via_cli("octo-org", "Roadmap")
    assert (type(raised.value), raised.value.details.get("status")) == (error, status)


def test_the_cli_board_lookup_raises_unread_on_server_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure such as HTTP 500 raises GitHubUnreadError so a transient failure does not look
    like a missing board."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: Server Error (HTTP 500)")
    with pytest.raises(GitHubUnreadError) as raised:
        find_project_via_cli("octo-org", "Roadmap")
    assert raised.value.error_code == "GITHUB_UNREAD"


_PARTIAL_GRAPHQL_ANSWER = (
    '{{"data": {{"repository": {{"issues": {{"nodes": [{{"number": 705, "title": "{title}"}}]}}}}}},'
    ' "errors": [{{"type": "FORBIDDEN", "message": "Resource not accessible by integration"}}]}}'
)


@pytest.mark.parametrize(
    "title",
    [
        "correct secondary-limit backoff and retry-after handling in run_gh",
        "verify read:project scope",
        "HTTP 401 Bad credentials",
        "not logged in",
        "unknown owner type",
    ],
)
def test_a_failed_board_read_classifies_gh_s_stderr_never_the_titles_on_stdout(
    process_fake: ProcessFake, title: str
) -> None:
    """A failed `gh api graphql` copies GitHub's partial answer, item titles included, to stdout
    and writes only `gh: <message>` to stderr. A title that reads like a rate limit, a scope or a
    refused login is GitHub's data, so the read fails as a failed read (#983)."""
    from pydantic import BaseModel

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "graphql")),
        ProcessAnswer(
            returncode=1,
            stdout=_PARTIAL_GRAPHQL_ANSWER.format(title=title),
            stderr="gh: Resource not accessible by integration",
        ),
    )
    with pytest.raises(GitHubOperationError) as raised:
        gh_read(["api", "graphql"], BaseModel, "board items")
    assert (
        type(raised.value),
        raised.value.message.startswith("Failed to read board items"),
    ) == (
        GitHubOperationError,
        True,
    )


def test_a_failed_board_read_raises_a_rate_limit_only_the_gh_table_names() -> None:
    """A board read that gh failed on a secondary rate limit raises it (#983); a failure the
    table does not name stays a failed read naming what was read."""
    failed = subprocess.CompletedProcess(["gh"], 1, "", _SECONDARY_RATE_LIMIT)
    other = subprocess.CompletedProcess(["gh"], 1, "", "gh: Server Error (HTTP 500)")
    limited = read_failure(failed, "board items", "project_items")
    unread = read_failure(other, "board items", "project_items")
    assert (
        type(limited),
        type(unread),
        "Failed to read board items" in str(unread),
    ) == (
        GitHubRateLimitError,
        GitHubOperationError,
        True,
    )


@pytest.mark.parametrize(
    ("budget", "error"),
    [
        pytest.param(
            (0, json.dumps(budget_reply(4000)), ""),
            GitHubOperationError,
            id="points-left",
        ),
        pytest.param((0, json.dumps(budget_reply(0)), ""), GitHubRateLimitError, id="spent"),
        pytest.param(
            (1, "", "gh: You have exceeded a secondary rate limit. (HTTP 403)"),
            GitHubRateLimitError,
            id="budget-read-rate-limited",
        ),
    ],
)
def test_a_board_read_whose_owner_lookup_gh_drops_asks_graphql_for_its_budget(
    process_fake: ProcessFake,
    budget: tuple[int, str, str],
    error: type[GitHubOperationError],
) -> None:
    """`gh project field-list --owner <login>` has no `@me` fallback: when gh drops its owner
    lookup's cause, the read asks GraphQL for its budget (#983). With
    points left the read fails plainly, naming them; a spent or refused budget keeps the rate
    limit."""
    from devops_cli.github.project_read import GRAPHQL_BUDGET_OPERATION

    def gh_side_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        args = list(call.argv)
        if "rate_limit" in args:
            fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
            payload = json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
            return subprocess.CompletedProcess(args, 0, payload, "")
        if GRAPHQL_BUDGET_OPERATION in " ".join(args):
            return subprocess.CompletedProcess(args, *budget)
        return subprocess.CompletedProcess(args, 1, "", "unknown owner type")

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh"),
        ProcessAnswer(side_effect=gh_side_effect),
    )
    with pytest.raises(GitHubOperationError) as raised:
        read_field_options("octo-org", 2)
    commands = [c for c in process_fake.calls if "rate_limit" not in c.argv]
    expected_calls = 4 if "secondary rate limit" in budget[2] else 2
    assert (
        type(raised.value),
        len(commands),
        "4000 points left" in raised.value.message,
    ) == (error, expected_calls, error is GitHubOperationError)


@pytest.mark.parametrize(
    ("said", "owners"),
    [
        pytest.param("unknown owner type", ["octo-org", "@me"], id="owner-lookup"),
        pytest.param(_SECONDARY_RATE_LIMIT, ["octo-org"], id="secondary-rate-limit"),
        pytest.param("gh: Too Many Requests (HTTP 429)", ["octo-org"], id="429"),
    ],
)
def test_only_an_owner_gh_project_cannot_look_up_is_asked_for_again_as_me(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
    said: str,
    owners: list[str],
) -> None:
    """gh project's owner lookup drops its error and writes "unknown owner type": the command is
    sent once more with `--owner @me`. A rate limit is never resent as `@me`, which would read
    the viewer's boards instead of the org's."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, said)
    projects_mod._run_project_cli(["gh", "project", "list", "--owner", "octo-org"], "octo-org")
    commands = [list(call.argv) for call in process_fake.calls]
    seen_owners: list[str] = []
    for argv in commands:
        if "--owner" in argv:
            owner = argv[argv.index("--owner") + 1]
            if not seen_owners or seen_owners[-1] != owner:
                seen_owners.append(owner)
    assert seen_owners == owners


def test_an_owner_lookup_failure_is_asked_for_as_me_at_once_through_run_gh(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch, clock: ClockFake
) -> None:
    """Through the real `run_gh`, "unknown owner type" is no rate limit to back off on (#983): the
    org's `gh project list` goes out once, then once as `--owner @me`, with no backoff wait and
    no throttle recorded."""
    limiter = get_github_rate_limiter()
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 3600.0)
    monkeypatch.setattr(limiter, "min_interval", 0.01)
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    boards = json.dumps({"projects": [{"title": "Roadmap", "number": 2}], "totalCount": 1})

    def gh_side_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        cmd = list(call.argv)
        if "rate_limit" in cmd:
            fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
            payload = json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
            return subprocess.CompletedProcess(cmd, 0, payload, "")
        if cmd[1:3] == ["api", "user"]:
            return subprocess.CompletedProcess(cmd, 0, "octocat\n", "")
        if "octo-org" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "unknown owner type")
        return subprocess.CompletedProcess(cmd, 0, boards, "")

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh"),
        ProcessAnswer(side_effect=gh_side_effect),
    )
    found = find_project_via_cli("octo-org", "Roadmap")
    sent = [list(call.argv) for call in process_fake.calls]
    assert (
        [argv[argv.index("--owner") + 1] for argv in sent if "--owner" in argv],
        max(clock.waits, default=0.0) < limiter.secondary_rate_wait,
        limiter.get_total_throttles(),
        (found or {}).get("number"),
    ) == (["octo-org", "@me"], True, 0, 2)


def test_find_remote_project_via_rest(process_fake: ProcessFake) -> None:
    """find_remote_project successfully finds project via REST without CLI fallback."""
    payload = [{"title": "DevOps CLI Roadmap", "number": 2, "id": "PVT_123"}]
    process_fake.answer(
        lambda call: bool(
            call.argv and call.argv[:2] == ("gh", "api") and "rate_limit" not in call.argv
        ),
        ProcessAnswer(returncode=0, stdout=json.dumps(payload)),
    )
    res = find_remote_project("dan-petty", "DevOps CLI Roadmap")
    assert res is not None
    assert res["number"] == 2
    assert res["id"] == "PVT_123"


def testresolve_project_owner_arg(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """resolve_project_owner_arg maps personal login to @me and leaves org unchanged."""
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})

    assert resolve_project_owner_arg("@me") == "@me"

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "api", "user")),
        ProcessAnswer(returncode=0, stdout="alice\n"),
    )
    assert resolve_project_owner_arg("alice") == "@me"
    assert resolve_project_owner_arg("ALICE") == "@me"
    assert resolve_project_owner_arg("my-org") == "my-org"


def test_project_sync_sends_no_option_update_when_the_template_options_differ(
    process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """project sync creates missing fields only; it never replaces an existing field's options.

    The board's Status has Todo and Backlog and lacks the template's New and Blocked. A request
    that replaced the options without their ids would clear Status on every card.
    """
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", "someone")
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    board_fields = {
        "totalCount": 1,
        "fields": [
            {
                "id": "PVTSSF_status",
                "name": "Status",
                "type": "ProjectV2SingleSelectField",
                "options": [
                    {"id": option_id, "name": name}
                    for option_id, name in (
                        ("5b8424c8", "Todo"),
                        ("82b128b7", "Backlog"),
                        ("89415499", "Ready"),
                        ("1cb0cdfe", "In Progress"),
                        ("77269eb5", "In Review"),
                        ("82c424e4", "Done"),
                    )
                ],
            }
        ],
    }
    template = ProjectTemplate(
        name="Roadmap",
        fields=[
            ProjectField(
                name="Status",
                type="single_select",
                options=[
                    ProjectFieldOption(name=name)
                    for name in (
                        "New",
                        "Ready",
                        "In Progress",
                        "In Review",
                        "Done",
                        "Blocked",
                    )
                ],
            )
        ],
    )
    process_fake.answer(
        ["gh", "project", "list", "--owner", "@me"],
        ProcessAnswer(returncode=0, stdout="[]"),
    )
    process_fake.answer(
        lambda call: bool(call.argv and "--owner" in call.argv and "owner" in call.argv),
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"projects": [{"title": "Roadmap", "number": 2}]}),
        ),
    )
    process_fake.answer(["gh", "project", "link"], ProcessAnswer(returncode=0, stdout=""))
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "field-list")),
        ProcessAnswer(returncode=0, stdout=json.dumps(board_fields)),
    )
    result = sync_remote_project("owner", "owner/repo", template, reconcile_fields=False)
    commands = [list(call.argv) for call in process_fake.calls]
    assert (
        result.fields_provisioned,
        [
            command[1:3]
            for command in commands
            if len(command) > 2 and command[1:3] == ["project", "field-list"]
        ],
        any("mutation" in " ".join(command) for command in commands),
    ) == ([], [["project", "field-list"]], False)


@pytest.mark.parametrize("kind", ["issues", "pulls"])
def test_the_repository_listings_are_read_from_every_linked_page(
    github_api: GitHubApiFake, kind: str
) -> None:
    """Issues and pull requests are read through the session, every linked page of them."""
    from devops_cli.github.projects import fetch_repository_issues, fetch_repository_prs

    second = f"/repositories/1/{kind}?state=open&per_page=100&page=2"
    github_api.route(
        "GET",
        f"/repos/owner/repo/{kind}?state=open&per_page=100",
        github_json([{"number": 1}], headers=next_page(second)),
    )
    github_api.route("GET", second, github_json([{"number": 2}]))
    fetcher = fetch_repository_issues if kind == "issues" else fetch_repository_prs
    assert [item["number"] for item in fetcher("owner/repo", state="open")] == [1, 2]


@pytest.mark.parametrize(
    ("items", "message"),
    [
        pytest.param([{"number": 1}, None], "NoneType", id="none-entry"),
        pytest.param([{"number": 1}, "string"], "str", id="string-entry"),
    ],
)
def test_a_repository_listing_holding_a_non_dict_entry_fails_read(
    github_api: GitHubApiFake, items: list[object], message: str
) -> None:
    """A page whose JSON is a list but holds an element that is not an object raises GitHubUnreadError."""
    from devops_cli.github.projects import fetch_repository_issues

    github_api.route(
        "GET",
        "/repos/owner/repo/issues?state=open&per_page=100",
        github_json(items),
    )
    with pytest.raises(GitHubUnreadError) as raised:
        fetch_repository_issues("owner/repo", state="open")
    assert message in raised.value.message


def test_a_repository_listing_holding_no_list_fails_read(
    github_api: GitHubApiFake,
) -> None:
    """A page returning an object rather than a list raises GitHubUnreadError."""
    from devops_cli.github.projects import fetch_repository_issues

    github_api.route(
        "GET",
        "/repos/owner/repo/issues?state=open&per_page=100",
        github_json({"message": "Not Found"}),
    )
    with pytest.raises(GitHubUnreadError) as raised:
        fetch_repository_issues("owner/repo", state="open")
    assert "not a JSON array" in raised.value.message


def test_field_options_sorting() -> None:
    """Options preserve specified order for Priority and Status."""
    options = [
        ProjectFieldOption(name="High"),
        ProjectFieldOption(name="Medium"),
        ProjectFieldOption(name="Low"),
    ]
    f = ProjectField(name="Priority", type="single_select", options=options)
    assert [o.name for o in f.options] == ["High", "Medium", "Low"]

    options_reversed = [
        ProjectFieldOption(name="Low"),
        ProjectFieldOption(name="Medium"),
        ProjectFieldOption(name="High"),
    ]
    f2 = ProjectField(name="Custom", type="single_select", options=options_reversed)
    assert [o.name for o in f2.options] == ["Low", "Medium", "High"]


def test_project_view_writes_are_paced_as_writes_and_the_view_read_is_not(
    process_fake: ProcessFake,
) -> None:
    """Through the real `run_gh` with gh's process stubbed (#1125): the views query acquires as
    a read, and `createProjectV2View` and `updateProjectV2View` as writes."""
    reply = {"data": {"repository": {"projectsV2": {"nodes": []}}}}
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh" and "rate_limit" not in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(reply)),
    )
    limiter = get_github_rate_limiter()
    original_acquire = limiter.acquire
    acquire_calls: list[dict[str, Any]] = []

    def spy_acquire(*args: Any, **kwargs: Any) -> float:
        acquire_calls.append(kwargs)
        return 0.0

    setattr(limiter, "acquire", spy_acquire)
    try:
        get_remote_project_views("o", "r")
        written = (
            create_project_view("PVT_1", "Sprint Kanban", "BOARD"),
            rename_default_view("PVTV_1", "Triage", "TABLE"),
        )
    finally:
        setattr(limiter, "acquire", original_acquire)

    assert (written, [call["is_mutation"] for call in acquire_calls]) == (
        (True, True),
        [False, True, True],
    )


def test_project_sync_reads_the_board_a_charged_graphql_page_at_a_time(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    """Project sync reads its board with the paged GraphQL query of `project_read`..."""

    def entry(n: int, **extra: Any) -> dict[str, Any]:
        url = f"https://github.com/o/r/issues/{n}"
        content = {"type": "Issue", "number": n, "url": url, "repository": "o/r"}
        return {"id": f"PVTI_{n}", "content": content, "status": "Ready", **extra}

    items = [entry(n) for n in range(1, 151)] + [entry(151, isArchived=True)]
    server = BoardServer({"items": items, "totalCount": 150}, page_cost=2)
    sent: list[list[str]] = []

    def gh_side_effect(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        cmd = list(call.argv)
        if "rate_limit" in cmd:
            fresh_quota = {"limit": 5000, "remaining": 5000, "reset": 4_102_444_800.0}
            payload = json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}})
            return subprocess.CompletedProcess(cmd, 0, payload, "")
        sent.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, json.dumps(server(cmd[1:])), "")

    limiter = get_github_rate_limiter()
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, reset_epoch=4_102_444_800.0, limit=5000)
    before = limiter.points_charged("graphql")

    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh"),
        ProcessAnswer(side_effect=gh_side_effect),
    )
    found = read_board("o", 2)
    assert (
        len(found),
        found["https://github.com/o/r/issues/7"]["status"],
        "https://github.com/o/r/issues/151" in found,
        [cmd[1:3] for cmd in sent],
        limiter.points_charged("graphql") - before,
    ) == (150, "Ready", False, [["api", "graphql"]] * 3, 5)


def test_fetch_existing_fields_fails_closed_on_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_existing_fields_by_name raises on failed gh command or malformed output."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: Server Error (HTTP 500)")
    with pytest.raises(GitHubOperationError) as raised:
        fetch_existing_fields_by_name("owner", 2)
    assert raised.value.error_code == "GITHUB_OPERATION_FAILED"


def test_fetch_existing_fields_fails_closed_on_missing_scope(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_existing_fields_by_name raises GitHubScopeError when token lacks scope."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, _PROJECT_SCOPE_MISSING)
    with pytest.raises(GitHubScopeError) as raised:
        fetch_existing_fields_by_name("owner", 2)
    assert raised.value.error_code == "GITHUB_SCOPE_MISSING"


def test_fetch_existing_fields_fails_closed_on_empty_output(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_existing_fields_by_name raises GitHubUnreadError on empty output."""
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "field-list")),
        ProcessAnswer(returncode=0, stdout="", stderr=""),
    )
    with pytest.raises(GitHubOperationError) as raised:
        fetch_existing_fields_by_name("owner", 2)
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_fetch_existing_fields_fails_closed_on_incomplete_listing(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fetch_existing_fields_by_name raises when field count is less than totalCount."""
    payload = {"fields": [{"id": "f1", "name": "Status"}], "totalCount": 2}
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[:3] == ("gh", "project", "field-list")),
        ProcessAnswer(returncode=0, stdout=json.dumps(payload), stderr=""),
    )
    with pytest.raises(GitHubOperationError, match="incomplete"):
        fetch_existing_fields_by_name("owner", 2)


def test_provision_single_field_raises_on_missing_scope(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provision_single_field raises GitHubScopeError when token lacks project scope."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, _PROJECT_SCOPE_MISSING)
    field = ProjectField(name="TestField", type="text")
    with pytest.raises(GitHubScopeError) as raised:
        provision_single_field("owner", 2, field)
    assert raised.value.error_code == "GITHUB_SCOPE_MISSING"


def test_provision_single_field_raises_on_unclassified_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """provision_single_field raises GitHubOperationError on non-zero exit."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: unclassified field error")
    field = ProjectField(name="TestField", type="text")
    with pytest.raises(GitHubOperationError) as raised:
        provision_single_field("owner", 2, field)
    assert raised.value.error_code == "GITHUB_OPERATION_FAILED"


def test_link_project_to_repository_raises_on_missing_scope(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """link_project_to_repository raises GitHubScopeError when token lacks project scope."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, _PROJECT_SCOPE_MISSING)
    with pytest.raises(GitHubScopeError) as raised:
        link_project_to_repository(2, "owner", "repo")
    assert raised.value.error_code == "GITHUB_SCOPE_MISSING"


def test_link_project_to_repository_raises_on_unclassified_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """link_project_to_repository raises GitHubOperationError on non-zero exit."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: link failure")
    with pytest.raises(GitHubOperationError) as raised:
        link_project_to_repository(2, "owner", "repo")
    assert raised.value.error_code == "GITHUB_OPERATION_FAILED"


def test_create_remote_project_raises_on_missing_scope(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_remote_project raises GitHubScopeError when token lacks project scope."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, _PROJECT_SCOPE_MISSING)
    with pytest.raises(GitHubScopeError) as raised:
        create_remote_project("owner", "Board Title")
    assert raised.value.error_code == "GITHUB_SCOPE_MISSING"


def test_find_project_via_repo_raises_on_server_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """find_project_via_repo raises GitHubUnreadError on server error."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: Server Error (HTTP 500)")
    with pytest.raises(GitHubUnreadError) as raised:
        find_project_via_repo("owner", "repo", "Roadmap")
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_find_project_via_repo_raises_on_empty_output(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """find_project_via_repo raises GitHubUnreadError on empty output."""
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    process_fake.answer(
        lambda call: bool(call.argv and call.argv[0] == "gh" and "rate_limit" not in call.argv),
        ProcessAnswer(returncode=0, stdout="", stderr=""),
    )
    with pytest.raises(GitHubUnreadError) as raised:
        find_project_via_repo("owner", "repo", "Roadmap")
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_find_project_via_rest_raises_on_server_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """find_project_via_rest raises GitHubUnreadError on server error."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: Server Error (HTTP 500)")
    with pytest.raises(GitHubUnreadError) as raised:
        find_project_via_rest("owner", "Roadmap")
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_list_projects_via_cli_raises_on_server_error(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """list_projects_via_cli raises GitHubUnreadError on server error."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, "gh: Server Error (HTTP 500)")
    with pytest.raises(GitHubUnreadError) as raised:
        list_projects_via_cli("owner")
    assert raised.value.error_code == "GITHUB_UNREAD"


def test_list_projects_via_cli_raises_on_missing_scope(
    process_fake: ProcessFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """list_projects_via_cli raises GitHubScopeError on missing scope."""
    _fail_every_gh_command(process_fake, monkeypatch, 1, _PROJECT_SCOPE_MISSING)
    with pytest.raises(GitHubScopeError) as raised:
        list_projects_via_cli("owner")
    assert raised.value.error_code == "GITHUB_SCOPE_MISSING"
