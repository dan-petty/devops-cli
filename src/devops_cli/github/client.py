"""The typed GitHub calls devops-cli makes through the GitHub session, and the gh label client."""

from __future__ import annotations

import base64
import binascii
import json
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode

from pydantic import AliasPath, BaseModel, ConfigDict, Field, ValidationError

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GITHUB_DIFF_MEDIA_TYPE,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import DEFAULT_GH_LABEL_LIST_LIMIT, DEFAULT_GH_REST_PER_PAGE
from devops_cli.exceptions.git import GitHubNotFoundError, GitHubOperationError, GitHubUnreadError
from devops_cli.github.rate_limiter import run_gh

if TYPE_CHECKING:
    from devops_cli.github.session import GitHubSession


class RepoInfo(BaseModel):
    name: str
    full_name: str
    ssh_url: str
    clone_url: str
    private: bool
    fork: bool
    archived: bool


class CommitRef(BaseModel):
    """One side of a pull request: a commit, the branch it is on and the repository that holds it.

    `repository` is the repository's full name, or None when GitHub reports the repository as
    null, which it does for the head of a pull request whose fork was deleted.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    sha: str
    ref: str
    repository: str | None = Field(default=None, validation_alias=AliasPath("repo", "full_name"))


class PullRequest(BaseModel):
    """The fields of a pull request that devops-cli reads."""

    title: str
    head: CommitRef
    base: CommitRef


class PullRequestFile(BaseModel):
    """One file a pull request changes; `previous_filename` is set for a renamed file only."""

    filename: str
    status: str
    previous_filename: str | None = None
    additions: int
    changes: int


class _FileContents(BaseModel):
    """What the contents endpoint says of a path that is not a directory: GitHub gives a file its
    content in base64, and one over 1 MB an empty content with the encoding `none`."""

    type: str
    encoding: str = ""
    content: str = ""


class _Comparison(BaseModel):
    """What the compare endpoint says of two commits that devops-cli reads: their merge base."""

    merge_base: str = Field(validation_alias=AliasPath("merge_base_commit", "sha"))


def _read_as[M: BaseModel](model: type[M], answer: Any, *, path: str) -> M:
    """`answer` as a `model`, raising `GitHubUnreadError` naming `path` when it is none."""
    try:
        return model.model_validate(answer)
    except ValidationError as exc:
        bounded = path[:CONST_MAX_ERROR_DETAIL_LENGTH]
        raise GitHubUnreadError(
            f"GitHub's answer to GET {bounded} is no {model.__name__}: "
            f"{exc.error_count()} invalid field(s)",
            details={"path": bounded},
        ) from exc


def _repo_path(repo: str, tail: str) -> str:
    """The REST path of `tail` under `repo`, with a character that is no part of a path encoded."""
    return f"/repos/{quote(repo, safe='/')}/{tail}"


class GitHubClient:
    """The typed calls devops-cli makes to GitHub, each one a request of the session it holds (#891).

    The session paces, charges and retries every request and names every failure with its error
    class, so a call here returns what GitHub said or raises why it did not.
    """

    def __init__(self, session: GitHubSession) -> None:
        self._session = session

    def get_org_repos(
        self,
        org_name: str,
        include_private: bool = True,
        include_forks: bool = False,
        include_archived: bool = True,
    ) -> list[RepoInfo]:
        """The repositories of an organization, or of the session's own account when GitHub says
        `org_name` is no organization and it is the account's login (the ones it owns)."""
        visibility = "all" if include_private else "public"
        per_page = f"per_page={DEFAULT_GH_REST_PER_PAGE}"
        listed_from = f"/orgs/{quote(org_name, safe='')}/repos?type={visibility}&{per_page}"
        try:
            listing = list(self._session.paginate(listed_from))
        except GitHubNotFoundError:
            if org_name != self._session.login:
                raise
            listed_from = f"/user/repos?affiliation=owner&visibility={visibility}&{per_page}"
            listing = list(self._session.paginate(listed_from))
        repos = [_read_as(RepoInfo, item, path=listed_from) for item in listing]
        return [
            repo
            for repo in repos
            if (include_private or not repo.private)
            and (include_forks or not repo.fork)
            and (include_archived or not repo.archived)
        ]

    # ── Pull requests ─────────────────────────────────────────────────────────

    def get_pull(self, repo: str, number: int) -> PullRequest:
        """The pull request's title, and the commit, branch and repository of its head and base."""
        path = _repo_path(repo, f"pulls/{number}")
        return _read_as(PullRequest, self._session.rest("GET", path), path=path)

    def get_pull_files(self, repo: str, number: int) -> list[PullRequestFile]:
        """Every file the pull request changes, read page by linked page."""
        path = _repo_path(repo, f"pulls/{number}/files?per_page={DEFAULT_GH_REST_PER_PAGE}")
        return [_read_as(PullRequestFile, item, path=path) for item in self._session.paginate(path)]

    def get_file_at(self, repo: str, path: str, ref: str) -> str | None:
        """A file's text at a commit; None when it is absent, binary or too large to fetch.

        Only what GitHub says of the path reads as None: a 404, a directory, a link or submodule,
        a file over 1 MB and bytes that are not UTF-8. A request that fails otherwise, or an
        answer that is no file, raises the session's error.
        """
        endpoint = _repo_path(repo, f"contents/{quote(path, safe='/')}?{urlencode({'ref': ref})}")
        try:
            answer = self._session.rest("GET", endpoint)
        except GitHubNotFoundError:
            return None
        if isinstance(answer, list):
            return None
        contents = _read_as(_FileContents, answer, path=endpoint)
        if contents.type != "file" or contents.encoding != "base64":
            return None
        try:
            return base64.b64decode(contents.content).decode("utf-8")
        except UnicodeDecodeError:
            return None
        except binascii.Error as exc:
            raise GitHubUnreadError(
                f"GitHub's answer to GET {endpoint[:CONST_MAX_ERROR_DETAIL_LENGTH]} is not base64",
                details={"path": endpoint[:CONST_MAX_ERROR_DETAIL_LENGTH]},
            ) from exc

    def get_merge_base(self, repo: str, base: str, head: str) -> str | None:
        """The merge base of two commits from the compare endpoint; None when GitHub has none.

        A pull request's `base.sha` is the base branch's tip, which moves on after the branch
        point; its diff starts here instead. Only a 404 reads as None: any other failure raises
        the session's error.
        """
        endpoint = _repo_path(repo, f"compare/{quote(base)}...{quote(head)}?per_page=1")
        try:
            comparison = self._session.rest("GET", endpoint)
        except GitHubNotFoundError:
            return None
        return _read_as(_Comparison, comparison, path=endpoint).merge_base

    def create_issue_comment(self, repo: str, number: int, body: str) -> None:
        """Post `body` as a comment on the issue or pull request `number`."""
        path = _repo_path(repo, f"issues/{number}/comments")
        self._session.rest("POST", path, body={"body": body})

    def get_pr_diff(self, repo: str, number: int) -> str:
        """The pull request's unified diff, read through the GitHub session.

        GitHub sends a diff as text; any other answer, JSON or a body without a content type,
        raises `GitHubUnreadError`.
        """
        path = _repo_path(repo, f"pulls/{number}")
        diff = self._session.rest("GET", path, accept=CONST_GITHUB_DIFF_MEDIA_TYPE)
        if not isinstance(diff, str):
            raise GitHubUnreadError(
                f"GitHub's answer to GET {path} is no diff: {type(diff).__name__}",
                details={"path": path[:CONST_MAX_ERROR_DETAIL_LENGTH]},
            )
        return diff


class GhCliClient:
    """GitHub client backed by the gh CLI tool for local operations without raw PATs."""

    def __init__(self, default_repo: str | None = None) -> None:
        self.default_repo = default_repo

    def _run_label_command(self, cmd: list[str], *, quiet: bool = False) -> str:
        """Run a `gh label` subcommand and return its output, raising when gh fails."""
        res = run_gh(cmd, check=False, quiet=quiet)
        if res.returncode != 0:
            stderr = res.stderr.strip()[:CONST_MAX_ERROR_DETAIL_LENGTH]
            raise GitHubOperationError(
                f"gh label {cmd[2]} failed with exit code {res.returncode}: {stderr}",
                operation=f"gh_label_{cmd[2]}",
                details={"stderr": stderr},
            )
        return res.stdout

    def get_labels(self, repo: str) -> list[dict[str, Any]]:
        target_repo = repo or self.default_repo or ""
        cmd = [
            CONST_GH_CLI,
            "label",
            "list",
            "--json",
            "name,color,description",
            "--limit",
            str(DEFAULT_GH_LABEL_LIST_LIMIT),
        ]
        if target_repo:
            cmd.extend(["--repo", target_repo])
        stdout = self._run_label_command(cmd, quiet=True)
        if not stdout.strip():
            return []
        try:
            return json.loads(stdout)  # type: ignore[no-any-return]
        except json.JSONDecodeError as exc:
            raise GitHubOperationError(
                f"gh label list returned output that is not JSON: {exc}",
                operation="gh_label_list",
            ) from exc

    def create_label(self, repo: str, name: str, color: str, description: str = "") -> None:
        target_repo = repo or self.default_repo or ""
        cmd = [
            CONST_GH_CLI,
            "label",
            "create",
            name,
            "--color",
            color.lstrip("#"),
            "--description",
            description,
        ]
        if target_repo:
            cmd.extend(["--repo", target_repo])
        self._run_label_command(cmd)

    def edit_label(self, repo: str, name: str, color: str, description: str = "") -> None:
        target_repo = repo or self.default_repo or ""
        cmd = [
            CONST_GH_CLI,
            "label",
            "edit",
            name,
            "--color",
            color.lstrip("#"),
            "--description",
            description,
        ]
        if target_repo:
            cmd.extend(["--repo", target_repo])
        self._run_label_command(cmd)

    def api(self, endpoint: str) -> str:
        """Execute a GitHub API request via rate-managed run_gh."""
        res = run_gh([CONST_GH_CLI, "api", endpoint], check=False, quiet=True)
        if res.returncode != 0:
            raise GitHubOperationError(
                f"gh api call failed with exit code {res.returncode}: {res.stderr.strip()}",
                operation="gh_api",
                details={"endpoint": endpoint, "stderr": res.stderr[:256]},
            )
        return res.stdout
