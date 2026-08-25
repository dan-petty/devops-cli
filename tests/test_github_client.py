"""Tests for the GitHub client wrapper and repository models."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from github.GithubException import UnknownObjectException

from devops_cli.github.client import GitHubClient, RepoInfo


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

    client._gh = _FakeGithub()

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

    client._gh = _FakeGithub()

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

    client._gh = _FakeGithub()

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
