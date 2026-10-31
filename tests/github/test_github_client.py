"""Tests for the GitHub client: the typed pull request, file, merge base, repository and issue
comment calls it makes through the GitHub session, and the gh label client (#891)."""

from __future__ import annotations

import base64
import json
import subprocess
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx2
import pytest

from devops_cli.config.constants import CONST_GH_CLI, CONST_GITHUB_DIFF_MEDIA_TYPE
from devops_cli.exceptions.git import (
    GitHubNotFoundError,
    GitHubUnauthenticatedError,
    GitHubUnreadError,
)
from devops_cli.github.client import (
    CommitRef,
    GhCliClient,
    PullRequest,
    PullRequestFile,
    RepoInfo,
)
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import (
    API,
    github_json,
    github_redirect,
    github_text,
    quota_headers,
)
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake

_RECORDED = json.loads(
    (FIXTURES / "github" / "hello_world_pull_request.json").read_text(encoding="utf-8")
)
_REPOSITORIES = json.loads(
    (FIXTURES / "github" / "hello_world_repositories.json").read_text(encoding="utf-8")
)
_PULL = "/repos/octocat/Hello-World/pulls/158"
_FILES = f"{_PULL}/files?per_page=100"
_BASE_SHA = "7fd1a60b01f91b314f59955a4e4d4e80d8edf11d"
_HEAD_SHA = "ec18ca7bca5202d8e139a58b25757dc161255245"
_README = _RECORDED["readme_contents"]
_README_AT_BASE = f"/repos/octocat/Hello-World/contents/README?ref={_BASE_SHA}"
_COMPARE = f"/repos/octocat/Hello-World/compare/{_BASE_SHA}...{_HEAD_SHA}?per_page=1"
_ORG_REPOS = "/orgs/octocat/repos?type=all&per_page=100"
_USER_OWNED_REPOS = "/user/repos?affiliation=owner&visibility=all&per_page=100"


def _client() -> Any:
    """The client of the process's GitHub session, as every caller reaches it."""
    return get_github_session().client


def _route_the_recorded_pull_request(api: GitHubApiFake) -> None:
    """Answer the pull request, and its two pages of files with the `Link` GitHub sent."""
    api.route("GET", _PULL, github_json(_RECORDED["pull_request"]))
    first, second = _RECORDED["files_pages"]
    api.route("GET", _FILES, github_json(first["body"], headers={"link": first["link"]}))
    api.route(
        "GET",
        "/repositories/1296269/pulls/158/files?per_page=1&page=2",
        github_json(second["body"], headers={"link": second["link"]}),
    )


def _carried(api: GitHubApiFake) -> set[str]:
    """The authorization every request the fake received carried."""
    return {request.headers["authorization"] for request in api.sent}


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


def test_the_client_is_the_sessions_own_and_is_built_once() -> None:
    """The session builds one client from itself, so every caller shares its identity."""
    session = get_github_session()
    assert session.client is session.client


def test_a_pull_request_is_read_with_its_title_and_both_commits(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The recorded pull request has a title, a base in octocat/Hello-World and a head whose
    repository GitHub reports as null, since the fork it came from was deleted: that head has no
    repository rather than a wrong one."""
    _route_the_recorded_pull_request(github_api)
    pull = _client().get_pull("octocat/Hello-World", 158)
    assert (pull, github_api.requested, _carried(github_api)) == (
        PullRequest(
            title="Update and rename README to README.md. Also Added Bolding",
            head=CommitRef(sha=_HEAD_SHA, ref="master", repository=None),
            base=CommitRef(sha=_BASE_SHA, ref="master", repository="octocat/Hello-World"),
        ),
        [f"GET https://api.github.com{_PULL}"],
        {f"token {pin_github_session}"},
    )


def test_a_pull_request_that_lacks_a_title_is_unread(github_api: GitHubApiFake) -> None:
    """An answer that is no pull request raises the unread error, naming the path."""
    github_api.route("GET", _PULL, github_json({"number": 158}))
    with pytest.raises(GitHubUnreadError) as raised:
        _client().get_pull("octocat/Hello-World", 158)
    assert raised.value.details["path"] == _PULL


def test_a_missing_pull_request_raises_the_not_found_error(github_api: GitHubApiFake) -> None:
    """GitHub's 404 for a pull request is the not-found error, not an empty pull request."""
    with pytest.raises(GitHubNotFoundError) as raised:
        _client().get_pull("octocat/Hello-World", 9999)
    assert raised.value.error_code == "GITHUB_NOT_FOUND"
    assert github_api.requested == [
        "GET https://api.github.com/repos/octocat/Hello-World/pulls/9999"
    ]


def test_a_repository_name_is_encoded_in_the_request(github_api: GitHubApiFake) -> None:
    """A character that is no part of a path stays inside the repository segment, so the name
    cannot end the path or start a query."""
    github_api.route(
        "GET", "/repos/octocat/Hello%23World/pulls/158", github_json(_RECORDED["pull_request"])
    )
    _client().get_pull("octocat/Hello#World", 158)
    assert github_api.requested == [
        "GET https://api.github.com/repos/octocat/Hello%23World/pulls/158"
    ]


def test_the_files_of_a_pull_request_come_from_every_page(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The recorded listing links a second page: both files are read, in order, with the token."""
    _route_the_recorded_pull_request(github_api)
    files = _client().get_pull_files("octocat/Hello-World", 158)
    assert (files, github_api.requested, _carried(github_api)) == (
        [
            PullRequestFile(filename="README", status="removed", additions=0, changes=1),
            PullRequestFile(filename="README.md", status="added", additions=1, changes=1),
        ],
        [
            f"GET https://api.github.com{_FILES}",
            "GET https://api.github.com/repositories/1296269/pulls/158/files?per_page=1&page=2",
        ],
        {f"token {pin_github_session}"},
    )


def test_a_renamed_file_names_its_previous_path(github_api: GitHubApiFake) -> None:
    """GitHub sends `previous_filename` for a renamed file only."""
    renamed = {**_RECORDED["files_pages"][1]["body"][0], "status": "renamed"}
    renamed["previous_filename"] = "README"
    github_api.route("GET", _FILES, github_json([renamed]))
    assert _client().get_pull_files("octocat/Hello-World", 158) == [
        PullRequestFile(
            filename="README.md",
            status="renamed",
            previous_filename="README",
            additions=1,
            changes=1,
        )
    ]


def test_a_page_with_a_malformed_file_is_unread(github_api: GitHubApiFake) -> None:
    """A file without a status raises the unread error, so no list that misses it is returned."""
    github_api.route("GET", _FILES, github_json([{"filename": "README"}]))
    with pytest.raises(GitHubUnreadError) as raised:
        _client().get_pull_files("octocat/Hello-World", 158)
    assert raised.value.details["path"] == _FILES


def test_a_file_is_read_as_the_text_of_its_contents(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The contents endpoint is asked for the file at the commit, and its base64 is decoded."""
    github_api.route("GET", _README_AT_BASE, github_json(_README))
    text = _client().get_file_at("octocat/Hello-World", "README", _BASE_SHA)
    assert (text, github_api.requested, _carried(github_api)) == (
        "Hello World!\n",
        [f"GET https://api.github.com{_README_AT_BASE}"],
        {f"token {pin_github_session}"},
    )


def test_a_path_and_a_ref_are_encoded_in_the_request(github_api: GitHubApiFake) -> None:
    """A space in a path and a slash in a ref reach GitHub as one path and one ref."""
    github_api.route(
        "GET",
        "/repos/octocat/Hello-World/contents/docs/a%20b%23c.md?ref=feature%2Fx",
        github_json({**_README, "path": "docs/a b#c.md"}),
    )
    _client().get_file_at("octocat/Hello-World", "docs/a b#c.md", "feature/x")
    assert github_api.requested == [
        "GET https://api.github.com/repos/octocat/Hello-World/contents/docs/a%20b%23c.md"
        "?ref=feature%2Fx"
    ]


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(github_json(_RECORDED["missing_contents"], status=404), id="no-such-file"),
        pytest.param(github_json([{**_README, "type": "dir"}]), id="a-directory"),
        pytest.param(github_json({**_README, "type": "symlink"}), id="a-symlink"),
        pytest.param(github_json({**_README, "content": "", "encoding": "none"}), id="over-1-mb"),
        pytest.param(
            github_json({**_README, "content": base64.b64encode(b"\xff\xfe\x00").decode()}),
            id="not-utf-8",
        ),
    ],
)
def test_a_file_that_is_absent_binary_or_too_large_is_none(
    github_api: GitHubApiFake, answer: httpx2.Response
) -> None:
    """GitHub's 404, a directory listing, a link, a file over 1 MB (which comes without its
    content) and bytes that are not UTF-8 read as no text, as before."""
    github_api.route("GET", _README_AT_BASE, answer)
    assert _client().get_file_at("octocat/Hello-World", "README", _BASE_SHA) is None


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        pytest.param(
            github_json({"message": "Server Error"}, status=500), GitHubUnreadError, id="500"
        ),
        pytest.param(
            github_json({"message": "Bad credentials"}, status=401),
            GitHubUnauthenticatedError,
            id="401",
        ),
        pytest.param(
            github_json({**_README, "content": "SGVsbG8"}), GitHubUnreadError, id="base64"
        ),
        pytest.param(github_json("README"), GitHubUnreadError, id="not-a-file"),
    ],
)
def test_a_file_that_could_not_be_read_raises_instead_of_reading_as_absent(
    github_api: GitHubApiFake, answer: httpx2.Response, error: type[Exception]
) -> None:
    """A 500 that outlasts the retries, a refused token and a body that is no file raise the
    session's error: a failed read never looks like a file that is not there."""
    github_api.route("GET", _README_AT_BASE, answer)
    with pytest.raises(error) as raised:
        _client().get_file_at("octocat/Hello-World", "README", _BASE_SHA)
    assert str(raised.value) != "" or getattr(raised.value, "error_code", None) is not None


def test_the_merge_base_is_read_from_the_compare_endpoint(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The recorded comparison names the commit the pull request branched from, and asks for one
    commit only."""
    github_api.route("GET", _COMPARE, github_json(_RECORDED["comparison"]))
    merge_base = _client().get_merge_base("octocat/Hello-World", _BASE_SHA, _HEAD_SHA)
    assert (merge_base, github_api.requested, _carried(github_api)) == (
        _BASE_SHA,
        [f"GET https://api.github.com{_COMPARE}"],
        {f"token {pin_github_session}"},
    )


def test_a_comparison_github_does_not_find_has_no_merge_base(github_api: GitHubApiFake) -> None:
    """GitHub's 404 for two commits it cannot compare is no merge base."""
    assert _client().get_merge_base("octocat/Hello-World", _BASE_SHA, "unknown") is None


@pytest.mark.parametrize(
    ("answer", "error"),
    [
        pytest.param(
            github_json({"message": "Server Error"}, status=502), GitHubUnreadError, id="502"
        ),
        pytest.param(github_json({"status": "ahead"}), GitHubUnreadError, id="no-merge-base"),
    ],
)
def test_a_comparison_that_could_not_be_read_raises(
    github_api: GitHubApiFake, answer: httpx2.Response, error: type[Exception]
) -> None:
    """A 5xx that outlasts the retries, or a comparison without its merge base, is unread."""
    github_api.route("GET", _COMPARE, answer)
    with pytest.raises(error) as raised:
        _client().get_merge_base("octocat/Hello-World", _BASE_SHA, _HEAD_SHA)
    assert str(raised.value) != "" or getattr(raised.value, "error_code", None) is not None


def _listed_repositories() -> list[RepoInfo]:
    """The repositories of the recorded listing as the client reports them."""
    return [
        RepoInfo(
            name=repo["name"],
            full_name=repo["full_name"],
            ssh_url=repo["ssh_url"],
            clone_url=repo["clone_url"],
            private=repo["private"],
            fork=repo["fork"],
            archived=repo["archived"],
        )
        for repo in _REPOSITORIES["repositories"]
    ]


def test_the_repositories_of_an_organization_leave_out_forks_by_default(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """`GET /orgs/{org}/repos` lists every repository; the fork is left out unless asked for."""
    github_api.route("GET", _ORG_REPOS, github_json(_REPOSITORIES["repositories"]))
    client = _client()
    without_forks = client.get_org_repos("octocat")
    with_forks = client.get_org_repos("octocat", include_forks=True)
    everything = _listed_repositories()
    assert (without_forks, with_forks, github_api.requested, _carried(github_api)) == (
        [repo for repo in everything if not repo.fork],
        everything,
        [f"GET https://api.github.com{_ORG_REPOS}"] * 2,
        {f"token {pin_github_session}"},
    )


def test_an_organization_name_is_encoded_in_the_request(github_api: GitHubApiFake) -> None:
    """A slash or a query mark in the name stays inside the organization segment, so the name
    cannot reach another endpoint."""
    listing = "/orgs/a%2Fb%3Fc/repos?type=all&per_page=100"
    github_api.route("GET", listing, github_json([]))
    _client().get_org_repos("a/b?c")
    assert github_api.requested == [f"GET https://api.github.com{listing}"]


def test_a_public_listing_asks_for_public_repositories_only(github_api: GitHubApiFake) -> None:
    """Without private repositories the request names the public type, and a private one that
    still comes back is dropped."""
    private = {**_REPOSITORIES["repositories"][0], "name": "secret", "private": True}
    github_api.route(
        "GET",
        "/orgs/octocat/repos?type=public&per_page=100",
        github_json([private, *_REPOSITORIES["repositories"]]),
    )
    names = [repo.name for repo in _client().get_org_repos("octocat", include_private=False)]
    assert names == ["Hello-World", "Spoon-Knife"]


def test_archived_repositories_can_be_left_out(github_api: GitHubApiFake) -> None:
    """GitHub's `archived` flag decides which repositories `include_archived=False` drops."""
    archived = {**_REPOSITORIES["repositories"][2], "archived": True}
    github_api.route("GET", _ORG_REPOS, github_json([*_REPOSITORIES["repositories"][:2], archived]))
    names = [repo.name for repo in _client().get_org_repos("octocat", include_archived=False)]
    assert names == ["Hello-World"]


def test_the_account_of_the_session_lists_the_repositories_it_owns_when_it_is_no_organization(
    github_api: GitHubApiFake,
) -> None:
    """GitHub answers 404 for `/orgs/octocat/repos` since octocat is a user. When that user is the
    session's login, its owned repositories are listed instead, as `/user/repos`."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    github_api.route("GET", _USER_OWNED_REPOS, github_json(_REPOSITORIES["repositories"]))
    repos = _client().get_org_repos("octocat")
    assert ([repo.name for repo in repos], github_api.requested) == (
        ["Hello-World", "Spoon-Knife"],
        [
            f"GET https://api.github.com{_ORG_REPOS}",
            "GET https://api.github.com/user",
            f"GET https://api.github.com{_USER_OWNED_REPOS}",
        ],
    )


def test_another_account_that_is_no_organization_raises_the_not_found_error(
    github_api: GitHubApiFake,
) -> None:
    """A name that is not an organization and not the session's login is not listed from
    `/user/repos`: that listing would be the session's own repositories."""
    github_api.route("GET", "/user", github_json({"login": "somebody-else"}))
    with pytest.raises(GitHubNotFoundError) as raised:
        _client().get_org_repos("octocat")
    assert raised.value.error_code == "GITHUB_NOT_FOUND"
    assert "GET https://api.github.com" + _USER_OWNED_REPOS not in github_api.requested


def test_a_public_listing_of_the_sessions_own_account_asks_for_public_repositories(
    github_api: GitHubApiFake,
) -> None:
    """The fallback keeps the visibility the caller asked for."""
    github_api.route("GET", "/user", github_json({"login": "octocat"}))
    github_api.route(
        "GET",
        "/user/repos?affiliation=owner&visibility=public&per_page=100",
        github_json(_REPOSITORIES["repositories"]),
    )
    repos = _client().get_org_repos("octocat", include_private=False)
    assert [repo.name for repo in repos] == ["Hello-World", "Spoon-Knife"]


def test_an_issue_comment_is_posted_once_with_the_text_as_its_body(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """One `POST /repos/{repo}/issues/{n}/comments` carries the text as JSON, with the token."""
    github_api.route(
        "POST", "/repos/octocat/Hello-World/issues/158/comments", github_json({"id": 1}, status=201)
    )
    _client().create_issue_comment("octocat/Hello-World", 158, "Looks fine.")
    assert [
        (f"{request.method} {request.url.path}", json.loads(request.content))
        for request in github_api.sent
    ] == [("POST /repos/octocat/Hello-World/issues/158/comments", {"body": "Looks fine."})]
    assert _carried(github_api) == {f"token {pin_github_session}"}


def test_get_pr_diff_normal_and_redirect(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The diff is one session request, and a moved repository's redirect is followed with the
    session's token and the diff media type."""
    github_api.route(
        "GET",
        "/repos/octo/repo/pulls/42",
        github_text("diff --git a/foo b/foo\n+line", media_type=CONST_GITHUB_DIFF_MEDIA_TYPE),
    )
    github_api.route("GET", "/repos/octo/moved/pulls/7", github_redirect("/repositories/1/pulls/7"))
    github_api.route(
        "GET",
        "/repositories/1/pulls/7",
        github_text(
            "diff --git a/redirected b/redirected", media_type=CONST_GITHUB_DIFF_MEDIA_TYPE
        ),
    )
    client = _client()
    diffs = (client.get_pr_diff("octo/repo", 42), client.get_pr_diff("octo/moved", 7))
    carried = {(r.headers["accept"], r.headers["authorization"]) for r in github_api.sent}
    assert (diffs, github_api.requested, carried) == (
        ("diff --git a/foo b/foo\n+line", "diff --git a/redirected b/redirected"),
        [
            "GET https://api.github.com/repos/octo/repo/pulls/42",
            "GET https://api.github.com/repos/octo/moved/pulls/7",
            "GET https://api.github.com/repositories/1/pulls/7",
        ],
        {(CONST_GITHUB_DIFF_MEDIA_TYPE, f"token {pin_github_session}")},
    )


def test_get_pr_diff_empty_diff_returns_empty_string(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """A pull request with no changes returns an empty string, not an unread error (#1907)."""
    github_api.route(
        "GET",
        "/repos/octo/repo/pulls/42",
        github_text("", media_type=CONST_GITHUB_DIFF_MEDIA_TYPE),
    )
    assert _client().get_pr_diff("octo/repo", 42) == ""


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param(httpx2.Response(200, content=b"diff --git a/f b/f"), id="no-content-type"),
        pytest.param(github_json({"number": 42}), id="json"),
    ],
)
def test_an_answer_that_is_no_diff_raises_the_unread_error(
    github_api: GitHubApiFake, pin_github_session: str, answer: httpx2.Response
) -> None:
    """A diff GitHub did not send as text is unread, not an empty or stringified diff."""
    github_api.route("GET", "/repos/octo/repo/pulls/42", answer)
    with pytest.raises(GitHubUnreadError) as raised:
        _client().get_pr_diff("octo/repo", 42)
    assert raised.value.details["path"] == "/repos/octo/repo/pulls/42"


@pytest.fixture
def gh_process(process_fake: ProcessFake) -> ProcessFake:
    """A process fake answering rate limit checks with fresh quota."""
    fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
    process_fake.answer(
        ["gh", "api", "rate_limit"],
        ProcessAnswer(
            returncode=0,
            stdout=json.dumps({"resources": {"core": fresh_quota, "graphql": fresh_quota}}),
        ),
    )
    return process_fake


def _scripted_gh(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    """Answer `gh auth token` with token A, `gh api rate_limit` with a fresh quota, the rest empty."""
    fresh_quota = {"limit": 5000, "remaining": 5000, "reset": time.time() + 60}
    answers = {
        ("auth", "token"): "A\n",
        ("api", "rate_limit"): json.dumps(
            {"resources": {"core": fresh_quota, "graphql": fresh_quota}}
        ),
    }
    return subprocess.CompletedProcess(cmd, 0, stdout=answers.get(tuple(cmd[1:3]), "[]"), stderr="")


def test_one_identity_reaches_the_pr_diff_gh_and_the_quota_refresh(
    monkeypatch: pytest.MonkeyPatch,
    public_dns: str,
    pin_github_session: str,
) -> None:
    """The PR diff, two run_gh calls and the quota refresh all act as token A from `gh auth token`."""
    from unittest.mock import patch

    from devops_cli.core.process import reset_github_token
    from devops_cli.github.rate_limiter import run_gh
    from devops_cli.github.session import get_github_session
    from tests.support.fakes.github import GitHubApiFake
    from tests.web_fakes import install_async_client_fake

    api = GitHubApiFake()
    install_async_client_fake(monkeypatch, api.client_class())
    reset_github_token()
    monkeypatch.setenv("GITHUB_TOKEN", "C")
    api.route(
        "GET",
        "https://api.github.com/repos/octo/repo/pulls/42",
        github_text("diff --git a/f b/f", media_type=CONST_GITHUB_DIFF_MEDIA_TYPE),
    )
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
    github_requests = [request for request in api.sent if request.url.host == "api.github.com"]
    assert (diff, [request.headers["authorization"] for request in github_requests], children) == (
        "diff --git a/f b/f",
        ["token A"],
        [
            (["auth", "token"], None, "C"),
            (["api", "rate_limit"], "A", None),
            (["issue", "list"], "A", None),
            (["label", "list"], "A", None),
        ],
    )


def test_gh_cli_client_labels(gh_process: ProcessFake) -> None:
    """Verify GhCliClient label listing, creation, and editing commands."""
    client = GhCliClient(default_repo="owner/my-repo")
    gh_process.answer(
        ["gh", "label", "list"],
        ProcessAnswer(stdout='[{"name": "bug", "color": "d73a4a", "description": "Bug fix"}]'),
    )
    gh_process.answer(["gh", "label", "create"], ProcessAnswer(stdout=""))
    gh_process.answer(["gh", "label", "edit"], ProcessAnswer(stdout=""))

    labels = client.get_labels("owner/my-repo")
    assert len(labels) == 1
    assert labels[0]["name"] == "bug"
    assert gh_process.calls[-1].argv[:4] == ("gh", "label", "list", "--json")

    client.create_label("owner/my-repo", "feature", "#0e8a16", "New feature")
    create_cmd = gh_process.calls[-1].argv
    assert create_cmd[:4] == ("gh", "label", "create", "feature")
    assert "--color" in create_cmd
    assert "0e8a16" in create_cmd

    client.edit_label("owner/my-repo", "feature", "0075ca", "Updated desc")
    edit_cmd = gh_process.calls[-1].argv
    assert edit_cmd[:4] == ("gh", "label", "edit", "feature")
    assert "0075ca" in edit_cmd


def test_gh_cli_client_label_failures_raise(gh_process: ProcessFake) -> None:
    """A failed `gh label` call raises instead of reading as no labels or as done (#961).

    `get_labels` returned [] on any failure, so `labels sync` set out to create every label,
    and `create_label` and `edit_label` dropped the result, so their failures went unseen.
    """
    from devops_cli.exceptions.git import GitHubOperationError

    client = GhCliClient(default_repo="o/r")
    gh_process.answer(
        ["gh", "label"], ProcessAnswer(returncode=1, stdout="", stderr="not logged in")
    )
    calls = [
        lambda: client.get_labels("o/r"),
        lambda: client.create_label("o/r", "x", "000000"),
        lambda: client.edit_label("o/r", "x", "000000"),
    ]
    raised: list[str] = []
    for call in calls:
        with pytest.raises(GitHubOperationError) as error:
            call()
        raised.append(str(error.value))
    assert all("not logged in" in message for message in raised)


def test_gh_cli_client_lists_every_label(gh_process: ProcessFake) -> None:
    """`gh label list` stops at 30 labels unless told otherwise; .github/labels.yml has 31."""
    gh_process.answer(["gh", "label", "list"], ProcessAnswer(returncode=0, stdout="[]"))
    GhCliClient(default_repo="o/r").get_labels("o/r")
    argv = gh_process.calls[-1].argv
    # Without --limit, gh lists 30.
    assert (int(argv[argv.index("--limit") + 1]) if "--limit" in argv else 30) > 30


def test_parse_paginated_json() -> None:
    """Verify parse_paginated_json handles empty strings, lists, dicts, and concatenated arrays."""
    from devops_cli.github.client import parse_paginated_json

    assert parse_paginated_json("") == []
    assert parse_paginated_json("   ") == []
    assert parse_paginated_json("not json") == []
    assert parse_paginated_json('[{"id": 1}]') == [{"id": 1}]
    assert parse_paginated_json('{"id": 2}') == [{"id": 2}]
    concatenated = '[{"id": 1}, {"id": 2}]\n[{"id": 3}]'
    assert parse_paginated_json(concatenated) == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_gh_cli_client_api_paginate(gh_process: ProcessFake) -> None:
    """GhCliClient.api adds --paginate and sets paginate timeout when requested."""
    from devops_cli.config.defaults import DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS

    gh_process.answer(
        ["gh", "api", "--paginate", "repos/owner/repo/issues"],
        ProcessAnswer(returncode=0, stdout='[{"id": 1}]'),
    )
    res = GhCliClient().api("repos/owner/repo/issues", paginate=True)
    assert res == '[{"id": 1}]'
    call = gh_process.calls[-1]
    assert call.argv == ("gh", "api", "--paginate", "repos/owner/repo/issues")
    assert call.timeout == DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS


_SEARCHED_REPO = "octo/repo"
_SEARCHED_PHRASE = "devops-review-finding"


def _search_page_path(page: int) -> str:
    """The search request of page `page` for the phrase in the bodies of the repository's issues."""
    query = f'"{_SEARCHED_PHRASE}" in:body is:issue repo:{_SEARCHED_REPO}'
    return f"/search/issues?{urlencode({'q': query, 'per_page': 100, 'page': page})}"


def _search_answer(numbers: range, *, total: int, incomplete: bool = False) -> httpx2.Response:
    """A page of issue search results, one open issue for each number, with the search quota."""
    items = [{"number": n, "state": "open", "state_reason": None, "body": f"#{n}"} for n in numbers]
    payload = {"total_count": total, "incomplete_results": incomplete, "items": items}
    return github_json(payload, headers=quota_headers(29, resource="search", limit=30))


@pytest.fixture
def search_quota(github_api: GitHubApiFake) -> GitHubApiFake:
    """The fake GitHub API with a fresh search quota, so pacing never refreshes it through gh."""
    get_github_rate_limiter().update_quota(
        "search", remaining=30, limit=30, reset_epoch=time.time() + 60.0
    )
    return github_api


def test_an_issue_search_is_read_from_every_page(search_quota: GitHubApiFake) -> None:
    """101 results come as a page of 100 and a page of 1, and both pages are read (#2419)."""
    search_quota.route("GET", _search_page_path(1), _search_answer(range(1, 101), total=101))
    search_quota.route("GET", _search_page_path(2), _search_answer(range(101, 102), total=101))

    hits = _client().search_issue_bodies(_SEARCHED_REPO, _SEARCHED_PHRASE)

    assert (
        [hit.number for hit in hits],
        {(hit.state, hit.state_reason) for hit in hits},
        search_quota.requested,
    ) == (
        list(range(1, 102)),
        {("open", None)},
        [f"GET {API}{_search_page_path(1)}", f"GET {API}{_search_page_path(2)}"],
    )


@pytest.mark.parametrize(
    ("total", "incomplete"),
    [(1, True), (1001, False)],
    ids=["incomplete", "past_the_result_cap"],
)
def test_an_issue_search_that_is_not_complete_is_unread(
    search_quota: GitHubApiFake, total: int, incomplete: bool
) -> None:
    """A page GitHub marks incomplete, or more results than search returns, is never read as all
    of them (#2419)."""
    answer = _search_answer(range(1, 2), total=total, incomplete=incomplete)
    search_quota.route("GET", _search_page_path(1), answer)

    with pytest.raises(GitHubUnreadError) as raised:
        _client().search_issue_bodies(_SEARCHED_REPO, _SEARCHED_PHRASE)

    assert (raised.value.details["path"], len(search_quota.requested)) == (_search_page_path(1), 1)


def test_a_draft_pull_request_is_opened_with_the_draft_flag(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    """The request carries the title, the body, both branches and `draft`, and the answer gives
    the number and the page of the new pull request (#2654)."""
    github_api.route(
        "POST",
        "/repos/octocat/Hello-World/pulls",
        github_json({"number": 9, "html_url": "https://example.com/pull/9"}, status=201),
    )

    created = _client().create_draft_pull(
        "octocat/Hello-World", title="fix: a title", body="Plans #1", head="fix/1-a", base="main"
    )

    assert (created.number, created.html_url) == (9, "https://example.com/pull/9")
    assert github_api.requested == [f"POST {API}/repos/octocat/Hello-World/pulls"]
    assert json.loads(github_api.sent[0].content) == {
        "title": "fix: a title",
        "body": "Plans #1",
        "head": "fix/1-a",
        "base": "main",
        "draft": True,
    }


def test_a_pull_request_is_closed_with_a_state_change(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    github_api.route("PATCH", "/repos/octocat/Hello-World/pulls/9", github_json({"number": 9}))

    _client().close_pull("octocat/Hello-World", 9)

    assert github_api.requested == [f"PATCH {API}/repos/octocat/Hello-World/pulls/9"]
    assert json.loads(github_api.sent[0].content) == {"state": "closed"}


@pytest.mark.parametrize(
    ("payload", "open_draft"),
    [
        ({"state": "open", "draft": True, "merged": False}, True),
        ({"state": "open", "draft": False, "merged": False}, False),
        ({"state": "closed", "draft": True, "merged": False}, False),
        ({"state": "closed", "draft": False, "merged": True}, False),
    ],
)
def test_a_pull_request_status_says_whether_it_is_an_open_draft(
    github_api: GitHubApiFake, pin_github_session: str, payload: dict[str, Any], open_draft: bool
) -> None:
    github_api.route("GET", "/repos/octocat/Hello-World/pulls/9", github_json(payload))

    status = _client().get_pull_status("octocat/Hello-World", 9)

    assert (status.state, status.merged, status.is_open_draft) == (
        payload["state"],
        payload["merged"],
        open_draft,
    )


def test_a_pull_request_status_gives_the_commit_of_its_head(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    payload = {"state": "open", "draft": True, "merged": False, "head": {"sha": "abc123"}}
    github_api.route("GET", "/repos/octocat/Hello-World/pulls/9", github_json(payload))

    status = _client().get_pull_status("octocat/Hello-World", 9)

    assert status.head_sha == "abc123"


def test_the_title_and_the_body_of_a_pull_request_are_set_with_one_patch(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    github_api.route("PATCH", "/repos/octocat/Hello-World/pulls/9", github_json({"number": 9}))

    _client().update_pull(
        "octocat/Hello-World", 9, title="fix(config): report an error", body="Closes #1"
    )

    assert github_api.requested == [f"PATCH {API}/repos/octocat/Hello-World/pulls/9"]
    assert json.loads(github_api.sent[0].content) == {
        "title": "fix(config): report an error",
        "body": "Closes #1",
    }


def test_a_comment_on_a_pull_request_goes_to_its_issue(
    github_api: GitHubApiFake, pin_github_session: str
) -> None:
    github_api.route(
        "POST", "/repos/octocat/Hello-World/issues/9/comments", github_json({"id": 1}, status=201)
    )

    _client().comment_on_pull("octocat/Hello-World", 9, "Step 1 passed.")

    assert github_api.requested == [f"POST {API}/repos/octocat/Hello-World/issues/9/comments"]
    assert json.loads(github_api.sent[0].content) == {"body": "Step 1 passed."}
