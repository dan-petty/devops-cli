"""Test suite for GitHub Projects v2 schema, views, and task synchronization."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner, Result

import devops_cli.github.projects as projects_mod
from devops_cli.exceptions.git import (
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubScopeError,
    GitHubUnauthenticatedError,
)
from devops_cli.github.projects import (
    ProjectTemplate,
    load_project_template,
)
from tests.project_reconcile_fake import BOARD_TITLE, REPO, ProjectGitHub, card, issue, pull
from tests.roadmap_board_fake import budget_reply
from tests.support.fakes.github import GitHubApiFake, github_json, next_page
from tests.support.paths import REPO_ROOT


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
    exit_code: int, said: str, error: type[GitHubOperationError]
) -> None:
    """The scope check raises what `classify_gh_failure` makes of `gh project list`'s failure
    (#983): a missing scope, a rate limit, a refused token or gh's exit 4, each with gh's text."""
    from devops_cli.github.projects import verify_project_auth_scopes

    failed = subprocess.CompletedProcess(["gh", "project", "list"], exit_code, "", said)
    with (
        patch("devops_cli.github.projects.run_gh", return_value=failed),
        pytest.raises(GitHubOperationError) as raised,
    ):
        verify_project_auth_scopes()
    first_line = " ".join(said.splitlines()[0].split())
    assert (type(raised.value), first_line in raised.value.message) == (error, True)


def test_verify_project_auth_scopes_asks_for_the_project_scope_board_sync_needs() -> None:
    """gh names only the read scope `gh project list` was refused, but board sync creates
    boards, links, fields and views, so the advice is the `project` scope, which includes
    read:project; gh's own words stay in the details (#983)."""
    from devops_cli.github.projects import verify_project_auth_scopes

    failed = subprocess.CompletedProcess(["gh", "project", "list"], 1, "", _PROJECT_SCOPE_MISSING)
    with (
        patch("devops_cli.github.projects.run_gh", return_value=failed),
        pytest.raises(GitHubOperationError) as raised,
    ):
        verify_project_auth_scopes()
    assert (
        type(raised.value),
        "gh auth refresh -s project" in raised.value.message,
        "[read:project]" in raised.value.details["output"],
    ) == (GitHubScopeError, True, True)


def test_verify_project_auth_scopes_unrelated_error_ignored() -> None:
    """verify_project_auth_scopes does not misclassify unrelated errors containing 'project'."""
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import verify_project_auth_scopes

    # A non-zero exit with "project not found" names no class, so nothing is raised.
    mock_proc = MagicMock(
        return_value=MagicMock(
            returncode=1,
            stderr="error: project not found",
            stdout="",
        )
    )
    with patch("devops_cli.github.projects.run_gh", mock_proc):
        # Should complete without raising GitHubOperationError about scopes
        verify_project_auth_scopes()


def test_sync_dry_run_makes_no_request_and_reports_no_board() -> None:
    """A dry run calls no `run_gh` and reports no board number or count it did not read."""
    from unittest.mock import patch

    from devops_cli.github.projects import sync_remote_project

    template = load_project_template(Path(".github/project-template.json"))
    with patch("devops_cli.github.projects.run_gh", side_effect=AssertionError("ran gh")):
        res = sync_remote_project("dan-petty", "dan-petty/devops-cli", template, dry_run=True)
    assert (
        res.dry_run,
        res.project_number,
        res.fields_provisioned,
        res.reconcile,
        res.project_title,
    ) == (True, None, [], None, template.name)


def test_cli_project_link_command() -> None:
    """CLI devops gh project link invokes link_project_to_repository."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import app

    runner = CliRunner()
    with patch("devops_cli.commands.gh.link_project_to_repository", return_value=True):
        res = runner.invoke(app, ["project", "link", "1", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "Linked project #1 to dan-petty/devops-cli" in res.output


def test_map_view_layout() -> None:
    """_map_view_layout maps layout names to GraphQL enum strings."""
    from devops_cli.github.projects import _map_view_layout

    assert _map_view_layout("board") == "BOARD_LAYOUT"
    assert _map_view_layout("roadmap") == "ROADMAP_LAYOUT"
    assert _map_view_layout("table") == "TABLE_LAYOUT"
    assert _map_view_layout("unknown") == "TABLE_LAYOUT"


def test_sync_remote_project_views() -> None:
    """sync_remote_project_views identifies existing views and provisions missing ones."""
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        ProjectView,
        sync_remote_project_views,
    )

    fake_template = MagicMock()
    fake_template.views = [
        ProjectView(name="Existing View", layout="table"),
        ProjectView(name="New Board View", layout="board"),
    ]

    with (
        patch("devops_cli.github.projects.verify_project_auth_scopes"),
        patch(
            "devops_cli.github.projects.get_remote_project_views",
            return_value=(
                "PVT_123",
                2,
                [{"id": "v1", "name": "Existing View", "layout": "TABLE_LAYOUT"}],
            ),
        ),
        patch("devops_cli.github.projects._create_project_view", return_value=True) as mock_create,
    ):
        res = sync_remote_project_views("dan-petty", "devops-cli", fake_template)
        assert res["project_number"] == 2
        assert "Existing View" in res["existing"]
        assert "New Board View" in res["created"]
        mock_create.assert_called_once_with("PVT_123", "New Board View", "board")


def test_cli_views_sync_command() -> None:
    """CLI devops gh views sync invokes sync_remote_project_views."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import views_app

    runner = CliRunner()
    with patch(
        "devops_cli.commands.gh.sync_remote_project_views",
        return_value={
            "project_number": 2,
            "existing": ["Sprint Kanban"],
            "created": ["Roadmap Timeline"],
            "views": ["Sprint Kanban", "Roadmap Timeline"],
        },
    ):
        res = runner.invoke(views_app, ["sync", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "Project #2 views synchronized" in res.output
        assert "Repository Issues Views" in res.output


def test_cli_project_status_and_template_commands() -> None:
    """CLI devops gh project status and template display declarative configuration."""
    from typer.testing import CliRunner

    from devops_cli.commands.gh import project_app

    runner = CliRunner()
    res_status = runner.invoke(project_app, ["status"])
    assert res_status.exit_code == 0
    assert "GitHub Projects v2 Configuration" in res_status.output
    assert "Custom Fields" in res_status.output

    res_tpl = runner.invoke(project_app, ["template"])
    assert res_tpl.exit_code == 0
    assert "DevOps CLI" in res_tpl.output


def test_cli_project_sync_dry_run_names_no_board_number() -> None:
    """`project sync --dry-run` reads nothing, so it prints no board number and says it adds no
    card."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import project_app

    with patch("devops_cli.github.projects.run_gh", side_effect=AssertionError("ran gh")):
        res = CliRunner().invoke(project_app, ["sync", "--dry-run", "--repo", "o/r"])
    assert (res.exit_code, "No request was made" in res.output, "#" in res.output) == (
        0,
        True,
        False,
    )


def _sync_cli(fake: ProjectGitHub, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Result:
    """`devops gh project sync --repo o/r` against `fake`, which stands in for `run_gh` only,
    with a template naming the fake's board and the fields it already has."""
    import json
    from unittest.mock import patch

    from devops_cli.commands.gh import project_app

    template = tmp_path / "project-template.json"
    fields = [
        {"name": name, "type": "single_select", "options": [{"name": option}]}
        for name, option in (("Status", "New"), ("Priority", "P1-High"))
    ]
    template.write_text(json.dumps({"name": BOARD_TITLE, "fields": fields}))
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    with (
        patch("devops_cli.github.projects.run_gh", side_effect=fake.run_gh),
        patch("devops_cli.github.projects.get_github_session", return_value=fake),
    ):
        return CliRunner().invoke(
            project_app, ["sync", "--repo", REPO, "--template", str(template)]
        )


def _board_with_five_changes(
    *, fail_edits: tuple[int, ...] = (), remaining: int = 5000
) -> ProjectGitHub:
    """Five cards needing five changes, one open issue and one open pull request off the
    board."""
    cards = [card(n) for n in range(1, 6)]
    issues = [issue(n, labels=["status/in-progress"]) for n in range(1, 6)] + [issue(10)]
    return ProjectGitHub(cards, issues, [pull(11)], fail_edits=fail_edits, remaining=remaining)


def test_sync_adds_no_card_and_exits_0_when_reconcile_completes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live sync against a board missing an open issue and an open pull request links the
    board, creates no field, makes every planned change and no `item-add`: intake places
    issues, and a pull request gets no card."""
    fake = _board_with_five_changes()
    result = _sync_cli(fake, tmp_path, monkeypatch)
    text = " ".join(result.output.split())
    assert (
        result.exit_code,
        fake.adds,
        len(fake.links),
        len(fake.edits),
        "Provisioned fields: all up-to-date." in text,
        "1 open issue is not on the board (awaiting intake: devops roadmap intake)." in text,
        "Changed 5 of 5 items on project #2 (5 field changes)." in text,
    ) == (0, [], 1, 5, True, True, True)


def test_sync_reports_reconciles_stop_and_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live sync whose reconcile stops at a failed write prints reconcile's stop line and
    exits 1."""
    fake = _board_with_five_changes(fail_edits=(2,))
    result = _sync_cli(fake, tmp_path, monkeypatch)
    assert (
        result.exit_code,
        "Stopped early (the write of Status on #2 failed: GraphQL: the write failed): "
        "4 planned changes remain." in " ".join(result.output.split()),
        fake.adds,
    ) == (1, True, [])


def test_sync_whose_reconcile_does_not_start_exits_1_with_reconciles_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reconcile's refusal, here a low GraphQL budget, is sync's error too: one line, exit 1,
    no write and no warning that hides it."""
    fake = _board_with_five_changes(remaining=101)
    result = _sync_cli(fake, tmp_path, monkeypatch)
    assert (
        result.exit_code,
        "100 points left until 00:00 UTC" in " ".join(result.output.split()),
        "Traceback" in result.output,
        fake.edits,
    ) == (1, True, False, [])


def test_cli_project_link_failure() -> None:
    """CLI devops gh project link exits with code 1 when linkage fails."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import project_app

    runner = CliRunner()
    with patch("devops_cli.commands.gh.link_project_to_repository", return_value=False):
        res = runner.invoke(project_app, ["link", "99", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 1
        assert "Failed to link project #99" in res.output


def test_cli_views_list_and_spec_commands() -> None:
    """CLI devops gh views list and spec output formatted views and JSON schemas."""
    from typer.testing import CliRunner

    from devops_cli.commands.gh import views_app

    runner = CliRunner()
    res_list = runner.invoke(views_app, ["list"])
    assert res_list.exit_code == 0
    assert "Sprint Kanban" in res_list.output
    assert "Roadmap Timeline" in res_list.output

    res_spec = runner.invoke(views_app, ["spec"])
    assert res_spec.exit_code == 0
    assert "Sprint Kanban" in res_spec.output
    assert '"layout":' in res_spec.output


def test_cli_views_sync_no_project_found() -> None:
    """CLI devops gh views sync handles unlinked projects gracefully."""
    from unittest.mock import patch

    from typer.testing import CliRunner

    from devops_cli.commands.gh import views_app

    runner = CliRunner()
    with patch(
        "devops_cli.commands.gh.sync_remote_project_views",
        return_value={"project_number": None, "status": "No linked project found"},
    ):
        res = runner.invoke(views_app, ["sync", "--repo", "dan-petty/devops-cli"])
        assert res.exit_code == 0
        assert "No linked project found" in res.output
        assert "milestone%3Acurrent" in res.output
        assert "sort%3Apriority-desc" in res.output


def test_find_and_create_remote_project() -> None:
    """find_remote_project and create_remote_project interact correctly with gh CLI."""
    import json
    from unittest.mock import MagicMock, patch

    import pytest

    from devops_cli.exceptions.git import GitHubOperationError
    from devops_cli.github.projects import create_remote_project, find_remote_project

    # Subprocess error
    mock_fail = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="error"))
    with patch("devops_cli.github.projects.run_gh", mock_fail):
        assert find_remote_project("dan-petty", "My Project") is None
        with pytest.raises(GitHubOperationError):
            create_remote_project("dan-petty", "My Project")

    # Match found
    mock_success = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout=json.dumps({"projects": [{"title": "My Project", "number": 3}]}),
            stderr="",
        )
    )
    with patch("devops_cli.github.projects.run_gh", mock_success):
        matched = find_remote_project("dan-petty", "my project")
        assert matched is not None
        assert matched["number"] == 3

        # Create remote project success
        mock_create = MagicMock(
            return_value=MagicMock(
                returncode=0,
                stdout=json.dumps({"title": "New Board", "number": 4}),
                stderr="",
            )
        )
        with patch("devops_cli.github.projects.run_gh", mock_create):
            created = create_remote_project("dan-petty", "New Board")
            assert created["number"] == 4


def test_provision_remote_project_fields() -> None:
    """provision_remote_project_fields provisions missing text and single-select fields."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        ProjectField,
        ProjectFieldOption,
        provision_remote_project_fields,
    )

    existing = {"fields": [{"name": "Status"}, {"name": "Assignees"}]}
    mock_proc = MagicMock(
        side_effect=[
            MagicMock(returncode=0, stdout=json.dumps(existing), stderr=""),  # list
            MagicMock(returncode=0, stdout="{}", stderr=""),  # create Priority
            MagicMock(returncode=0, stdout="{}", stderr=""),  # create Job record
        ]
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
    with (
        patch("devops_cli.github.projects._get_authenticated_user", return_value="owner"),
        patch("devops_cli.github.projects.run_gh", mock_proc),
    ):
        provisioned = provision_remote_project_fields(2, "owner", fields)
        assert provisioned == ["Priority", "Job record"]


def test_get_remote_project_views() -> None:
    """get_remote_project_views parses GraphQL repository response."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import get_remote_project_views

    # Failure path
    mock_fail = MagicMock(return_value=MagicMock(returncode=1, stdout="", stderr="graphql err"))
    with patch("devops_cli.github.projects.run_gh", mock_fail):
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
                                "nodes": [{"id": "v_1", "name": "View 1", "layout": "TABLE_LAYOUT"}]
                            },
                        }
                    ]
                }
            }
        }
    }
    mock_ok = MagicMock(return_value=MagicMock(returncode=0, stdout=json.dumps(payload), stderr=""))
    with patch("devops_cli.github.projects.run_gh", mock_ok):
        pid, pnum, views = get_remote_project_views("dan-petty", "devops-cli")
        assert pid == "PVT_99"
        assert pnum == 5
        assert len(views) == 1
        assert views[0]["name"] == "View 1"


def test_graphql_query_and_mutation_escaping() -> None:
    """Verify get_remote_project_views, _create_project_view, and _rename_default_view safely escape quotes."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        _create_project_view,
        _rename_default_view,
        get_remote_project_views,
    )

    mock_proc = MagicMock(
        return_value=MagicMock(
            returncode=0, stdout=json.dumps({"data": {"repository": {"projectsV2": {"nodes": []}}}})
        )
    )
    with patch("devops_cli.github.projects.run_gh", mock_proc):
        # Query with quotes in owner/repo
        get_remote_project_views('owner"with"quotes', 'repo"with"quotes')
        called_cmd = mock_proc.call_args[0][0]
        query_arg = next(arg for arg in called_cmd if arg.startswith("query="))
        assert r"\"owner\"with\"quotes\"" in query_arg or r"owner\"with\"quotes" in query_arg

        # Mutation with quotes in view name
        ok_create = _create_project_view("PVT_1", 'Sprint "Special" Kanban', "BOARD")
        assert ok_create is True
        called_cmd = mock_proc.call_args[0][0]
        mutation_arg = next(arg for arg in called_cmd if arg.startswith("query="))
        assert r"Sprint \"Special\" Kanban" in mutation_arg

        ok_rename = _rename_default_view("V_1", 'Default "Renamed" View', "TABLE")
        assert ok_rename is True
        called_cmd = mock_proc.call_args[0][0]
        mutation_arg = next(arg for arg in called_cmd if arg.startswith("query="))
        assert r"Default \"Renamed\" View" in mutation_arg


def test_list_remote_projects() -> None:
    """list_remote_projects parses gh project list json."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import list_remote_projects

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
    with patch("devops_cli.github.projects.run_gh") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=json.dumps(payload))
        projects = list_remote_projects("test")
        assert len(projects) == 1
        assert projects[0]["number"] == 2
        assert projects[0]["state"] == "open"


def test_audit_remote_project_views() -> None:
    """audit_remote_project_views matches template views against remote views."""
    from unittest.mock import patch

    from devops_cli.github.projects import ProjectTemplate, ProjectView, audit_remote_project_views

    template = ProjectTemplate(
        name="Test",
        views=[
            ProjectView(name="Sprint Kanban", layout="BOARD"),
            ProjectView(name="Roadmap Timeline", layout="ROADMAP"),
        ],
    )
    remote_views = [{"name": "Sprint Kanban", "layout": "BOARD_LAYOUT"}]
    with patch(
        "devops_cli.github.projects.get_remote_project_views",
        return_value=("PVT_1", 2, remote_views),
    ):
        res = audit_remote_project_views("owner", "repo", template)
        assert res["project_number"] == 2
        assert res["compliant"] is False
        assert "Roadmap Timeline" in res["missing_views"]
        assert "Sprint Kanban" in res["matching_views"]


def test_audit_project_drift() -> None:
    """audit_project_drift produces comprehensive status check."""
    from unittest.mock import patch

    from devops_cli.github.projects import ProjectTemplate, audit_project_drift

    template = ProjectTemplate(name="Test Board", short_name="test-board", views=[])
    views_audit = {
        "project_number": 2,
        "compliant": True,
        "missing_views": [],
        "matching_views": [],
    }
    with (
        patch("devops_cli.github.projects.audit_remote_project_views", return_value=views_audit),
        patch("devops_cli.github.projects.find_remote_project", return_value={"number": 2}),
    ):
        res = audit_project_drift("owner", "repo", template)
        assert res["project_found"] is True
        assert res["project_number"] == 2
        assert res["views_compliant"] is True


_SECONDARY_RATE_LIMIT = "gh: Please retry your request again later. (HTTP 403)"


class _FailingGh:
    """The projects module's gh, failing every command with one exit status and stderr, and
    keeping each argv."""

    def __init__(self, exit_code: int, said: str) -> None:
        self.exit_code, self.said = exit_code, said
        self.argvs: list[list[str]] = []

    def __call__(self, args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.argvs.append(list(args))
        return subprocess.CompletedProcess(args, self.exit_code, "", self.said)


def _fail_every_gh_command(
    monkeypatch: pytest.MonkeyPatch, exit_code: int, said: str
) -> _FailingGh:
    """Fail every gh command of the projects module, with no login or owner cached."""
    gh = _FailingGh(exit_code, said)
    monkeypatch.setattr(projects_mod, "run_gh", gh)
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    return gh


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
    monkeypatch: pytest.MonkeyPatch,
    exit_code: int,
    said: str,
    error: type[GitHubOperationError],
    status: int | None,
) -> None:
    """`gh project list` failing on a rate limit, a missing scope, a refused token or gh's exit
    4 raises that class (#983), where the board lookup's own phrase list read all but a few rate
    limits as no board."""
    _fail_every_gh_command(monkeypatch, exit_code, said)
    with pytest.raises(GitHubOperationError) as raised:
        projects_mod._find_project_via_cli("octo-org", "Roadmap")
    assert (type(raised.value), raised.value.details.get("status")) == (error, status)


def test_the_cli_board_lookup_finds_no_board_on_a_failure_the_gh_table_names_no_class_for(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure the classifier names no class for, such as a 500, leaves the lookup with no
    board, for the caller's other lookups."""
    _fail_every_gh_command(monkeypatch, 1, "gh: Server Error (HTTP 500)")
    assert projects_mod._find_project_via_cli("octo-org", "Roadmap") is None


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
    monkeypatch: pytest.MonkeyPatch, title: str
) -> None:
    """A failed `gh api graphql` copies GitHub's partial answer, item titles included, to stdout
    and writes only `gh: <message>` to stderr. A title that reads like a rate limit, a scope or a
    refused login is GitHub's data, so the read fails as a failed read (#983)."""
    from pydantic import BaseModel

    answer = subprocess.CompletedProcess(
        ["gh", "api", "graphql"],
        1,
        _PARTIAL_GRAPHQL_ANSWER.format(title=title),
        "gh: Resource not accessible by integration",
    )
    monkeypatch.setattr(projects_mod, "run_gh", lambda args, **_: answer)
    with pytest.raises(GitHubOperationError) as raised:
        projects_mod._gh_read(["api", "graphql"], BaseModel, "board items")
    assert (type(raised.value), raised.value.message.startswith("Failed to read board items")) == (
        GitHubOperationError,
        True,
    )


def test_a_failed_board_read_raises_a_rate_limit_only_the_gh_table_names() -> None:
    """A board read that gh failed on a secondary rate limit raises it (#983); a failure the
    table does not name stays a failed read naming what was read."""
    failed = subprocess.CompletedProcess(["gh"], 1, "", _SECONDARY_RATE_LIMIT)
    other = subprocess.CompletedProcess(["gh"], 1, "", "gh: Server Error (HTTP 500)")
    limited = projects_mod._read_failure(failed, "board items", "project_items")
    unread = projects_mod._read_failure(other, "board items", "project_items")
    assert (type(limited), type(unread), "Failed to read board items" in str(unread)) == (
        GitHubRateLimitError,
        GitHubOperationError,
        True,
    )


@pytest.mark.parametrize(
    ("budget", "error"),
    [
        pytest.param(
            (0, json.dumps(budget_reply(4000)), ""), GitHubOperationError, id="points-left"
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
    monkeypatch: pytest.MonkeyPatch,
    budget: tuple[int, str, str],
    error: type[GitHubOperationError],
) -> None:
    """`gh project field-list --owner <login>` has no `@me` fallback: when gh drops its owner
    lookup's cause, the read asks GraphQL for its budget, as the roadmap store does (#983). With
    points left the read fails plainly, naming them; a spent or refused budget keeps the rate
    limit."""
    from devops_cli.roadmap.board_read import GRAPHQL_BUDGET_OPERATION

    sent: list[list[str]] = []

    def gh(args: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        sent.append(list(args))
        if GRAPHQL_BUDGET_OPERATION in " ".join(args):
            return subprocess.CompletedProcess(args, *budget)
        return subprocess.CompletedProcess(args, 1, "", "unknown owner type")

    monkeypatch.setattr(projects_mod, "run_gh", gh)
    with pytest.raises(GitHubOperationError) as raised:
        projects_mod._read_field_options("octo-org", 2)
    assert (
        type(raised.value),
        len(sent),
        "4000 points left" in raised.value.message,
    ) == (error, 2, error is GitHubOperationError)


@pytest.mark.parametrize(
    ("said", "owners"),
    [
        pytest.param("unknown owner type", ["octo-org", "@me"], id="owner-lookup"),
        pytest.param(_SECONDARY_RATE_LIMIT, ["octo-org"], id="secondary-rate-limit"),
        pytest.param("gh: Too Many Requests (HTTP 429)", ["octo-org"], id="429"),
    ],
)
def test_only_an_owner_gh_project_cannot_look_up_is_asked_for_again_as_me(
    monkeypatch: pytest.MonkeyPatch, said: str, owners: list[str]
) -> None:
    """gh project's owner lookup drops its error and writes "unknown owner type": the command is
    sent once more with `--owner @me`. A rate limit is never resent as `@me`, which would read
    the viewer's boards instead of the org's."""
    gh = _fail_every_gh_command(monkeypatch, 1, said)
    projects_mod._run_project_cli(["gh", "project", "list", "--owner", "octo-org"], "octo-org")
    assert [argv[argv.index("--owner") + 1] for argv in gh.argvs] == owners


def test_an_owner_lookup_failure_is_asked_for_as_me_at_once_through_run_gh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Through the real `run_gh`, "unknown owner type" is no rate limit to back off on (#983): the
    org's `gh project list` goes out once, then once as `--owner @me`, with no backoff wait and
    no throttle recorded."""
    import json
    import time

    from devops_cli.github import rate_limiter

    limiter = rate_limiter.get_github_rate_limiter()
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, limit=5000, reset_epoch=time.time() + 3600.0)
    monkeypatch.setattr(limiter, "min_interval", 0.01)
    monkeypatch.setattr(projects_mod, "_CURRENT_USER_CACHE", None)
    monkeypatch.setattr(projects_mod, "_PROJECT_OWNER_ARG_CACHE", {})
    boards = json.dumps({"projects": [{"title": "Roadmap", "number": 2}], "totalCount": 1})

    def gh(cmd: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        if cmd[1:3] == ["api", "user"]:
            return subprocess.CompletedProcess(cmd, 0, "octocat\n", "")
        if "octo-org" in cmd:
            return subprocess.CompletedProcess(cmd, 1, "", "unknown owner type")
        return subprocess.CompletedProcess(cmd, 0, boards, "")

    with (
        patch.object(rate_limiter, "run_subprocess", side_effect=gh) as run,
        patch("time.sleep") as sleep,
    ):
        found = projects_mod._find_project_via_cli("octo-org", "Roadmap")
    sent = [call.args[0] for call in run.call_args_list]
    waits = [recorded.args[0] for recorded in sleep.call_args_list]
    assert (
        [argv[argv.index("--owner") + 1] for argv in sent if "--owner" in argv],
        max(waits, default=0.0) < limiter.secondary_rate_wait,
        limiter.get_total_throttles(),
        (found or {}).get("number"),
    ) == (["octo-org", "@me"], True, 0, 2)


def test_find_remote_project_via_rest() -> None:
    """find_remote_project successfully finds project via REST without CLI fallback."""
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import find_remote_project

    mock_proc = MagicMock(
        return_value=MagicMock(
            returncode=0,
            stdout=json.dumps([{"title": "DevOps CLI Roadmap", "number": 2, "id": "PVT_123"}]),
            stderr="",
        )
    )
    with patch("devops_cli.github.projects.run_gh", mock_proc):
        res = find_remote_project("dan-petty", "DevOps CLI Roadmap")
        assert res is not None
        assert res["number"] == 2
        assert res["id"] == "PVT_123"


def test_resolve_project_owner_arg() -> None:
    """_resolve_project_owner_arg maps personal login to @me and leaves org unchanged."""
    from unittest.mock import patch

    import devops_cli.github.projects as projects_mod
    from devops_cli.github.projects import _resolve_project_owner_arg

    # Reset cache
    projects_mod._CURRENT_USER_CACHE = None

    # When owner is already @me
    assert _resolve_project_owner_arg("@me") == "@me"

    # When authenticated user matches owner
    with patch("devops_cli.github.projects._get_authenticated_user", return_value="alice"):
        assert _resolve_project_owner_arg("alice") == "@me"
        assert _resolve_project_owner_arg("ALICE") == "@me"
        assert _resolve_project_owner_arg("my-org") == "my-org"


def test_project_sync_sends_no_option_update_when_the_template_options_differ() -> None:
    """project sync creates missing fields only; it never replaces an existing field's options.

    The board's Status has Todo and Backlog and lacks the template's New and Blocked. A request
    that replaced the options without their ids would clear Status on every card.
    """
    import json
    from unittest.mock import MagicMock, patch

    from devops_cli.github.projects import (
        ProjectField,
        ProjectFieldOption,
        ProjectTemplate,
        sync_remote_project,
    )

    board_fields = {
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
        ]
    }
    template = ProjectTemplate(
        name="Roadmap",
        fields=[
            ProjectField(
                name="Status",
                type="single_select",
                options=[
                    ProjectFieldOption(name=name)
                    for name in ("New", "Ready", "In Progress", "In Review", "Done", "Blocked")
                ],
            )
        ],
    )
    run_gh = MagicMock(return_value=MagicMock(returncode=0, stdout=json.dumps(board_fields)))
    with (
        patch("devops_cli.github.projects.verify_project_auth_scopes"),
        patch("devops_cli.github.projects.find_remote_project", return_value={"number": 2}),
        patch("devops_cli.github.projects.link_project_to_repository", return_value=True),
        patch("devops_cli.github.projects._get_authenticated_user", return_value="someone"),
        patch("devops_cli.github.projects.run_gh", run_gh),
    ):
        result = sync_remote_project("owner", "owner/repo", template, reconcile_fields=False)
    commands = [call.args[0] for call in run_gh.call_args_list]
    assert (
        result.fields_provisioned,
        [command[1:3] for command in commands],
        any(
            "graphql" in command or "input" in call.kwargs
            for command, call in zip(commands, run_gh.call_args_list, strict=True)
        ),
    ) == ([], [["project", "field-list"]], False)


@pytest.mark.parametrize("kind", ["issues", "pulls"])
def test_the_repository_listings_are_read_from_every_linked_page(
    github_api: GitHubApiFake, kind: str
) -> None:
    """Issues and pull requests are read through the session, every linked page of them."""
    from devops_cli.github.projects import _fetch_repository_issues, _fetch_repository_prs

    second = f"/repositories/1/{kind}?state=open&per_page=100&page=2"
    github_api.route(
        "GET",
        f"/repos/owner/repo/{kind}?state=open&per_page=100",
        github_json([{"number": 1}], headers=next_page(second)),
    )
    github_api.route("GET", second, github_json([{"number": 2}]))
    read = _fetch_repository_issues if kind == "issues" else _fetch_repository_prs
    assert [item["number"] for item in read("owner/repo")] == [1, 2]


def test_a_repository_listing_page_that_is_no_list_fails_the_read(
    github_api: GitHubApiFake,
) -> None:
    """A malformed page raises, so reconcile never works from part of the issues."""
    from devops_cli.exceptions.git import GitHubUnreadError
    from devops_cli.github.projects import _fetch_repository_issues

    second = "/repositories/1/issues?state=open&per_page=100&page=2"
    github_api.route(
        "GET",
        "/repos/owner/repo/issues?state=open&per_page=100",
        github_json([{"number": 1}], headers=next_page(second)),
    )
    github_api.route("GET", second, github_json({"message": "Server Error"}))
    with pytest.raises(GitHubUnreadError, match="page 2"):
        _fetch_repository_issues("owner/repo")


@pytest.mark.parametrize(
    ("kind", "entry", "type_name"),
    [
        ("issues", 5, "int"),
        ("issues", None, "NoneType"),
        ("issues", "text", "str"),
        ("pulls", 5, "int"),
    ],
)
def test_a_repository_listing_entry_that_is_no_object_fails_the_read(
    github_api: GitHubApiFake, kind: str, entry: object, type_name: str
) -> None:
    """An entry that is not an object is a typed read failure naming its type, never a bare
    TypeError or AttributeError and never a shorter list."""
    from devops_cli.exceptions.git import GitHubUnreadError
    from devops_cli.github.projects import _fetch_repository_issues, _fetch_repository_prs

    github_api.route(
        "GET",
        f"/repos/owner/repo/{kind}?state=open&per_page=100",
        github_json([{"number": 1, "html_url": "u1"}, entry]),
    )
    read = _fetch_repository_issues if kind == "issues" else _fetch_repository_prs
    with pytest.raises(GitHubUnreadError, match=type_name):
        read("owner/repo")


def test_extract_item_fields_case_insensitive() -> None:
    """_extract_item_fields extracts custom fields regardless of casing or dict formatting."""
    from devops_cli.github.projects import _extract_item_fields

    item = {
        "Status": "Done",
        "PRIORITY": {"name": "P1-High"},
        "value": "High",
        "Effort": "Low",
        "id": "ITEM_1",
    }
    assert _extract_item_fields(item) == {
        "status": "Done",
        "priority": "P1-High",
        "value": "High",
        "effort": "Low",
        "id": "ITEM_1",
    }


def test_mutation_budget_lifecycle() -> None:
    """MutationBudget decrements remaining, tracks total_mutations, and exhausts at limit."""
    from devops_cli.github.projects import MutationBudget

    budget = MutationBudget(limit=2)
    assert (budget.limit, budget.remaining, budget.is_exhausted) == (2, 2, False)

    res1 = budget.record_mutation()
    assert (res1, budget.remaining, budget.total_mutations, budget.is_exhausted) == (
        True,
        1,
        1,
        False,
    )

    res2 = budget.record_mutation()
    assert (res2, budget.remaining, budget.total_mutations, budget.is_exhausted) == (
        True,
        0,
        2,
        True,
    )

    res3 = budget.record_mutation()
    assert (res3, budget.remaining, budget.total_mutations, budget.is_exhausted) == (
        False,
        0,
        2,
        True,
    )


def test_the_board_template_follows_adr_0001() -> None:
    """Status is New, Ready, In Progress, In Review, Done and Blocked; Category and the Milestone text field are gone (#739)."""
    from devops_cli.github.projects import load_project_template

    template = load_project_template(REPO_ROOT / ".github" / "project-template.json")
    fields = {field.name: field for field in template.fields}
    assert (
        [option.name for option in fields["Status"].options],
        {"Category", "Milestone"} & set(fields),
        [view.name for view in template.views if "Category" in view.model_dump_json()],
        [option.name for option in fields["Value"].options],
        [option.name for option in fields["Effort"].options],
    ) == (
        ["New", "Ready", "In Progress", "In Review", "Done", "Blocked"],
        set(),
        [],
        ["High", "Medium", "Low"],
        ["Low", "Medium", "High"],
    )


def test_project_view_writes_are_paced_as_writes_and_the_view_read_is_not() -> None:
    """Through the real `run_gh` with gh's process stubbed (#1125): the views query acquires as
    a read, and `createProjectV2View` and `updateProjectV2View` as writes."""
    import json
    import subprocess
    from typing import Any
    from unittest.mock import patch

    from devops_cli.github.projects import (
        _create_project_view,
        _rename_default_view,
        get_remote_project_views,
    )
    from devops_cli.github.rate_limiter import GitHubRateLimiter

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        reply: dict[str, Any] = {"data": {"repository": {"projectsV2": {"nodes": []}}}}
        return subprocess.CompletedProcess(cmd, 0, json.dumps(reply), "")

    with (
        patch("devops_cli.github.rate_limiter._burst_protected_subprocess", side_effect=gh),
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as acquire,
    ):
        get_remote_project_views("o", "r")
        written = (
            _create_project_view("PVT_1", "Sprint Kanban", "BOARD"),
            _rename_default_view("PVTV_1", "Triage", "TABLE"),
        )
    assert (written, [call.kwargs["is_mutation"] for call in acquire.call_args_list]) == (
        (True, True),
        [False, True, True],
    )


def test_project_sync_reads_the_board_a_charged_graphql_page_at_a_time() -> None:
    """Project sync reads its board with the roadmap store's paged GraphQL query, not
    `gh project item-list`, which pages unseen and reports no cost (#1125): through the real
    `run_gh` with gh's process stubbed, 150 items and one archived take two pages, each charged
    the points it reports, and the archived item neither shows nor fails the count."""
    import json
    import subprocess
    from typing import Any
    from unittest.mock import patch

    from devops_cli.github import rate_limiter
    from devops_cli.github.projects import _read_board
    from tests.roadmap_board_fake import BoardServer

    def entry(n: int, **extra: Any) -> dict[str, Any]:
        url = f"https://github.com/o/r/issues/{n}"
        content = {"type": "Issue", "number": n, "url": url, "repository": "o/r"}
        return {"id": f"PVTI_{n}", "content": content, "status": "Ready", **extra}

    items = [entry(n) for n in range(1, 151)] + [entry(151, isArchived=True)]
    server = BoardServer({"items": items, "totalCount": 150}, page_cost=2)
    sent: list[list[str]] = []

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        sent.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, json.dumps(server(cmd[1:])), "")

    limiter = rate_limiter.get_github_rate_limiter()
    for resource in ("core", "graphql"):
        limiter.update_quota(resource, remaining=5000, reset_epoch=4_102_444_800.0, limit=5000)
    before = limiter.points_charged("graphql")
    with (
        patch.object(rate_limiter, "_burst_protected_subprocess", side_effect=gh),
        patch.object(rate_limiter, "run_subprocess", side_effect=AssertionError("ran gh")),
        patch("devops_cli.github.rate_limiter.time.sleep"),
    ):
        found = _read_board("o", 2)
    assert (
        len(found),
        found["https://github.com/o/r/issues/7"]["status"],
        "https://github.com/o/r/issues/151" in found,
        [cmd[1:3] for cmd in sent],
        limiter.points_charged("graphql") - before,
    ) == (150, "Ready", False, [["api", "graphql"]] * 3, 5)
