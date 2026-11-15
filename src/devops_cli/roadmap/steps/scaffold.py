"""The roadmap step `scaffold`: makes, resumes or adopts the item branch (ADR 0021, section 8; #5499).

Applies the resume rule in order:
1. A branch on origin names the issue, and only the App wrote past `origin/main`: resume on it.
2. The branch holds a commit of a person or an agent: the item is held. Skip it and write nothing (`issue_holder`).
3. The branch is App-only, and the record does not name it: adopt it and record it.
4. No branch: create the ref at the latest `origin/main` head with the git refs API, with no commit.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from devops_cli.config.constants import (
    CONST_GIT_CLI,
    CONST_GIT_MAIN_BRANCH,
    CONST_GIT_REMOTE_ORIGIN,
)
from devops_cli.config.settings import load_settings
from devops_cli.exceptions import GitOperationError
from devops_cli.git.branch_form import branch_name, slug_from_title
from devops_cli.git.worktree_add import (
    _pushed_branches,
    issue_holder,
    local_holder,
    read_remote_heads,
    worktree_directory,
)
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.clone_git import branch_authors
from devops_cli.roadmap.commit_title import commit_type
from devops_cli.roadmap.stores.store import RoadmapStore, ScaffoldRecordKey

logger = logging.getLogger(__name__)

_GIT_OPERATION = "roadmap scaffold"


class ScaffoldResult(StrEnum):
    """The result of the scaffold step on an item branch (#5499)."""

    CREATED = "created"
    RESUMED = "resumed"
    ADOPTED = "adopted"
    HELD = "held"


@dataclass(frozen=True)
class ScaffoldReport:
    """The outcome of the scaffold step for an item."""

    repo: str
    item: int
    branch: str
    result: ScaffoldResult
    holder: str | None = None

    def to_json(self) -> str:
        """The JSON result line of the scaffold step."""
        data: dict[str, Any] = {
            "job": "scaffold",
            "repo": self.repo,
            "item": self.item,
            "branch": self.branch,
            "result": self.result.value,
        }
        if self.holder is not None:
            data["holder"] = self.holder
        return json.dumps(data)


def _git(cwd: Path, *args: str) -> str:
    from devops_cli.core.process import run_subprocess

    proc = run_subprocess([CONST_GIT_CLI, "-C", str(cwd), *args], check=False, quiet=True)
    if proc.returncode != 0:
        raise GitOperationError(
            f"git {' '.join(args)} failed: {proc.stderr.strip()}", operation=_GIT_OPERATION
        )
    return proc.stdout.strip()


def _is_app_author(author: str, source: Path) -> bool:
    bot = load_settings().service.github_app.bot_login
    if bot is not None and author == bot:
        return True
    try:
        user_name = _git(source, "config", "user.name")
        if user_name and author == user_name:
            return True
    except GitOperationError:
        pass
    return False


def run_scaffold(
    store: RoadmapStore,
    *,
    repo: str,
    item: int,
    source: Path,
    kind: str = "plan",
    slug: str | None = None,
    type_: str | None = None,
    dry_run: bool = False,
) -> ScaffoldReport:
    """Run the scaffold step for `item` in `repo` with clone `source` (#5499).

    Exits with result `created`, `resumed`, `adopted`, or `held`.
    """
    found_item = store.item(item)
    if found_item is None:
        raise ValueError(f"Item #{item} not found in roadmap store.")

    # Determine branch name
    title = found_item.title
    derived_type = type_ or commit_type(title) or "feat"
    derived_slug = slug or slug_from_title(title)
    expected_branch = branch_name(item, derived_type, derived_slug)

    if dry_run:
        # Dry-run: make zero external requests, write no marks
        return ScaffoldReport(
            repo=repo,
            item=item,
            branch=expected_branch,
            result=ScaffoldResult.CREATED,
        )

    # 1. Check local holder
    local = local_holder(source, item, worktree_directory(item, source))
    if local is not None:
        return ScaffoldReport(
            repo=repo,
            item=item,
            branch=expected_branch,
            result=ScaffoldResult.HELD,
            holder=local,
        )

    remote_heads = read_remote_heads(source)
    pushed = _pushed_branches(remote_heads, item)

    if pushed:
        branch = pushed[0].name
        # Check authors on branch past origin/main
        authors = branch_authors(source, branch, operation=_GIT_OPERATION)
        foreign = [author for author in authors if not _is_app_author(author, source)]

        if foreign:
            # Case 2: The branch holds a commit of a person or an agent
            holder = (
                issue_holder(source, item, remote_heads, branch) or f"held by {', '.join(foreign)}"
            )
            report = ScaffoldReport(
                repo=repo,
                item=item,
                branch=branch,
                result=ScaffoldResult.HELD,
                holder=holder,
            )
            return report

        # Branch is App-only
        recorded_branch = found_item.job_record.get(ScaffoldRecordKey.BRANCH)
        if recorded_branch == branch:
            # Case 1: The record names an App-only branch -> resume
            report = ScaffoldReport(
                repo=repo,
                item=item,
                branch=branch,
                result=ScaffoldResult.RESUMED,
            )
            return report

        # Case 3: The branch is App-only and record does not name it -> adopt
        store.set_marks(found_item, {ScaffoldRecordKey.BRANCH: branch})
        report = ScaffoldReport(
            repo=repo,
            item=item,
            branch=branch,
            result=ScaffoldResult.ADOPTED,
        )
        return report

    # Case 4: No branch on origin
    _git(source, "fetch", "-q", CONST_GIT_REMOTE_ORIGIN, CONST_GIT_MAIN_BRANCH)
    sha = _git(source, "rev-parse", f"{CONST_GIT_REMOTE_ORIGIN}/{CONST_GIT_MAIN_BRANCH}")

    client = get_github_session().client
    client.create_ref(repo, ref=f"refs/heads/{expected_branch}", sha=sha)
    store.set_marks(found_item, {ScaffoldRecordKey.BRANCH: expected_branch})

    return ScaffoldReport(
        repo=repo,
        item=item,
        branch=expected_branch,
        result=ScaffoldResult.CREATED,
    )
