"""GitHub API client wrapping PyGithub."""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import TYPE_CHECKING, Any

import httpx2
from pydantic import BaseModel

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_MAX_ERROR_DETAIL_LENGTH,
    CONST_URL_GITHUB_API_BASE,
)
from devops_cli.config.defaults import DEFAULT_GH_LABEL_LIST_LIMIT, DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.models.ssh import SSHKeyInfo

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from github.PullRequest import PullRequest

    from devops_cli.github.graphql import GitHubGraphQLClient


class RepoInfo(BaseModel):
    name: str
    full_name: str
    ssh_url: str
    clone_url: str
    private: bool
    fork: bool
    archived: bool


class GitHubClient:
    def __init__(self, token: str) -> None:
        from github import Auth, Github

        from devops_cli.github.graphql import GitHubGraphQLClient

        self._token = token
        self._gh = Github(auth=Auth.Token(token))
        self._graphql = GitHubGraphQLClient(token=token)

    @property
    def graphql(self) -> GitHubGraphQLClient:
        """Access high-performance GraphQL client with batching and ETag caching."""
        return self._graphql

    def get_repo_overview(
        self,
        repo: str,
        issues_limit: int = 50,
        prs_limit: int = 50,
        milestones_limit: int = 20,
    ) -> Any:
        """Fetch repository overview (issues, PRs, milestones, rate limit) in a single GraphQL call."""
        if "/" in repo:
            owner, name = repo.split("/", 1)
        else:
            owner = self._gh.get_user().login
            name = repo
        try:
            return self._graphql.fetch_repo_overview(
                owner=owner,
                repo=name,
                issues_limit=issues_limit,
                prs_limit=prs_limit,
                milestones_limit=milestones_limit,
            )
        except GitHubOperationError:
            raise
        except Exception as exc:
            raise GitHubOperationError(
                f"Failed fetching repository overview for '{owner}/{name}': {exc}",
                operation="repo_overview",
                details={"repo": f"{owner}/{name}"},
            ) from exc

    def get_org_repos(
        self,
        org_name: str,
        include_private: bool = True,
        include_forks: bool = False,
        include_archived: bool = True,
    ) -> list[RepoInfo]:
        from github.GithubException import UnknownObjectException

        try:
            org = self._gh.get_organization(org_name)
            repos = org.get_repos(type="all" if include_private else "public")
        except UnknownObjectException:
            user = self._gh.get_user()
            if user.login != org_name:
                raise
            repos = user.get_repos()

        result: list[RepoInfo] = []
        for repo in repos:
            if not include_private and repo.private:
                continue
            if not include_forks and repo.fork:
                continue
            if not include_archived and getattr(repo, "archived", False):
                continue
            result.append(
                RepoInfo(
                    name=repo.name,
                    full_name=repo.full_name,
                    ssh_url=repo.ssh_url,
                    clone_url=repo.clone_url,
                    private=repo.private,
                    fork=repo.fork,
                    archived=getattr(repo, "archived", False),
                )
            )
        return result

    def get_user_ssh_keys(self) -> list[SSHKeyInfo]:
        user = self._gh.get_user()
        return [SSHKeyInfo(id=k.id, title=k.title, key=k.key) for k in user.get_keys()]

    def add_user_ssh_key(self, title: str, key: str) -> int:
        user = self._gh.get_user()
        created = user.create_key(title=title, key=key)
        return created.id

    def delete_user_ssh_key(self, key_id: int) -> None:
        self._gh.get_user().get_key(key_id).delete()

    # ── Pull requests ─────────────────────────────────────────────────────────

    def get_pull(self, repo: str, number: int) -> PullRequest:
        """Return a PyGithub PullRequest object."""
        return self._gh.get_repo(repo).get_pull(number)

    def get_file_at(self, repo: str, path: str, ref: str) -> str | None:
        """A file's text at a commit; None when it is absent, binary or too large to fetch."""
        try:
            content = self._gh.get_repo(repo).get_contents(path, ref=ref)
            if isinstance(content, list):
                return None
            return content.decoded_content.decode("utf-8")
        except Exception as exc:
            logger.debug("Could not fetch %s@%s from %s: %s", path, ref, repo, exc)
            return None

    def get_merge_base(self, repo: str, base: str, head: str) -> str | None:
        """The merge base of two commits from the compare endpoint; None when it cannot be read.

        A pull request's `base.sha` is the base branch's tip, which moves on after the branch
        point; its diff starts here instead.
        """
        try:
            comparison = self._gh.get_repo(repo, lazy=True).compare(
                base, head, comparison_commits_per_page=1
            )
            return str(comparison.merge_base_commit.sha)
        except Exception as exc:
            logger.debug("Could not compare %s...%s in %s: %s", base, head, repo, exc)
            return None

    def get_pr_diff(self, repo: str, number: int) -> str:
        """Fetch the raw unified diff for a pull request."""
        url = f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/pulls/{number}"
        headers = {
            "Accept": "application/vnd.github.diff",
            "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        client_timeout = httpx2.Timeout(DEFAULT_HTTP_TIMEOUT_SECONDS, connect=1.0)
        with httpx2.Client(timeout=client_timeout, follow_redirects=False) as c:
            r = c.get(url, headers=headers)
            if r.is_redirect:
                target_url = r.headers.get("location", "")
                parsed = urllib.parse.urlparse(target_url)
                if parsed.scheme == "https" and parsed.netloc in ("api.github.com", "github.com"):
                    r = c.get(target_url, headers=headers)
            r.raise_for_status()
            return r.text

    def create_pr_review_comment(
        self,
        repo: str,
        number: int,
        body: str,
        commit_id: str,
        path: str,
        line: int,
    ) -> Any:
        """Post a line-level inline review comment on a pull request diff hunk."""
        pr = self.get_pull(repo, number)
        commit_obj = pr.head.sha if not commit_id else commit_id
        return pr.create_review_comment(
            body=body,
            commit=commit_obj,
            path=path,
            line=line,
        )

    # ── Labels ───────────────────────────────────────────────────────────────

    def get_labels(self, repo: str) -> list[dict[str, Any]]:
        """Fetch all labels for a repository."""
        labels = self._gh.get_repo(repo).get_labels()
        return [
            {
                "name": lbl.name,
                "color": lbl.color,
                "description": lbl.description or "",
            }
            for lbl in labels
        ]

    def create_label(self, repo: str, name: str, color: str, description: str = "") -> Any:
        """Create a new label in the specified repository."""
        return self._gh.get_repo(repo).create_label(
            name=name,
            color=color.lstrip("#"),
            description=description,
        )

    def edit_label(self, repo: str, name: str, color: str, description: str = "") -> Any:
        """Update an existing label's color and description."""
        label = self._gh.get_repo(repo).get_label(name)
        return label.edit(
            name=name,
            color=color.lstrip("#"),
            description=description,
        )

    # ── Issues ───────────────────────────────────────────────────────────────

    def get_issues(
        self,
        repo: str,
        state: str = "open",
        milestone: str | int | None = None,
        labels: list[str] | None = None,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Fetch issues matching state, milestone, and labels."""
        from devops_cli.github.issues import get_repository_issues

        m_str = str(milestone) if milestone is not None else None
        issues = get_repository_issues(
            repo, state=state, milestone=m_str, labels=labels, limit=limit
        )
        return [issue.model_dump() for issue in issues]

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        milestone: str | None = None,
        labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new issue with milestone and taxonomy labels."""
        from devops_cli.github.issues import create_repository_issue

        issue = create_repository_issue(
            repo=repo, title=title, body=body, milestone=milestone, labels=labels
        )
        return issue.model_dump()

    def edit_issue(
        self,
        repo: str,
        number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        milestone: str | int | None = None,
        clear_milestone: bool = False,
        labels: list[str] | None = None,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> dict[str, Any]:
        """Update an existing issue in the specified repository."""
        from devops_cli.github.issues import edit_repository_issue

        issue = edit_repository_issue(
            repo=repo,
            number=number,
            title=title,
            body=body,
            state=state,
            milestone=milestone,
            clear_milestone=clear_milestone,
            labels=labels,
            add_labels=add_labels,
            remove_labels=remove_labels,
        )
        return issue.model_dump()

    # ── GitHub Pages ──────────────────────────────────────────────────────────

    def get_pages_info(self, repo: str) -> dict[str, Any] | None:
        """Fetch GitHub Pages site status and configuration."""
        from devops_cli.github.pages import get_pages_status

        info = get_pages_status(repo)
        return info.model_dump() if info else None

    def get_pages_builds(self, repo: str, limit: int = 5) -> list[dict[str, Any]]:
        """Fetch historical GitHub Pages build records."""
        from devops_cli.github.pages import get_pages_builds

        builds = get_pages_builds(repo, limit=limit)
        return [b.model_dump() for b in builds]


def parse_paginated_json(text: str) -> list[dict[str, Any]]:
    """Parse one or multiple concatenated JSON documents or arrays from gh api --paginate."""
    if not text or not text.strip():
        return []
    decoder = json.JSONDecoder()
    items: list[dict[str, Any]] = []
    idx = 0
    length = len(text)
    while idx < length:
        while idx < length and text[idx].isspace():
            idx += 1
        if idx >= length:
            break
        try:
            obj, end_idx = decoder.raw_decode(text, idx)
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

    def edit_issue(
        self,
        repo: str,
        number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        milestone: str | int | None = None,
        clear_milestone: bool = False,
        labels: list[str] | None = None,
        add_labels: list[str] | None = None,
        remove_labels: list[str] | None = None,
    ) -> bool:
        """Update an existing issue using gh CLI."""
        from devops_cli.github.issues import edit_repository_issue

        try:
            edit_repository_issue(
                repo=repo or self.default_repo or "",
                number=number,
                title=title,
                body=body,
                state=state,
                milestone=milestone,
                clear_milestone=clear_milestone,
                labels=labels,
                add_labels=add_labels,
                remove_labels=remove_labels,
            )
            return True
        except Exception:
            return False

    def api(self, endpoint: str, paginate: bool = False) -> str:
        """Execute a GitHub API request via rate-managed run_gh."""
        cmd = [CONST_GH_CLI, "api"]
        if paginate:
            cmd.append("--paginate")
        cmd.append(endpoint)
        res = run_gh(cmd, check=False, quiet=True)
        if res.returncode != 0:
            raise GitHubOperationError(
                f"gh api call failed with exit code {res.returncode}: {res.stderr.strip()}",
                operation="gh_api",
                details={"endpoint": endpoint, "stderr": res.stderr[:256]},
            )
        return res.stdout
