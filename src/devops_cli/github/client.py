"""GitHub API client wrapping PyGithub."""

from __future__ import annotations

import json
import urllib.parse
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

import httpx2
from pydantic import BaseModel

from devops_cli.config.constants import CONST_GH_CLI, CONST_URL_GITHUB_API_BASE
from devops_cli.config.defaults import DEFAULT_HTTP_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.models.ssh import SSHKeyInfo

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
        created = user.create_key(title=title, key=key)
        return created.id

    def delete_user_ssh_key(self, key_id: int) -> None:
        self._gh.get_user().get_key(key_id).delete()

    # ── Pull requests ─────────────────────────────────────────────────────────

    def get_pull(self, repo: str, number: int) -> PullRequest:
        """Return a PyGithub PullRequest object."""
        return self._gh.get_repo(repo).get_pull(number)

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

    # ── Milestones ────────────────────────────────────────────────────────────

    def get_milestones(self, repo: str, state: str = "all") -> list[dict[str, Any]]:
        """Fetch all milestones for a repository."""
        milestones = self._gh.get_repo(repo).get_milestones(state=state)
        results: list[dict[str, Any]] = []
        for m in milestones:
            due = getattr(m, "due_on", None)
            due_str = (
                due.isoformat()
                if due and hasattr(due, "isoformat")
                else (str(due) if due else None)
            )
            results.append(
                {
                    "title": m.title,
                    "number": m.number,
                    "state": m.state,
                    "description": m.description or "",
                    "open_issues": m.open_issues,
                    "closed_issues": m.closed_issues,
                    "due_on": due_str,
                }
            )
        return results

    def create_milestone(
        self,
        repo: str,
        title: str,
        description: str = "",
        state: str = "open",
        due_on: str | date | datetime | None = None,
    ) -> Any:
        """Create a new milestone in the specified repository."""
        kwargs: dict[str, Any] = {
            "title": title,
            "description": description,
            "state": state,
        }
        if due_on is not None:
            if isinstance(due_on, (datetime, date)):
                kwargs["due_on"] = due_on
            elif isinstance(due_on, str) and due_on.strip():
                clean_due = due_on.strip()
                try:
                    kwargs["due_on"] = datetime.fromisoformat(clean_due.replace("Z", "+00:00"))
                except ValueError:
                    kwargs["due_on"] = date.fromisoformat(clean_due)
        return self._gh.get_repo(repo).create_milestone(**kwargs)

    def edit_milestone(
        self,
        repo: str,
        number: int,
        title: str | None = None,
        state: str = "closed",
        description: str | None = None,
        due_on: str | date | datetime | None = None,
    ) -> Any:
        """Update an existing milestone in the specified repository."""
        milestone = self._gh.get_repo(repo).get_milestone(number)
        kwargs: dict[str, Any] = {"state": state}
        kwargs["title"] = title if title is not None else milestone.title
        if description is not None:
            kwargs["description"] = description
        if due_on is not None:
            if isinstance(due_on, (datetime, date)):
                kwargs["due_on"] = due_on
            elif isinstance(due_on, str) and due_on.strip():
                clean_due = due_on.strip()
                try:
                    kwargs["due_on"] = datetime.fromisoformat(clean_due.replace("Z", "+00:00"))
                except ValueError:
                    kwargs["due_on"] = date.fromisoformat(clean_due)
        return milestone.edit(**kwargs)

    def close_milestone(self, repo: str, version_or_number: str | int) -> bool:
        """Close a milestone by number or title/version string."""
        if isinstance(version_or_number, int):
            self.edit_milestone(repo, version_or_number, state="closed")
            return True

        target_title = str(version_or_number).strip()
        candidates = {target_title, target_title.lstrip("v"), f"v{target_title.lstrip('v')}"}
        milestones = self.get_milestones(repo, state="all")
        matched = next((m for m in milestones if m.get("title") in candidates), None)
        if matched and "number" in matched:
            self.edit_milestone(repo, int(matched["number"]), state="closed")
            return True
        return False

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


class GhCliClient:
    """GitHub client backed by the gh CLI tool for local operations without raw PATs."""

    def __init__(self, default_repo: str | None = None) -> None:
        self.default_repo = default_repo

    def get_labels(self, repo: str) -> list[dict[str, Any]]:
        target_repo = repo or self.default_repo or ""
        cmd = [CONST_GH_CLI, "label", "list", "--json", "name,color,description"]
        if target_repo:
            cmd.extend(["--repo", target_repo])
        res = run_subprocess(cmd, check=False, quiet=True)
        if res.returncode == 0 and res.stdout.strip():
            try:
                return json.loads(res.stdout)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                pass
        return []

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
        run_subprocess(cmd, check=False)

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
        run_subprocess(cmd, check=False)

    def get_milestones(self, repo: str, state: str = "all") -> list[dict[str, Any]]:
        target_repo = repo or self.default_repo or ""
        cmd = [
            CONST_GH_CLI,
            "api",
            "--paginate",
            f"repos/{target_repo}/milestones?state={state}&per_page=100",
        ]
        res = run_subprocess(cmd, check=False, quiet=True)
        if res.returncode == 0 and res.stdout.strip():
            try:
                raw = json.loads(res.stdout)
                return [
                    {
                        "title": m.get("title", ""),
                        "number": m.get("number", 0),
                        "state": m.get("state", "open"),
                        "description": m.get("description", ""),
                        "open_issues": m.get("open_issues", 0),
                        "closed_issues": m.get("closed_issues", 0),
                        "due_on": m.get("due_on"),
                    }
                    for m in raw
                    if isinstance(m, dict)
                ]
            except json.JSONDecodeError:
                pass
        return []

    def create_milestone(
        self,
        repo: str,
        title: str,
        description: str = "",
        state: str = "open",
        due_on: Any = None,
    ) -> None:
        target_repo = repo or self.default_repo or ""
        cmd = [
            CONST_GH_CLI,
            "api",
            f"repos/{target_repo}/milestones",
            "-f",
            f"title={title}",
            "-f",
            f"description={description}",
            "-f",
            f"state={state}",
        ]
        if due_on:
            cmd.extend(["-f", f"due_on={due_on}"])
        run_subprocess(cmd, check=False)
