"""The Service row `open`: the open step for a pushed bot branch that has no pull request (#5974).

The implement job records its branch (`implement.branch`) before its first push and opens the pull
request after the push. A Job that ends between the two leaves a branch with no pull request, and
the jobs of #4719 and #5029 end at the push. The row finds each such branch and runs the open step
for it, so that one step derives the title, the body, the labels and the Status, and checks them
with the rules of CI (`steps/open.py`).

A branch is a candidate when:
- the job record of an open item names it in `implement.branch`, so the row never opens a branch
  of a person, and `origin` holds it;
- no open pull request holds the issue;
- no runner Job holds the item, no stage Job holds it, the stage job does not own it as an orphan
  (`stage.pending`, #4051), and no stop of the item waits for a person;
- GitHub associates no pull request with its head commit: a person who closed a pull request of
  that head decided, and the row does not open it again.

A plan branch stays with the stage job: the stage job records `stage.branch` only after it opens
the plan pull request, and removes its orphans itself (#4051).

`roadmap.open.mode` sets what the row does: `off` reads nothing, `plan` logs each candidate and
writes nothing, and `on` runs the open step for each candidate.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from devops_cli.config.constants import (
    CONST_OPENSPEC_ARCHIVED_FOLDER_RE,
    CONST_OPENSPEC_CHANGE_FOLDER_RE,
    CONST_OPENSPEC_CHANGES_DIR,
)
from devops_cli.exceptions import DevOpsCLIError, GitHubFileNotFoundError, ValidationError
from devops_cli.exceptions.roadmap import RoadmapOpenRefusedError
from devops_cli.git.branch_form import issue_of_branch
from devops_cli.git.worktree_add import read_remote_heads
from devops_cli.git.worktree_inventory import CONST_REFS_HEADS_PREFIX
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.commit_title import commit_summary
from devops_cli.roadmap.pull_form import BODY_MAX_CHARS, build_body
from devops_cli.roadmap.pull_labels import declared_labels
from devops_cli.roadmap.stage.stage_change import (
    closing_keyword_in,
    delivery_title,
    plan_summary,
    safe_text,
)
from devops_cli.roadmap.status_sync import job_holds
from devops_cli.roadmap.step_files import section_text
from devops_cli.roadmap.steps.open import OpenRequest, open_or_update
from devops_cli.roadmap.stores.store import ImplementRecordKey, StageRecordKey

if TYPE_CHECKING:
    from pathlib import Path

    from devops_cli.config.defaults import RowMode
    from devops_cli.github.client import PullRequestFile
    from devops_cli.roadmap.stores.store import Item, RoadmapStore

logger = logging.getLogger(__name__)

_WHY_HEADINGS = frozenset({"why"})
_PROPOSAL = "proposal.md"
_SHORT_SHA = 12
_GIT_OPERATION = "roadmap.open"


@dataclass(frozen=True)
class OpenCandidate:
    """A pushed branch of an open item that has no pull request: the item, the branch and the
    commit at the head of the branch on `origin`."""

    item: Item
    branch: str
    sha: str


@dataclass
class OpenRound:
    """What one round of the row did: the candidates it found, the pull requests it opened, and
    the items whose open step failed."""

    candidates: list[OpenCandidate] = field(default_factory=list)
    opened: list[int] = field(default_factory=list)
    failed: list[int] = field(default_factory=list)


def _heads(ls_remote: str) -> dict[str, str]:
    """The commit of each branch in the output of `git ls-remote --heads`."""
    heads: dict[str, str] = {}
    for line in ls_remote.splitlines():
        sha, _, ref = line.partition("\t")
        if ref.startswith(CONST_REFS_HEADS_PREFIX):
            heads[ref.removeprefix(CONST_REFS_HEADS_PREFIX)] = sha.strip()
    return heads


def _held(item: Item) -> bool:
    """Whether a Job, the orphan rule of the stage job or a stop holds the item."""
    record = item.job_record
    return (
        job_holds(item)
        or bool(record.get(StageRecordKey.JOB))
        or bool(record.get(StageRecordKey.PENDING))
        or bool(record.get(ImplementRecordKey.STOPPED))
    )


def open_candidates(store: RoadmapStore, ls_remote: str) -> list[OpenCandidate]:
    """The pushed branches of open items that the row may open, in the order of the items. It
    reads the listing of the store and `ls_remote`, and sends no request."""
    heads = _heads(ls_remote)
    held_issues = {issue_of_branch(pull.head_ref) for pull in store.open_pulls()}
    found = []
    for item in store.open_items():
        branch = item.job_record.get(ImplementRecordKey.BRANCH)
        if not branch or branch not in heads or item.number in held_issues or _held(item):
            continue
        found.append(OpenCandidate(item=item, branch=branch, sha=heads[branch]))
    return found


def _change_folder(files: Sequence[PullRequestFile], issue: int) -> str | None:
    """The change folder of `issue` that the diff writes: the archived folder that it adds, else
    the active folder, else None."""
    for pattern in (CONST_OPENSPEC_ARCHIVED_FOLDER_RE, CONST_OPENSPEC_CHANGE_FOLDER_RE):
        for changed in files:
            found = re.fullmatch(pattern, changed.filename)
            if found is not None and int(found["issue"]) == issue:
                return changed.filename[: found.end("change")]
    return None


def delivery_why(proposal: str | None, item_title: str, room: int) -> str:
    """The "why" of `proposal` on one line, at most `room` characters long. The summary of
    `item_title` stands in when the proposal has none, when its text is longer than `room`, or when
    it holds a closing keyword. The text is never cut."""
    text = ""
    if proposal:
        text = safe_text(section_text(proposal, _WHY_HEADINGS).partition("\n")[2])
    if not text or len(text) > room or closing_keyword_in(text) is not None:
        text = safe_text(commit_summary(item_title) or item_title)
    return text


def _proposal(store: RoadmapStore, folder: str, sha: str) -> str | None:
    try:
        return store.repository_file(f"{folder}/{_PROPOSAL}", ref=sha)
    except GitHubFileNotFoundError:
        return None


def _plan_summary(source: Path, number: int) -> str | None:
    """The summary of the merged plan of item `number`, from the subject of the commit of the
    default branch that adds its proposal (#5341), as the implement job reads it."""
    proposal = f":(glob){CONST_OPENSPEC_CHANGES_DIR}/{number}-*/{_PROPOSAL}"
    subject = git(
        source,
        *("log", "-1", "--diff-filter=A", "--format=%s", "HEAD", "--", proposal),
        operation=_GIT_OPERATION,
    )
    return plan_summary(subject, number)


def delivery_request(
    store: RoadmapStore,
    *,
    repo: str,
    candidate: OpenCandidate,
    base: str,
    source: Path | None = None,
) -> OpenRequest:
    """The request of the open step for the delivery branch of `candidate`: the title of the item
    with the summary of its plan, and a body that closes the item and names the change folder of
    the diff. The open step checks both with the rules of CI before it writes them."""
    item = candidate.item
    try:
        declared: tuple[str, ...] = declared_labels(store, ref=base)
    except GitHubFileNotFoundError:
        declared = ()
    summary = _plan_summary(source, item.number) if source is not None else None
    title = delivery_title(item.title, declared, summary)
    files = get_github_session().client.get_compare_files(repo, base, candidate.sha).files
    folder = _change_folder(files, item.number)
    closing = f"\n\nCloses #{item.number}"
    if folder is None:
        body = delivery_why(None, item.title, BODY_MAX_CHARS - len(closing)) + closing
    else:
        room = BODY_MAX_CHARS - len(f"{closing}\n\nChange: `{folder}/`")
        why = delivery_why(_proposal(store, folder, candidate.sha), item.title, room)
        try:
            body = build_body(why=why, issue=item.number, change=folder)
        except ValidationError as exc:
            raise RoadmapOpenRefusedError(str(exc)) from exc
    return OpenRequest(
        repo=repo,
        head=candidate.branch,
        base=base,
        title=title,
        body=body,
        kind="delivery",
        item=item.number,
        store=store,
        changed=tuple(files),
    )


def _fresh(repo: str, candidates: Sequence[OpenCandidate]) -> list[OpenCandidate]:
    """The candidates whose head commit GitHub associates with no pull request, open or closed."""
    client = get_github_session().client
    return [c for c in candidates if not client.get_commit_pulls(repo, c.sha)]


def run_open_round(
    store: RoadmapStore,
    *,
    repo: str,
    source: Path,
    mode: RowMode,
    base: str,
    ls_remote: str | None = None,
) -> OpenRound:
    """One round of the row `open` in `mode` (#5974). `ls_remote` is the output of
    `git ls-remote --heads origin` for `source`, read when None. A failed open step of one item
    leaves the other items, and the round raises `RoadmapOpenRefusedError` that names each failed
    item once every candidate was tried."""
    result = OpenRound()
    if mode == "off":
        return result
    heads = read_remote_heads(source) if ls_remote is None else ls_remote
    result.candidates = _fresh(repo, open_candidates(store, heads))
    texts = MESSAGES.roadmap
    for candidate in result.candidates:
        number = candidate.item.number
        if mode != "on":
            logger.info(
                texts.open_row_would_open,
                repo,
                number,
                candidate.branch,
                candidate.sha[:_SHORT_SHA],
            )
            continue
        try:
            request = delivery_request(
                store, repo=repo, candidate=candidate, base=base, source=source
            )
            opened = open_or_update(request)
        except DevOpsCLIError as exc:
            logger.warning(texts.open_row_failed, repo, number, candidate.branch, exc)
            result.failed.append(number)
            continue
        logger.info(texts.open_row_opened, repo, opened.number, number, opened.title)
        result.opened.append(opened.number)
    if result.failed:
        raise RoadmapOpenRefusedError(
            texts.open_row_round_failed.format(
                repo=repo, items=", ".join(f"#{n}" for n in result.failed)
            )
        )
    return result
