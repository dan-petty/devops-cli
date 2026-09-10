"""Tests for the GitHub client wrapper and repository models."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from github.GithubException import UnknownObjectException

from devops_cli.github.client import (
    GhCliClient,
    GitHubClient,
    RepoInfo,
    parse_paginated_json,
)


def test_repo_info_model() -> None:
    """Verify RepoInfo Pydantic model initialization."""
    info = RepoInfo(
        name="test",
        full_name="org/test",
        ssh_url="git@github.com:org/test.git",
        clone_url="https://github.com/org/test.git",
        private=True,
        fork=False,
        archived=False,
    )
    assert info.name == "test"
    assert info.private is True


def test_github_client_operations() -> None:
    """Verify GitHubClient get_org_repos, SSH key management, and PR lookups."""
    mock_gh = MagicMock()
    mock_user = MagicMock()
    mock_user.login = "test-user"
    mock_key = MagicMock()
    mock_key.id = 1
    mock_key.title = "key1"
    mock_key.key = "ssh-ed25519 AAA..."
    mock_user.get_keys.return_value = [mock_key]
    mock_created_key = MagicMock()
    mock_created_key.id = 2
    mock_user.create_key.return_value = mock_created_key
    mock_gh.get_user.return_value = mock_user

    mock_repo = MagicMock()
    mock_repo.name = "repo1"
    mock_repo.full_name = "test-org/repo1"
    mock_repo.ssh_url = "git@github.com:test-org/repo1.git"
    mock_repo.clone_url = "https://github.com/test-org/repo1.git"
    mock_repo.private = False
    mock_repo.fork = False
    mock_repo.archived = False

    mock_org = MagicMock()
    mock_org.get_repos.return_value = [mock_repo]
    mock_gh.get_organization.return_value = mock_org

    with patch("github.Github", return_value=mock_gh):
        client = GitHubClient("token123")
        repos = client.get_org_repos("test-org")
        assert len(repos) == 1
        assert repos[0].name == "repo1"

        keys = client.get_user_ssh_keys()
        assert len(keys) == 1
        assert keys[0].id == 1

        new_key_id = client.add_user_ssh_key("new_key", "ssh-ed25519 AAA...")
        assert new_key_id == 2

        client.delete_user_ssh_key(1)
        mock_user.get_key.assert_called_with(1)

        _ = client.get_pull("test-org/repo1", 42)
        mock_gh.get_repo.assert_called_with("test-org/repo1")


def test_get_org_repos_falls_back_to_authenticated_user_login() -> None:
    client = GitHubClient("token")

    repos = [
        SimpleNamespace(
            name="public-repo",
            full_name="octo/public-repo",
            ssh_url="git@github.com:octo/public-repo.git",
            clone_url="https://github.com/octo/public-repo.git",
            private=False,
            fork=False,
        ),
        SimpleNamespace(
            name="private-repo",
            full_name="octo/private-repo",
            ssh_url="git@github.com:octo/private-repo.git",
            clone_url="https://github.com/octo/private-repo.git",
            private=True,
            fork=False,
        ),
        SimpleNamespace(
            name="forked-repo",
            full_name="octo/forked-repo",
            ssh_url="git@github.com:octo/forked-repo.git",
            clone_url="https://github.com/octo/forked-repo.git",
            private=False,
            fork=True,
        ),
    ]

    class _FakeUser:
        login = "octo"

        def get_repos(self) -> list[SimpleNamespace]:
            return repos

    class _FakeGithub:
        def get_organization(self, org_name: str) -> object:
            raise UnknownObjectException(404, None, None, f"No org {org_name}")

        def get_user(self) -> _FakeUser:
            return _FakeUser()

    client._gh = _FakeGithub()  # type: ignore[assignment]

    result = client.get_org_repos("octo", include_private=False, include_forks=False)

    assert [repo.name for repo in result] == ["public-repo"]


def test_get_org_repos_skips_archived_repos() -> None:
    client = GitHubClient("token")

    repos = [
        SimpleNamespace(
            name="active-repo",
            full_name="octo/active-repo",
            ssh_url="git@github.com:octo/active-repo.git",
            clone_url="https://github.com/octo/active-repo.git",
            private=False,
            fork=False,
            archived=False,
        ),
        SimpleNamespace(
            name="archived-repo",
            full_name="octo/archived-repo",
            ssh_url="git@github.com:octo/archived-repo.git",
            clone_url="https://github.com/octo/archived-repo.git",
            private=False,
            fork=False,
            archived=True,
        ),
    ]

    class _FakeOrg:
        def get_repos(self, type: str) -> list[SimpleNamespace]:
            return repos

    class _FakeGithub:
        def get_organization(self, org_name: str) -> _FakeOrg:
            return _FakeOrg()

    client._gh = _FakeGithub()  # type: ignore[assignment]

    result = client.get_org_repos(
        "octo", include_private=False, include_forks=False, include_archived=False
    )

    assert [repo.name for repo in result] == ["active-repo"]


def test_create_pr_review_comment() -> None:
    client = GitHubClient("token")

    called_kwargs: dict[str, str | int] = {}

    class _FakePull:
        head = SimpleNamespace(sha="sha-123")

        def create_review_comment(self, **kwargs: str | int) -> str:
            called_kwargs.update(kwargs)
            return "comment-123"

    class _FakeRepo:
        def get_pull(self, number: int) -> _FakePull:
            return _FakePull()

    class _FakeGithub:
        def get_repo(self, repo: str) -> _FakeRepo:
            return _FakeRepo()

    client._gh = _FakeGithub()  # type: ignore[assignment]

    res = client.create_pr_review_comment(
        repo="octo/repo",
        number=42,
        body="LGTM!",
        commit_id="",
        path="src/main.py",
        line=15,
    )
    assert res == "comment-123"
    assert called_kwargs["body"] == "LGTM!"
    assert called_kwargs["commit"] == "sha-123"
    assert called_kwargs["path"] == "src/main.py"
    assert called_kwargs["line"] == 15


def test_get_pr_diff_normal_and_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify get_pr_diff fetches unified diff with and without redirect."""
    import httpx2

    client = GitHubClient("token123")

    class MockDiffResponse:
        def __init__(self, text: str, is_redirect: bool = False, location: str = ""):
            self.text = text
            self.is_redirect = is_redirect
            self.headers = {"location": location} if location else {}

        def raise_for_status(self) -> None:
            pass

    # 1. Direct diff response
    monkeypatch.setattr(
        httpx2.Client,
        "get",
        lambda self, url, **kwargs: MockDiffResponse("diff --git a/foo b/foo\n+line"),
    )
    diff = client.get_pr_diff("octo/repo", 42)
    assert "diff --git a/foo b/foo" in diff

    # 2. Redirected diff response
    calls = []

    def mock_redirect_get(self: Any, url: str, **kwargs: Any) -> MockDiffResponse:
        calls.append(url)
        if len(calls) == 1:
            return MockDiffResponse(
                "",
                is_redirect=True,
                location="https://api.github.com/repos/octo/repo/pulls/42/diff",
            )
        return MockDiffResponse("diff --git a/redirected b/redirected\n+newline")

    monkeypatch.setattr(httpx2.Client, "get", mock_redirect_get)
    diff_redir = client.get_pr_diff("octo/repo", 42)
    assert "diff --git a/redirected" in diff_redir
    assert len(calls) == 2


def test_create_milestone_forwards_due_on(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify create_milestone parses and forwards due_on to GitHub repository."""
    import datetime
    from unittest.mock import MagicMock

    client = GitHubClient("token123")
    mock_repo = MagicMock()
    monkeypatch.setattr(client._gh, "get_repo", lambda r: mock_repo)

    # String date
    client.create_milestone(
        repo="octo/repo",
        title="v1.0.0",
        description="Launch",
        state="open",
        due_on="2026-12-31",
    )
    mock_repo.create_milestone.assert_called_once()
    called_kwargs = mock_repo.create_milestone.call_args[1]
    assert called_kwargs["title"] == "v1.0.0"
    assert called_kwargs["description"] == "Launch"
    assert called_kwargs["state"] == "open"
    assert isinstance(called_kwargs["due_on"], (datetime.date, datetime.datetime))
    assert called_kwargs["due_on"].year == 2026

    # Native date object
    mock_repo.reset_mock()
    target_date = datetime.date(2027, 1, 15)
    client.create_milestone(
        repo="octo/repo",
        title="v1.1.0",
        due_on=target_date,
    )
    called_kwargs2 = mock_repo.create_milestone.call_args[1]
    assert called_kwargs2["due_on"] == target_date


def test_edit_milestone_supplies_existing_title(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify edit_milestone supplies milestone.title when title is None."""
    from unittest.mock import MagicMock

    client = GitHubClient("token123")
    mock_repo = MagicMock()
    mock_milestone = MagicMock()
    mock_milestone.title = "v0.2.12"
    mock_repo.get_milestone.return_value = mock_milestone
    monkeypatch.setattr(client._gh, "get_repo", lambda r: mock_repo)

    client.edit_milestone("octo/repo", 24, state="closed")
    mock_milestone.edit.assert_called_once_with(state="closed", title="v0.2.12")


def test_close_milestone_by_title_and_number(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify close_milestone closes by numeric id and by title string."""
    from unittest.mock import MagicMock

    client = GitHubClient("token123")
    mock_repo = MagicMock()
    mock_milestone = MagicMock()
    mock_milestone.title = "v0.2.12"
    mock_repo.get_milestone.return_value = mock_milestone
    monkeypatch.setattr(client._gh, "get_repo", lambda r: mock_repo)

    # 1. Close by integer
    res_int = client.close_milestone("octo/repo", 24)
    assert res_int is True
    mock_milestone.edit.assert_called_with(state="closed", title="v0.2.12")

    # 2. Close by title matching
    mock_milestone.reset_mock()
    monkeypatch.setattr(
        client,
        "get_milestones",
        lambda repo, state="all": [{"title": "v0.2.13", "number": 25}],
    )
    mock_milestone.title = "v0.2.13"
    res_title = client.close_milestone("octo/repo", "v0.2.13")
    assert res_title is True
    mock_repo.get_milestone.assert_called_with(25)
    mock_milestone.edit.assert_called_with(state="closed", title="v0.2.13")

    # 3. Non-existent milestone returns False
    res_missing = client.close_milestone("octo/repo", "v9.9.9")
    assert res_missing is False


def test_parse_paginated_json_concatenated_documents() -> None:
    """Verify parse_paginated_json correctly parses multiple concatenated pages from gh api --paginate."""
    page_1 = '[{"number": 1, "title": "v0.1.0"}]'
    page_2 = '[{"number": 2, "title": "v0.2.0"}, {"number": 3, "title": "v0.3.0"}]'
    raw_output = f"{page_1}\n{page_2}\n"

    parsed = parse_paginated_json(raw_output)
    assert len(parsed) == 3
    assert parsed[0]["title"] == "v0.1.0"
    assert parsed[1]["title"] == "v0.2.0"
    assert parsed[2]["title"] == "v0.3.0"

    assert parse_paginated_json("") == []
    assert parse_paginated_json("   ") == []


def test_gh_cli_client_labels() -> None:
    """Verify GhCliClient label listing, creation, and editing commands."""
    client = GhCliClient(default_repo="owner/my-repo")

    mock_list_proc = MagicMock(
        returncode=0,
        stdout='[{"name": "bug", "color": "d73a4a", "description": "Bug fix"}]',
    )
    mock_run = MagicMock(return_value=mock_list_proc)

    with patch("devops_cli.github.client.run_subprocess", mock_run):
        labels = client.get_labels("owner/my-repo")
        assert len(labels) == 1
        assert labels[0]["name"] == "bug"
        assert mock_run.call_args[0][0][:4] == ["gh", "label", "list", "--json"]

        client.create_label("owner/my-repo", "feature", "#0e8a16", "New feature")
        create_cmd = mock_run.call_args[0][0]
        assert create_cmd[:4] == ["gh", "label", "create", "feature"]
        assert "--color" in create_cmd
        assert "0e8a16" in create_cmd

        client.edit_label("owner/my-repo", "feature", "0075ca", "Updated desc")
        edit_cmd = mock_run.call_args[0][0]
        assert edit_cmd[:4] == ["gh", "label", "edit", "feature"]
        assert "0075ca" in edit_cmd


def test_gh_cli_client_milestones_paginated() -> None:
    """Verify GhCliClient milestone querying across multiple paginated pages."""
    client = GhCliClient(default_repo="owner/my-repo")

    multi_page_stdout = (
        '[{"number": 1, "title": "v0.1.0", "state": "closed", "open_issues": 0, "closed_issues": 5}]\n'
        '[{"number": 2, "title": "v0.2.0", "state": "open", "open_issues": 3, "closed_issues": 10}]\n'
    )
    mock_proc = MagicMock(returncode=0, stdout=multi_page_stdout)
    mock_run = MagicMock(return_value=mock_proc)

    with patch("devops_cli.github.client.run_subprocess", mock_run):
        milestones = client.get_milestones("owner/my-repo")
        assert len(milestones) == 2
        assert milestones[0]["title"] == "v0.1.0"
        assert milestones[0]["state"] == "closed"
        assert milestones[1]["title"] == "v0.2.0"
        assert milestones[1]["open_issues"] == 3

        client.create_milestone(
            "owner/my-repo",
            "v0.3.0",
            description="Next release",
            due_on="2026-10-01T00:00:00Z",
        )
        create_cmd = mock_run.call_args[0][0]
        assert "repos/owner/my-repo/milestones" in create_cmd
        assert "title=v0.3.0" in create_cmd
        assert "due_on=2026-10-01T00:00:00Z" in create_cmd

        client.edit_milestone("owner/my-repo", 2, title="v0.2.1", state="closed")
        edit_cmd = mock_run.call_args[0][0]
        assert "repos/owner/my-repo/milestones/2" in edit_cmd
        assert "title=v0.2.1" in edit_cmd
        assert "state=closed" in edit_cmd
