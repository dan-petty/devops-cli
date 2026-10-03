"""Test suite for devops gh CLI command group."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app, milestones_app
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState

runner = CliRunner()


def test_gh_labels_list() -> None:
    """devops gh labels list outputs label records."""
    mock_labels = [
        {"name": "type/feature", "color": "0E8A16", "description": "Feature addition"},
        {"name": "type/bug", "color": "D73A4A", "description": "Bug fix"},
    ]
    with patch("devops_cli.commands.gh._get_repo_labels", return_value=mock_labels):
        result = runner.invoke(app, ["labels", "list"])
        assert result.exit_code == 0
        assert "type/feature" in result.output
        assert "type/bug" in result.output


def test_gh_labels_sync_dry_run() -> None:
    """devops gh labels sync --dry-run previews label reconciliations without mutations."""
    with (
        patch("devops_cli.commands.gh._get_repo_labels", return_value=[]),
        patch("devops_cli.commands.gh.sync_repository_labels") as mock_sync,
    ):
        mock_sync.return_value = MagicMock(created_count=5, updated_count=0, dry_run=True)
        result = runner.invoke(app, ["labels", "sync", "--dry-run"])
        assert result.exit_code == 0
        assert (
            "DRY RUN" in result.output or "dry-run" in result.output.lower() or "5" in result.output
        )


def test_gh_labels_sync_exits_nonzero_when_unauthenticated(tmp_path: Path) -> None:
    """`devops gh labels sync` fails when gh cannot list or create labels (#961).

    With no token and gh logged out, the label list came back empty, every create failed
    unseen, and the command still printed "Label sync complete" and exited 0.
    """
    labels_file = tmp_path / "labels.yml"
    labels_file.write_text("- name: type/bug\n  color: D73A4A\n", encoding="utf-8")
    failed = MagicMock(returncode=1, stdout="", stderr="gh auth login required")

    with (
        patch("devops_cli.commands.gh._get_github_client", return_value=None),
        patch("devops_cli.github.client.run_gh", return_value=failed),
    ):
        result = runner.invoke(app, ["labels", "sync", "-f", str(labels_file), "-R", "o/r"])

    assert (
        result.exit_code,
        "Label sync complete" in result.output,
        "gh auth login required" in result.output,
    ) == (1, False, True)


def test_gh_labels_list_asks_for_every_label() -> None:
    """`devops gh labels list` asks gh for more than its default 30 labels."""
    from devops_cli.commands.gh import _get_repo_labels

    listed = MagicMock(returncode=0, stdout='[{"name": "type/bug"}]', stderr="")
    with patch("devops_cli.commands.gh.run_gh", return_value=listed) as run_gh:
        _get_repo_labels("o/r")
    argv = run_gh.call_args.args[0]
    # Without --limit, gh lists 30.
    assert (int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 30) > 30


def test_gh_milestones_list(roadmap_store: InMemoryRoadmapStore) -> None:
    """devops gh milestones list prints each Release with its progress rate."""
    roadmap_store.create_release("v0.2.11")
    roadmap_store.seed_issue("Shipped", state=GitHubState.CLOSED, release="v0.2.11")

    result = runner.invoke(milestones_app, ["list", "-R", "example/repo"])
    assert (result.exit_code, "v0.2.11" in result.output, "100.0%" in result.output) == (
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


def test_get_github_client_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """_get_github_client respects DEVOPS_CLI_GITHUB_TOKEN."""
    from devops_cli.commands.gh import _get_github_client
    from devops_cli.config.env import ENV_GITHUB_TOKEN

    with patch("devops_cli.commands.gh.get_keyring_secret", return_value=None):
        monkeypatch.setenv(ENV_GITHUB_TOKEN, "test-env-token-12345")
        client = _get_github_client()
        assert client is not None
        assert client._token == "test-env-token-12345"


def test_gh_pages_status() -> None:
    """devops gh pages status outputs site deployment panel."""
    from devops_cli.github.pages import GitHubPagesInfo

    mock_info = GitHubPagesInfo(
        status="built",
        html_url="https://dan-petty.github.io/devops-cli/",
        build_type="legacy",
        branch="main",
        path="/",
        https_enforced=True,
    )
    with patch("devops_cli.commands.gh.get_pages_status", return_value=mock_info):
        result = runner.invoke(app, ["pages", "status", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "BUILT" in result.output
        assert "https://dan-petty.github.io/devops-cli/" in result.output


def test_gh_pages_builds() -> None:
    """devops gh pages builds lists build history records."""
    from devops_cli.github.pages import GitHubPagesBuildInfo

    mock_builds = [
        GitHubPagesBuildInfo(
            status="built",
            commit="b861fc4",
            duration=45802,
            created_at="2026-09-09T14:25:58Z",
        )
    ]
    with patch("devops_cli.commands.gh.get_pages_builds", return_value=mock_builds):
        result = runner.invoke(app, ["pages", "builds", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "BUILT" in result.output
        assert "b861fc4" in result.output


def test_gh_pages_verify(tmp_path: pytest.TempPathFactory) -> None:
    """devops gh pages verify passes on valid configuration."""
    with patch(
        "devops_cli.commands.gh.verify_pages_configuration", return_value=(True, ["✓ Config OK"])
    ):
        result = runner.invoke(app, ["pages", "verify"])
        assert result.exit_code == 0
        assert "compliant" in result.output.lower()


def test_gh_issues_list() -> None:
    """devops gh issues list outputs open issues."""
    from devops_cli.github.issues import GitHubIssue

    mock_issues = [
        GitHubIssue(
            number=77,
            title="feat(rag): dedicated library vector tier",
            state="open",
            milestone="v0.2.14",
            labels=["type/feature", "scope/ai"],
            assignees=["dan-petty"],
        )
    ]
    with patch("devops_cli.commands.gh.get_repository_issues", return_value=mock_issues):
        result = runner.invoke(app, ["issues", "list", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "#77" in result.output
        assert "feat(rag)" in result.output


def test_gh_issues_create() -> None:
    """devops gh issues create delegates to create_repository_issue."""
    from devops_cli.github.issues import GitHubIssue

    mock_created = GitHubIssue(
        number=99,
        title="fix(cli): bug fix",
        state="open",
        milestone="v0.2.14",
        labels=["type/bug", "scope/cli"],
        url="https://github.com/dan-petty/devops-cli/issues/99",
    )
    with patch("devops_cli.commands.gh.create_repository_issue", return_value=mock_created):
        result = runner.invoke(
            app,
            [
                "issues",
                "create",
                "--title",
                "fix(cli): bug fix",
                "--body",
                "details",
                "--milestone",
                "v0.2.14",
                "--label",
                "type/bug",
            ],
        )
        assert result.exit_code == 0
        assert "#99" in result.output


def test_gh_issues_triage() -> None:
    """devops gh issues triage reports compliance metrics."""
    from devops_cli.github.issues import IssueTriageAudit

    mock_audit = IssueTriageAudit(
        total_open=5,
        valid_count=5,
        issues_missing_type=[],
        issues_missing_scope=[],
        issues_missing_priority=[],
        issues_missing_milestone=[],
    )
    with patch("devops_cli.commands.gh.audit_issues_triage", return_value=mock_audit):
        result = runner.invoke(app, ["issues", "triage", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "5 (100.0%)" in result.output


def test_gh_issues_status() -> None:
    """devops gh issues status outputs category counts."""
    mock_summary = {
        "total_open": 3,
        "by_priority": {"priority/p1-high": 1, "priority/p2-medium": 2},
        "by_type": {"type/feature": 3},
        "by_milestone": {"v0.2.14": 3},
    }
    with patch("devops_cli.commands.gh.get_issues_summary", return_value=mock_summary):
        result = runner.invoke(app, ["issues", "status", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "Total Open" in result.output
        assert "v0.2.14" in result.output


def test_gh_project_list() -> None:
    """devops gh project list displays remote project boards."""
    mock_projects = [
        {
            "number": 2,
            "title": "Roadmap Board",
            "state": "open",
            "id": "PVT_123",
            "url": "https://github.com/orgs/test/projects/2",
        }
    ]
    with patch("devops_cli.commands.gh.list_remote_projects", return_value=mock_projects):
        result = runner.invoke(app, ["project", "list", "--owner", "test"])
        assert result.exit_code == 0
        assert "Roadmap Board" in result.output
        assert "OPEN" in result.output


def test_gh_project_audit() -> None:
    """devops gh project audit outputs alignment results."""
    mock_drift = {
        "project_number": 2,
        "project_found": True,
        "views_compliant": True,
        "missing_views": [],
        "matching_views": ["Sprint Kanban"],
    }
    with patch("devops_cli.commands.gh.audit_project_drift", return_value=mock_drift):
        result = runner.invoke(app, ["project", "audit", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "COMPLIANT" in result.output


def test_gh_views_audit() -> None:
    """devops gh views audit displays view compliance table."""
    mock_views_audit = {
        "project_number": 2,
        "compliant": True,
        "missing_views": [],
        "matching_views": ["Sprint Kanban", "Roadmap Timeline"],
        "total_remote_views": 4,
    }
    with patch("devops_cli.commands.gh.audit_remote_project_views", return_value=mock_views_audit):
        result = runner.invoke(app, ["views", "audit", "--repo", "dan-petty/devops-cli"])
        assert result.exit_code == 0
        assert "Project Views Compliance" in result.output


def test_gh_project_reconcile() -> None:
    """devops gh project reconcile lists every field change with what decided it."""
    mock_res = {
        "project_number": 2,
        "items_evaluated": 10,
        "items_reconciled": 1,
        "dry_run": True,
        "changes": [
            {
                "url": "https://github.com/dan-petty/devops-cli/issues/7",
                "field": "Status",
                "old": None,
                "new": "Backlog",
                "source": "default for an unset status",
            }
        ],
    }
    with patch(
        "devops_cli.github.projects.reconcile_project_custom_fields",
        return_value=mock_res,
    ):
        result = runner.invoke(
            app,
            [
                "project",
                "reconcile",
                "--project-number",
                "2",
                "--repo",
                "dan-petty/devops-cli",
                "--dry-run",
            ],
        )
    assert (
        result.exit_code,
        "default for an unset status" in result.output,
        "1 of 10 items" in result.output,
    ) == (0, True, True)


def test_gh_project_reconcile_refuses_a_missing_board() -> None:
    """Without a matching board, reconcile must not guess a board number."""
    with (
        patch("devops_cli.github.projects.find_remote_project", return_value=None),
        patch("devops_cli.github.projects.reconcile_project_custom_fields") as mock_reconcile,
    ):
        result = runner.invoke(app, ["project", "reconcile", "--repo", "dan-petty/devops-cli"])
    assert (result.exit_code, mock_reconcile.called, "--project-number" in result.output) == (
        1,
        False,
        True,
    )


def test_gh_pr_threads_alias() -> None:
    """devops gh pr threads list functions as an alias to devops pr threads list."""
    with patch(
        "devops_cli.github.pr_threads.list_pr_review_threads",
        return_value=[],
    ):
        result = runner.invoke(
            app, ["pr", "threads", "list", "83", "--repo", "dan-petty/devops-cli"]
        )
        assert result.exit_code == 0
        assert "No review threads found" in result.output


def test_gh_rate_limit_table() -> None:
    """devops gh rate-limit displays formatted rate limit table."""
    mock_rate_limit = json.dumps(
        {
            "resources": {
                "core": {"limit": 5000, "used": 10, "remaining": 4990, "reset": 1789249509},
                "graphql": {"limit": 5000, "used": 5000, "remaining": 0, "reset": 1789246767},
                "search": {"limit": 30, "used": 2, "remaining": 28, "reset": 1789245969},
            }
        }
    )
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout=mock_rate_limit, stderr=""),
        ),
    ):
        result = runner.invoke(app, ["rate-limit"])
        assert (
            result.exit_code,
            "GitHub API Rate Limits" in result.output,
            "graphql" in result.output,
            "4990" in result.output,
            "Rate Limiter Activity" in result.output,
        ) == (0, True, True, True, True)


def test_gh_runs_list() -> None:
    """devops gh runs list renders recent workflow runs table."""
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
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout=mock_runs, stderr=""),
        ),
    ):
        result = runner.invoke(app, ["runs", "list"])
        assert result.exit_code == 0
        assert "CI Quality Gate" in result.output
        assert "12345678" in result.output


def test_gh_runs_view_failed_logs() -> None:
    """devops gh runs view with --log-failed fetches failed workflow logs."""
    mock_log = "Error: Step failed with exit code 1"
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout=mock_log, stderr=""),
        ) as mock_subprocess,
    ):
        result = runner.invoke(app, ["runs", "view", "12345678", "--log-failed"])
        assert result.exit_code == 0
        assert "Step failed" in result.output
        args = mock_subprocess.call_args[0][0]
        assert "run" in args
        assert "view" in args
        assert "12345678" in args
        assert "--log-failed" in args


def test_gh_issues_edit_success() -> None:
    """devops gh issues edit patches issue title, body, and state via stdin."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout="", stderr=""),
        ) as mock_sub,
    ):
        result = runner.invoke(
            app,
            [
                "issues",
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
        cmd = mock_sub.call_args[0][0]
        assert "PATCH" in cmd
        assert any("issues/185" in c for c in cmd)
        assert "--input" in cmd
        payload = json.loads(mock_sub.call_args.kwargs["input"])
        assert payload["title"] == "Updated Title"
        assert payload["body"] == "Updated Body"
        assert payload["state"] == "closed"


def test_gh_issues_edit_error_masked() -> None:
    """devops gh issues edit masks secret tokens in error output."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(
                returncode=1,
                stdout="",
                stderr="HTTP 401: Bad credentials token ghp_secrettoken1234567890abcdefghijklmn",
            ),
        ),
    ):
        result = runner.invoke(app, ["issues", "edit", "185", "--title", "New Title"])
        assert result.exit_code == 1
        assert "ghp_secrettoken" not in result.output


def test_gh_issues_edit_no_changes() -> None:
    """devops gh issues edit warns when no changes are specified."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
    ):
        result = runner.invoke(app, ["issues", "edit", "185"])
        assert result.exit_code == 0
        assert "No changes specified" in result.output


def test_gh_rate_limit_error_masked() -> None:
    """devops gh rate-limit masks secrets on error."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(
                returncode=1,
                stdout="",
                stderr="Error ghp_secrettoken1234567890abcdefghijklmn",
            ),
        ),
    ):
        result = runner.invoke(app, ["rate-limit"])
        assert result.exit_code == 1
        assert "ghp_secrettoken" not in result.output


def test_gh_runs_list_error_masked() -> None:
    """devops gh runs list masks secrets on error."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(
                returncode=1,
                stdout="",
                stderr="Error ghp_secrettoken1234567890abcdefghijklmn",
            ),
        ),
    ):
        result = runner.invoke(app, ["runs", "list"])
        assert result.exit_code == 1
        assert "ghp_secrettoken" not in result.output


def test_gh_runs_view_error_masked() -> None:
    """devops gh runs view masks secrets on error."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(
                returncode=1,
                stdout="",
                stderr="Error ghp_secrettoken1234567890abcdefghijklmn",
            ),
        ),
    ):
        result = runner.invoke(app, ["runs", "view", "123456"])
        assert result.exit_code == 1
        assert "ghp_secrettoken" not in result.output


def test_gh_rate_limit_json() -> None:
    """devops gh rate-limit --format json outputs valid json."""
    mock_data = json.dumps({"resources": {"core": {"limit": 5000, "remaining": 4999}}})
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout=mock_data, stderr=""),
        ),
    ):
        result = runner.invoke(app, ["rate-limit", "--format", "json"])
        parsed = json.loads(result.output)
        assert (
            result.exit_code,
            "resources" in parsed,
            "total_throttles" in parsed,
            "total_wait_seconds" in parsed,
        ) == (0, True, True, True)


def test_gh_rate_limit_invalid_format() -> None:
    """devops gh rate-limit --format invalid exits with error."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout="{}", stderr=""),
        ),
    ):
        result = runner.invoke(app, ["rate-limit", "--format", "xml"])
        assert result.exit_code == 1
        assert "Unsupported format" in result.output


def test_gh_runs_list_json() -> None:
    """devops gh runs list --format json outputs serialized json list."""
    mock_runs = json.dumps([{"databaseId": 1234, "name": "CI", "status": "completed"}])
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch("devops_cli.core.repo.get_repo_origin_name", return_value="owner/repo"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout=mock_runs, stderr=""),
        ),
    ):
        result = runner.invoke(app, ["runs", "list", "--format", "json"])
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert len(parsed) == 1
        assert parsed[0]["databaseId"] == 1234


def test_gh_runs_list_options() -> None:
    """devops gh runs list forwards branch and repo flags."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout="[]", stderr=""),
        ) as mock_sub,
    ):
        result = runner.invoke(
            app, ["runs", "list", "--branch", "feat/test", "--repo", "custom/repo"]
        )
        assert result.exit_code == 0
        cmd = mock_sub.call_args[0][0]
        assert "--branch" in cmd
        assert "feat/test" in cmd
        assert "--repo" in cmd
        assert "custom/repo" in cmd


def test_gh_runs_view_full_log_and_job() -> None:
    """devops gh runs view forwards --log, --job, and --repo."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout="Job log content\n", stderr=""),
        ) as mock_sub,
    ):
        result = runner.invoke(
            app, ["runs", "view", "999", "--log", "--job", "build", "--repo", "custom/repo"]
        )
        assert result.exit_code == 0
        assert "Job log content" in result.output
        cmd = mock_sub.call_args[0][0]
        assert "--log" in cmd
        assert "--job" in cmd
        assert "build" in cmd
        assert "--repo" in cmd
        assert "custom/repo" in cmd


def test_gh_api_basic() -> None:
    """devops gh api executes request and outputs result."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout='{"name": "test-repo"}\n', stderr=""),
        ) as mock_gh,
    ):
        result = runner.invoke(app, ["api", "repos/test/repo"])
        assert result.exit_code == 0
        assert "test-repo" in result.output
        mock_gh.assert_called_once()
        args = mock_gh.call_args[0][0]
        assert args == ["api", "repos/test/repo"]


def test_gh_api_options_and_cache() -> None:
    """devops gh api forwards HTTP method, pagination, jq, templates, and caching flags."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(returncode=0, stdout="Filtered Output\n", stderr=""),
        ) as mock_gh,
    ):
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
        args = mock_gh.call_args[0][0]
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
        assert mock_gh.call_args.kwargs["use_cache"] is True
        assert mock_gh.call_args.kwargs["cache_ttl"] == 25.0


def test_gh_api_error_masked() -> None:
    """devops gh api masks sensitive tokens on request failure."""
    with (
        patch("shutil.which", return_value="/usr/bin/gh"),
        patch(
            "devops_cli.commands.gh.run_gh",
            return_value=MagicMock(
                returncode=1,
                stdout="",
                stderr="HTTP 403: API rate limit exceeded token ghp_secretkey1234567890abcdefghijkl",
            ),
        ),
    ):
        result = runner.invoke(app, ["api", "rate_limit"])
        assert result.exit_code == 1
        assert "GitHub API request failed" in result.output
        assert "ghp_secretkey" not in result.output
