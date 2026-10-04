"""Tests for the GitHub client wrapper and repository models."""

from __future__ import annotations

import json
import subprocess
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from github.GithubException import UnknownObjectException

from devops_cli.config.constants import CONST_GH_CLI
from devops_cli.github.client import (
    GhCliClient,
    GitHubClient,
    RepoInfo,
    parse_paginated_json,
)

if TYPE_CHECKING:
    from tests.web_fakes import StubWeb


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


def test_get_merge_base_reads_the_compare_endpoint() -> None:
    """Verify the merge base comes from comparing base and head in the named repository, and a
    failed comparison gives None rather than a ref to read at (#593)."""
    client = GitHubClient("token")
    compared: list[tuple[str, str, str, int | None]] = []

    class _FakeRepo:
        def __init__(self, name: str) -> None:
            self.name = name

        def compare(
            self, base: str, head: str, comparison_commits_per_page: int | None = None
        ) -> SimpleNamespace:
            compared.append((self.name, base, head, comparison_commits_per_page))
            if head == "unknown":
                raise UnknownObjectException(404, "Not Found", None)
            return SimpleNamespace(merge_base_commit=SimpleNamespace(sha="merge-base-sha"))

    class _FakeGithub:
        def get_repo(self, repo: str, lazy: bool = False) -> _FakeRepo:
            return _FakeRepo(f"{repo} lazy={lazy}")

    client._gh = _FakeGithub()  # type: ignore[assignment]

    found = client.get_merge_base("octo/repo", "base-tip", "head-sha")
    missing = client.get_merge_base("octo/repo", "base-tip", "unknown")

    assert (found, missing, compared) == (
        "merge-base-sha",
        None,
        [
            ("octo/repo lazy=True", "base-tip", "head-sha", 1),
            ("octo/repo lazy=True", "base-tip", "unknown", 1),
        ],
    )


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


def _scripted_gh(argv: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
    """Answer `gh auth token` with token A, `gh api rate_limit` with a fresh quota, the rest empty."""
    answers = {
        ("auth", "token"): "A\n",
        ("api", "rate_limit"): json.dumps(
            {"resources": {"core": {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}}}
        ),
    }
    return subprocess.CompletedProcess(
        argv, 0, stdout=answers.get(tuple(argv[1:3]), "[]"), stderr=""
    )


def test_one_identity_reaches_pygithub_gh_and_the_quota_refresh(
    monkeypatch: pytest.MonkeyPatch, stub_web: StubWeb
) -> None:
    """The PR diff, two run_gh calls and the quota refresh all act as token A from `gh auth token`."""
    from devops_cli.core import process
    from devops_cli.github.rate_limiter import run_gh
    from devops_cli.github.session import get_github_session

    monkeypatch.setattr(process, "_github_token", None)
    monkeypatch.setenv("GITHUB_TOKEN", "C")
    stub_web.page("https://api.github.com/repos/octo/repo/pulls/42", "diff --git a/f b/f")
    with patch("subprocess.run", side_effect=_scripted_gh) as run:
        diff = get_github_session().client.get_pr_diff("octo/repo", 42)
        run_gh(["issue", "list"])
        run_gh(["label", "list"])
    children = [
        (
            call.args[0][1:3],
            call.kwargs["env"].get("GH_TOKEN"),
            call.kwargs["env"].get("GITHUB_TOKEN"),
        )
        for call in run.call_args_list
        if call.args[0][0] == CONST_GH_CLI
    ]
    github_requests = [request for request in stub_web.sent if request.url.host == "api.github.com"]
    assert (diff, [request.headers["authorization"] for request in github_requests], children) == (
        "diff --git a/f b/f",
        ["Bearer A"],
        [
            (["auth", "token"], None, "C"),
            (["api", "rate_limit"], "A", None),
            (["issue", "list"], "A", None),
            (["label", "list"], "A", None),
        ],
    )


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

    with patch("devops_cli.github.client.run_gh", mock_run):
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


def test_gh_cli_client_label_failures_raise() -> None:
    """A failed `gh label` call raises instead of reading as no labels or as done (#961).

    `get_labels` returned [] on any failure, so `labels sync` set out to create every label,
    and `create_label` and `edit_label` dropped the result, so their failures went unseen.
    """
    from devops_cli.exceptions.git import GitHubOperationError

    client = GhCliClient(default_repo="o/r")
    failed = MagicMock(returncode=1, stdout="", stderr="not logged in")
    calls = [
        lambda: client.get_labels("o/r"),
        lambda: client.create_label("o/r", "x", "000000"),
        lambda: client.edit_label("o/r", "x", "000000"),
    ]
    raised: list[str] = []
    with patch("devops_cli.github.client.run_gh", return_value=failed):
        for call in calls:
            with pytest.raises(GitHubOperationError) as error:
                call()
            raised.append(str(error.value))
    assert all("not logged in" in message for message in raised)


def test_gh_cli_client_lists_every_label() -> None:
    """`gh label list` stops at 30 labels unless told otherwise; .github/labels.yml has 31."""
    listed = MagicMock(returncode=0, stdout="[]", stderr="")
    with patch("devops_cli.github.client.run_gh", return_value=listed) as run_gh:
        GhCliClient(default_repo="o/r").get_labels("o/r")
    argv = run_gh.call_args.args[0]
    # Without --limit, gh lists 30.
    assert (int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 30) > 30
