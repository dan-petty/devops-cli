"""The typed GitHub calls devops-cli makes through the GitHub session, and the gh label client."""

from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode

from pydantic import AliasPath, BaseModel, ConfigDict, Field, ValidationError

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GITHUB_DIFF_MEDIA_TYPE,
    CONST_GITHUB_SEARCH_MAX_RESULTS,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import (
    DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS,
    DEFAULT_GH_LABEL_LIST_LIMIT,
    DEFAULT_GH_REST_PER_PAGE,
    DEFAULT_GH_SUBPROCESS_TIMEOUT_SECONDS,
)
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


class PullStatus(BaseModel):
    """Whether a pull request is open, a draft, or merged (#2665), and the commit of its head
    (#2865). `head_sha` is empty when GitHub names no head."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    state: str
    draft: bool = False
    merged: bool = False
    head_sha: str = Field(default="", validation_alias=AliasPath("head", "sha"))

    @property
    def is_open_draft(self) -> bool:
        """Whether the pull request is open and still a draft."""
        return self.state == "open" and self.draft


class PullRequestFile(BaseModel):
    """One file a pull request changes; `previous_filename` is set for a renamed file only."""

    filename: str
    status: str
    previous_filename: str | None = None
    additions: int = 0
    changes: int = 0


class CommitPull(BaseModel):
    """A pull request that GitHub associates with a commit: whether it merged, and the commit it
    ended on. `merged_at` is None for a pull request that is open or was closed unmerged."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    number: int
    merged_at: str | None = None
    head_sha: str = Field(validation_alias=AliasPath("head", "sha"))


class CreatedPull(BaseModel):
    """A pull request that GitHub made: its number and the address of its page."""

    number: int
    html_url: str


class IssueSearchHit(BaseModel):
    """One issue that an issue search found: its number, its state, why it was closed (None while
    it is open), and its body, which GitHub gives as null when it is empty."""

    number: int
    state: str
    state_reason: str | None = None
    body: str | None = None


class _IssueSearchPage(BaseModel):
    """A page of GitHub's issue search: the results of the whole search, whether the search timed
    out before it found them all, and this page's issues."""

    total_count: int
    incomplete_results: bool
    items: list[IssueSearchHit]


class JobRunTime(BaseModel):
    """How long a job took in one workflow run, from its start to its end (#2699)."""

    run_id: int
    seconds: float


# The conclusions of a job that ran to an end: it passed, failed, or hit its time limit. A skipped or
# cancelled job did not run its work, so its time says nothing of the job.
_JOB_ENDED_CONCLUSIONS = frozenset({"success", "failure", "timed_out"})


class _WorkflowRunRef(BaseModel):
    """The run of a workflow listing that devops-cli reads: its number."""

    id: int


class _JobTiming(BaseModel):
    """One job of a run: its name, how it ended, and when it started and ended."""

    name: str
    conclusion: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @property
    def seconds(self) -> float | None:
        """The seconds from start to end; None for a job that has not both."""
        if self.started_at is None or self.completed_at is None:
            return None
        return (self.completed_at - self.started_at).total_seconds()


class _RunJobs(BaseModel):
    """What the jobs endpoint says of a run."""

    jobs: list[_JobTiming]


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


def _short_search_reason(page: _IssueSearchPage) -> str | None:
    """Why the search's pages cannot hold all of its results, or None when they can: GitHub
    marked the page incomplete, or the search has more results than GitHub returns."""
    if page.incomplete_results:
        return "GitHub marked the search incomplete"
    if page.total_count > CONST_GITHUB_SEARCH_MAX_RESULTS:
        return (
            f"the search has {page.total_count} results, and GitHub returns "
            f"{CONST_GITHUB_SEARCH_MAX_RESULTS} at most"
        )
    return None


def _refuse_a_short_search(page: _IssueSearchPage, *, path: str) -> None:
    """Raise `GitHubUnreadError` naming `path` when the search's pages cannot hold all of its
    results."""
    reason = _short_search_reason(page)
    if reason is None:
        return
    bounded = path[:CONST_MAX_ERROR_DETAIL_LENGTH]
    raise GitHubUnreadError(
        f"GitHub's answer to GET {bounded} is not every result: {reason}",
        details={"path": bounded, "total_count": page.total_count},
    )


def org_repos_path(org_name: str, *, include_private: bool = True) -> str:
    """The listing of the repositories of an organization, as `get_org_repos` reads it."""
    visibility = "all" if include_private else "public"
    return f"/orgs/{quote(org_name, safe='')}/repos?type={visibility}&per_page={DEFAULT_GH_REST_PER_PAGE}"


def own_repos_path(*, include_private: bool = True) -> str:
    """The listing of the repositories that the session's own account owns, the fallback of
    `get_org_repos` when the organization is the account's login."""
    visibility = "all" if include_private else "public"
    return (
        f"/user/repos?affiliation=owner&visibility={visibility}&per_page={DEFAULT_GH_REST_PER_PAGE}"
    )


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
        listed_from = org_repos_path(org_name, include_private=include_private)
        try:
            listing = list(self._session.paginate(listed_from))
        except GitHubNotFoundError:
            if org_name != self._session.login:
                raise
            listed_from = own_repos_path(include_private=include_private)
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

    def create_draft_pull(
        self, repo: str, *, title: str, body: str, head: str, base: str
    ) -> CreatedPull:
        """Open a draft pull request from the branch `head` into `base` (#2654)."""
        path = _repo_path(repo, "pulls")
        payload = {"title": title, "body": body, "head": head, "base": base, "draft": True}
        return _read_as(CreatedPull, self._session.rest("POST", path, body=payload), path=path)

    def get_pull_status(self, repo: str, number: int) -> PullStatus:
        """The state, the draft flag, the merge flag and the head commit of the pull request `number`
        (#2665, #2865)."""
        path = _repo_path(repo, f"pulls/{number}")
        return _read_as(PullStatus, self._session.rest("GET", path), path=path)

    def update_pull(self, repo: str, number: int, *, title: str, body: str) -> None:
        """Set the title and the body of the pull request `number` (#2665, #2714)."""
        path = _repo_path(repo, f"pulls/{number}")
        self._session.rest("PATCH", path, body={"title": title, "body": body})

    def comment_on_pull(self, repo: str, number: int, body: str) -> None:
        """Comment `body` on the pull request `number`. GitHub keeps the comments of a pull
        request on its issue (#2665)."""
        path = _repo_path(repo, f"issues/{number}/comments")
        self._session.rest("POST", path, body={"body": body})

    def close_pull(self, repo: str, number: int) -> None:
        """Close the pull request `number` without a merge."""
        path = _repo_path(repo, f"pulls/{number}")
        self._session.rest("PATCH", path, body={"state": "closed"})

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

    def get_commit_pulls(self, repo: str, sha: str) -> list[CommitPull]:
        """Every pull request that GitHub associates with the commit `sha`, merged or not.

        A squash merge leaves the head of the pull request out of the base branch, and GitHub
        still lists the pull request for that commit. HTTP 422 is GitHub's answer for a commit it
        does not hold, such as one that was never pushed, and reads as no pull request: any other
        failure raises the session's error.
        """
        path = _repo_path(
            repo, f"commits/{quote(sha, safe='')}/pulls?per_page={DEFAULT_GH_REST_PER_PAGE}"
        )
        try:
            listing = list(self._session.paginate(path))
        except GitHubOperationError as exc:
            if exc.details.get("status") == HTTPStatus.UNPROCESSABLE_ENTITY:
                return []
            raise
        return [_read_as(CommitPull, item, path=path) for item in listing]

    def search_issue_bodies(self, repo: str, phrase: str) -> list[IssueSearchHit]:
        """Every issue of `repo`, open or closed, whose body holds `phrase`, from GitHub's issue
        search. Search finds text inside an HTML comment of a body too (#2419).

        The pages are read by number, 100 issues a page, while the search has more results. A page
        that GitHub marks `incomplete_results`, or a search with more results than search returns
        (`CONST_GITHUB_SEARCH_MAX_RESULTS`), raises `GitHubUnreadError`: a short answer never
        reads as all of them. `GitHubSession.paginate` gives only the items, so it cannot tell.
        """
        query = f'"{phrase}" in:body is:issue repo:{repo}'
        per_page = DEFAULT_GH_REST_PER_PAGE
        hits: list[IssueSearchHit] = []
        for number in range(1, CONST_GITHUB_SEARCH_MAX_RESULTS // per_page + 1):
            path = f"/search/issues?{urlencode({'q': query, 'per_page': per_page, 'page': number})}"
            page = _read_as(_IssueSearchPage, self._session.rest("GET", path), path=path)
            _refuse_a_short_search(page, path=path)
            hits.extend(page.items)
            if len(hits) >= page.total_count or len(page.items) < per_page:
                break
        return hits

    def get_job_run_times(
        self, repo: str, *, workflow: str, branch: str, job: str, count: int
    ) -> list[JobRunTime]:
        """How long `job` took in each of the last `count` completed `push` runs of `workflow` on
        `branch` where it ran to an end, newest first (#2699).

        The job's own conclusion decides, not the run's. A job that ended `success`, `failure` or
        `timed_out` counts, so a run that failed for another job, such as the guard that reads
        this time, still gives the time of the job. A run that has no job of that name, or whose
        job was skipped or cancelled, is left out. The listing is read page by page and stops once
        `count` runs hold the job, so the jobs of no later run are asked for. Fewer than `count`
        come back when the workflow has fewer such runs.
        """
        query = urlencode(
            {
                "branch": branch,
                "event": "push",
                "status": "completed",
                "per_page": DEFAULT_GH_REST_PER_PAGE,
            }
        )
        listing = _repo_path(repo, f"actions/workflows/{quote(workflow, safe='')}/runs?{query}")
        times: list[JobRunTime] = []
        for item in self._session.paginate(listing, iterable_key="workflow_runs"):
            run = _read_as(_WorkflowRunRef, item, path=listing)
            seconds = self._job_seconds(repo, run.id, job)
            if seconds is not None:
                times.append(JobRunTime(run_id=run.id, seconds=seconds))
            if len(times) >= count:
                break
        return times

    def _job_seconds(self, repo: str, run_id: int, job: str) -> float | None:
        """The seconds the job `job` took in the run `run_id`; None if it did not run to an end."""
        path = _repo_path(repo, f"actions/runs/{run_id}/jobs?per_page={DEFAULT_GH_REST_PER_PAGE}")
        jobs = _read_as(_RunJobs, self._session.rest("GET", path), path=path).jobs
        return next(
            (j.seconds for j in jobs if j.name == job and j.conclusion in _JOB_ENDED_CONCLUSIONS),
            None,
        )

    def create_issue_comment(self, repo: str, number: int, body: str) -> None:
        """Post `body` as a comment on the issue or pull request `number`."""
        path = _repo_path(repo, f"issues/{number}/comments")
        self._session.rest("POST", path, body={"body": body})

    def get_pr_diff(self, repo: str, number: int) -> str:
        """The pull request's unified diff, read through the GitHub session.

        GitHub sends a diff as text; any other answer, JSON or a body without a content type,
        raises `GitHubUnreadError`. A pull request with no changes returns an empty string.
        """
        path = _repo_path(repo, f"pulls/{number}")
        diff = self._session.rest("GET", path, accept=CONST_GITHUB_DIFF_MEDIA_TYPE)
        if not isinstance(diff, str):
            raise GitHubUnreadError(
                f"GitHub's answer to GET {path} is no diff: {type(diff).__name__}",
                details={"path": path[:CONST_MAX_ERROR_DETAIL_LENGTH]},
            )
        return diff


def parse_paginated_json(text: str) -> list[dict[str, Any]]:
    """Parse one or multiple concatenated JSON documents or arrays from gh api --paginate."""
    cleaned = text.strip()
    if not cleaned:
        return []
    decoder = json.JSONDecoder()
    items: list[dict[str, Any]] = []
    idx = 0
    length = len(cleaned)
    while idx < length:
        while idx < length and cleaned[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            obj, end_idx = decoder.raw_decode(cleaned, idx)
            idx = end_idx
            if isinstance(obj, list):
                items.extend(item for item in obj if isinstance(item, dict))
            elif isinstance(obj, dict):
                items.append(obj)
        except json.JSONDecodeError:
            break
    return items


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

    def api(self, endpoint: str, paginate: bool = False) -> str:
        """Execute a GitHub API request via rate-managed run_gh."""
        cmd = [CONST_GH_CLI, "api"]
        if paginate:
            cmd.append("--paginate")
        cmd.append(endpoint)
        timeout = (
            DEFAULT_GH_API_PAGINATE_TIMEOUT_SECONDS
            if paginate
            else DEFAULT_GH_SUBPROCESS_TIMEOUT_SECONDS
        )
        res = run_gh(cmd, check=False, quiet=True, timeout=timeout)
        if res.returncode != 0:
            raise GitHubOperationError(
                f"gh api call failed with exit code {res.returncode}: {res.stderr.strip()}",
                operation="gh_api",
                details={"endpoint": endpoint, "stderr": res.stderr[:256]},
            )
        return res.stdout
