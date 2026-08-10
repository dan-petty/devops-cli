"""GitHub API client wrapping PyGithub."""

from __future__ import annotations

from typing import TYPE_CHECKING

import httpx2
from pydantic import BaseModel

from devops_cli.config.constants import CONST_URL_GITHUB_API_BASE
from devops_cli.models.github import SSHKeyInfo

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
    def __init__(self, token: str) -> None:
        from github import Auth, Github

        self._token = token
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

    def get_user_ssh_keys(self) -> list[SSHKeyInfo]:
        user = self._gh.get_user()
        return [SSHKeyInfo(id=k.id, title=k.title, key=k.key) for k in user.get_keys()]

    def add_user_ssh_key(self, title: str, key: str) -> int:
        user = self._gh.get_user()
        created = user.create_key(title=title, key=key)  # type: ignore[union-attr]
        return created.id

    def delete_user_ssh_key(self, key_id: int) -> None:
        self._gh.get_user().get_key(key_id).delete()  # type: ignore[union-attr]

    # ── Pull requests ─────────────────────────────────────────────────────────

    def get_pull(self, repo: str, number: int) -> PullRequest:
        """Return a PyGithub PullRequest object."""
        return self._gh.get_repo(repo).get_pull(number)

    def get_pr_diff(self, repo: str, number: int) -> str:
        """Fetch the raw unified diff for a pull request."""
        with httpx2.Client(timeout=60, follow_redirects=True) as c:
            r = c.get(
                f"{CONST_URL_GITHUB_API_BASE}/repos/{repo}/pulls/{number}",
                headers={
                    "Accept": "application/vnd.github.diff",
                    "Authorization": f"Bearer {self._token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            r.raise_for_status()
            return r.text
