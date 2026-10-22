"""GitHub API client wrapping PyGithub."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GITHUB_DIFF_MEDIA_TYPE,
    CONST_MAX_ERROR_DETAIL_LENGTH,
)
from devops_cli.config.defaults import DEFAULT_GH_LABEL_LIST_LIMIT
from devops_cli.exceptions.git import GitHubOperationError, GitHubUnreadError
from devops_cli.github.rate_limiter import run_gh
from devops_cli.github.session import get_github_session

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from github.PullRequest import PullRequest


class RepoInfo(BaseModel):
    name: str
    full_name: str
    ssh_url: str
    clone_url: str
    private: bool
    fork: bool
    archived: bool


class GitHubClient:
    """PyGithub with the session's token; `github.session` builds the only one (#767)."""

    def __init__(self, token: str) -> None:
        from github import Auth, Github

        self._gh = Github(auth=Auth.Token(token))

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
        """The pull request's unified diff, read through the GitHub session.

        GitHub sends a diff as text; any other answer, JSON or a body without a content type,
        raises `GitHubUnreadError`.
        """
        path = f"/repos/{repo}/pulls/{number}"
        diff = get_github_session().rest("GET", path, accept=CONST_GITHUB_DIFF_MEDIA_TYPE)
        if not isinstance(diff, str):
            raise GitHubUnreadError(
                f"GitHub's answer to GET {path} is no diff: {type(diff).__name__}",
                details={"path": path[:CONST_MAX_ERROR_DETAIL_LENGTH]},
            )
        return diff

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
