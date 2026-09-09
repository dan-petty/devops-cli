"""Test suite for devops gh CLI command group."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.gh import app

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


def test_gh_milestones_list() -> None:
    """devops gh milestones list prints milestones and progress rates."""
    mock_milestones = [
        {
            "title": "v0.2.11",
            "state": "open",
            "open_issues": 1,
            "closed_issues": 9,
            "due_on": "2026-09-10",
        },
    ]
    with patch("devops_cli.commands.gh._get_repo_milestones", return_value=mock_milestones):
        result = runner.invoke(app, ["milestones", "list"])
        assert result.exit_code == 0
        assert "v0.2.11" in result.output


def test_gh_milestones_sync_dry_run() -> None:
    """devops gh milestones sync --dry-run extracts roadmap milestones and simulates create."""
    with (
        patch("devops_cli.commands.gh._get_repo_milestones", return_value=[]),
        patch("devops_cli.commands.gh.sync_repository_milestones") as mock_sync,
    ):
        mock_sync.return_value = MagicMock(created_count=4, dry_run=True)
        result = runner.invoke(app, ["milestones", "sync", "--dry-run"])
        assert result.exit_code == 0


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


def test_get_repo_milestones_paginated() -> None:
    """_get_repo_milestones passes --paginate and per_page=100 to gh api."""
    from devops_cli.commands.gh import _get_repo_milestones

    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = '[{"title": "v0.2.12", "number": 1, "state": "open"}]'

    with (
        patch("devops_cli.commands.gh._get_github_client", return_value=None),
        patch("devops_cli.commands.gh.run_subprocess", return_value=mock_res) as mock_run,
    ):
        milestones = _get_repo_milestones("org/test-repo", state="all")
        assert len(milestones) == 1
        assert milestones[0]["title"] == "v0.2.12"
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "--paginate" in cmd
        assert any("per_page=100" in arg for arg in cmd)


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
