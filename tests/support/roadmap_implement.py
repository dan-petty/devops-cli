"""A Staged item for the tests of the implement job (#2665): the repository of `stage_repo` with
the branch that the stage job pushes, the item and its record, and the draft pull request that
GitHub reports for it.

The branch holds one commit by the App, `STAGE_NAME`, with the change folder
`openspec/changes/1-the-job-drops-a-comment/` and its two task groups. `STAGE_NAME` is also the
identity the clone commits as, so the commits of the steps are the App's too.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import ItemField, StageRecordKey
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo

BRANCH = "fix/1-the-job-drops-a-comment"
CHANGE = "1-the-job-drops-a-comment"
CHANGE_DIR = f"openspec/changes/{CHANGE}"
PULL = 5
TITLE = "fix(roadmap): the job drops a comment"
BODY = (
    "## Problem or Motivation\n\nThe job drops the last comment of a thread.\n\n"
    "## Acceptance criteria\n\n- The job keeps every comment.\n"
)

PROPOSAL = (
    "# Proposal\n\n## Why\n\nThe job drops the last comment of a thread (#1). It must keep it.\n\n"
    "## What Changes\n\n- The job keeps every comment.\n"
)
DESIGN = "# Design\n\n## Decisions\n\n- Keep the last comment.\n"
TASKS = """\
# Tasks

## 1. The first group

- [ ] Add `src/devops_cli/shout.py`
  - Verification: `uv run devops ci test tests/test_shout.py`

## 2. The second group

- [ ] Document the function in `docs/SHOUT.md`
  - Verification: `uv run devops docs check`
"""
TICKED_FIRST = TASKS.replace("- [ ] Add", "- [x] Add")
TICKED_ALL = TICKED_FIRST.replace("- [ ] Document", "- [x] Document")
SHOUT = '"""Shout."""\n\n\ndef shout(text: str) -> str:\n    """Shout `text`."""\n    return text.upper()\n'
SHOUT_DOC = "The shout function upper-cases a text.\n"
TASKS_PATH = f"{CHANGE_DIR}/tasks.md"

OPEN_DRAFT = {"state": "open", "draft": True, "merged": False}


def write_change(root: Path, tasks: str = TASKS) -> None:
    """The files of the change folder, in the checkout at `root`."""
    folder = root / CHANGE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in (
        ("proposal.md", PROPOSAL),
        ("design.md", DESIGN),
        ("tasks.md", tasks),
        (".openspec.yaml", "schema: spec-driven\ncreated: 2026-10-29\n"),
    ):
        (folder / name).write_text(text, encoding="utf-8")


def push_staged_branch(repo: StageRepo, *, tasks: str = TASKS, author: str = STAGE_NAME) -> None:
    """Push `BRANCH` with one commit by `author` that adds the change, as the stage job does; the
    clone stays on `main` with no local branch."""
    repo.git("switch", "-q", "-c", BRANCH)
    write_change(repo.clone, tasks)
    repo.git("add", "-A")
    repo.git("-c", f"user.name={author}", "commit", "-q", "-m", "fix(roadmap): plan")
    repo.git("push", "-q", "origin", BRANCH)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-q", "-D", BRANCH)


def seed_staged(
    store: InMemoryRoadmapStore,
    *,
    labels: tuple[str, ...] = ("type/bug", "effort/low"),
    priority: str = "P1-High",
    status: str = "Ready",
    record: bool = True,
    author_association: str | None = "OWNER",
    title: str = TITLE,
) -> int:
    """An item with the stage job's record: the branch and the draft pull request `PULL`."""
    number = store.seed_issue(
        title,
        body=BODY,
        labels=labels,
        fields={ItemField.STATUS: status, ItemField.PRIORITY: priority},
        author_association=author_association,
    )
    if record:
        item = store.item(number)
        assert item is not None
        store.set_marks(item, {StageRecordKey.BRANCH: BRANCH, StageRecordKey.PR: str(PULL)})
    return number


def route_pull_status(api: GitHubApiFake, status: dict[str, object] = OPEN_DRAFT) -> None:
    """GitHub's answer to the read of the state of pull request `PULL`."""
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(status))


@pytest.fixture
def app_slug(config: Callable[..., Path]) -> None:
    """The slug of the App, so that `STAGE_NAME` is its bot's login."""
    config(service={"github_app": {"slug": STAGE_NAME.removesuffix("[bot]")}})


@pytest.fixture
def staged_repo(stage_repo: StageRepo, app_slug: None) -> StageRepo:
    """`stage_repo` with the staged branch pushed."""
    push_staged_branch(stage_repo)
    return stage_repo
