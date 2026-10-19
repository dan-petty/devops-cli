"""The release pull request's remaining review threads, filed as follow-up issues (#1345).

Once the release pull request's Copilot passes are spent, the stop rule in `RELEASE_CYCLE.md`
Step 3 lets a remaining review comment block the release only if it is a regression the release
introduces; every other one becomes a follow-up issue. `file_thread_issues` files each unresolved
thread not kept as one issue, through the roadmap store with no milestone and labelled
`source/agent`, replies in the thread naming the issue, and resolves the thread, in that order.
The reply carries `CONST_PR_THREAD_FILED_MARKER`, so a rerun after a run that stopped part-way
resolves a thread already filed and files it no second time.

An issue quotes its thread's comments inside a fence longer than any in them, so a mention or an
issue reference in a comment neither notifies nor links. No model is called: `devops roadmap
intake` places the issue later, as an open issue not on the board.

This module is apart from `pr_threads.py`, which `pr_monitor.py` imports, because it reads the
pull request through `pr_monitor.py`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_PR_THREAD_FILED_MARKER,
    CONST_ROADMAP_SOURCE_AGENT_LABEL,
)
from devops_cli.config.defaults import DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.exceptions.git import ThreadFilingRefusedError
from devops_cli.github.pr_branches import branch_ref, is_release_pr
from devops_cli.github.pr_monitor import _fetch_pr_details, pr_details_argv
from devops_cli.github.pr_threads import (
    ReviewThread,
    list_pr_review_threads,
    reply_pr_review_thread,
    reply_thread_args,
    resolve_pr_review_thread,
    resolve_thread_args,
    review_threads_args,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.github_store import create_issue_args
from devops_cli.roadmap.store import RoadmapStore

_FENCE_MIN = 3


class ThreadOutcome(StrEnum):
    """What a filing run did, or would do, with one unresolved thread."""

    KEPT = "kept"
    TO_FILE = "to file"
    FILED = "filed"
    ALREADY_FILED = "already filed"


class ThreadFiling(BaseModel):
    """One unresolved thread, and what the run did or would do with it."""

    model_config = ConfigDict(frozen=True)

    thread_id: str
    location: str
    title: str
    outcome: ThreadOutcome
    issue: int | None = None


def thread_location(thread: ReviewThread) -> str:
    """The thread's `path:line`, or its path alone when GitHub gives it no line."""
    return f"{thread.path}:{thread.line}" if thread.line is not None else thread.path


def thread_issue_title(pr_number: int, thread: ReviewThread) -> str:
    """The title of the follow-up issue for `thread` on pull request `pr_number`."""
    return MESSAGES.pr.thread_issue_title.format(location=thread_location(thread), number=pr_number)


def _fence_for(text: str) -> str:
    """A backtick fence longer than every run of backticks in `text`, so none closes it."""
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    return "`" * max(_FENCE_MIN, longest + 1)


def _thread_text(thread: ReviewThread) -> str:
    """The thread's comments, each under its author, cut to the most an issue quotes."""
    text = "\n\n".join(f"{comment.author}:\n{comment.body}" for comment in thread.comments)
    cap = DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS
    if len(text) <= cap:
        return text
    return f"{text[:cap]}\n{MESSAGES.pr.thread_issue_cut.format(chars=cap)}"


def thread_issue_body(pr_number: int, thread: ReviewThread) -> str:
    """The follow-up issue's body: the thread's comments inside a fence, then its location and
    the link to its first comment."""
    text = _thread_text(thread)
    fence = _fence_for(text)
    url = thread.comments[0].url if thread.comments else ""
    location = thread_location(thread)
    source = MESSAGES.pr.thread_issue_source.format(location=location, url=url) if url else location
    intro = MESSAGES.pr.thread_issue_intro.format(number=pr_number)
    return f"{intro}\n\n{fence}\n{text}\n{fence}\n\n{source}\n"


def _already_filed(thread: ReviewThread) -> bool:
    """Whether an earlier run filed the thread: a reply in it holds the marker."""
    return any(CONST_PR_THREAD_FILED_MARKER in comment.body for comment in thread.comments)


def _require_release_pr(owner: str, repo_name: str, pr_number: int) -> None:
    """Refuse any pull request but the release pull request, naming its two branches."""
    pr_data = _fetch_pr_details(owner, repo_name, pr_number)
    if is_release_pr(pr_data):
        return
    head, base = branch_ref(pr_data, "head"), branch_ref(pr_data, "base")
    raise ThreadFilingRefusedError(
        MESSAGES.pr.threads_not_release_pr.format(number=pr_number, head=head, base=base),
        details={"pull_request": pr_number, "head": head, "base": base},
    )


def _file(store: RoadmapStore, pr_number: int, thread: ReviewThread) -> int:
    """File `thread` as an issue, then reply naming it, then resolve the thread."""
    title, body = thread_issue_title(pr_number, thread), thread_issue_body(pr_number, thread)
    issue = store.create_issue(title, body, labels=(CONST_ROADMAP_SOURCE_AGENT_LABEL,))
    reply = MESSAGES.pr.thread_filed_reply.format(issue=issue.number)
    reply_pr_review_thread(thread.id, f"{reply}\n\n{CONST_PR_THREAD_FILED_MARKER}")
    resolve_pr_review_thread(thread.id)
    return issue.number


def _handle(
    thread: ReviewThread, pr_number: int, keep: frozenset[str], store: RoadmapStore | None
) -> ThreadFiling:
    """Keep, preview, resolve or file one thread; `store` is None when nothing is written."""
    filing = ThreadFiling(
        thread_id=thread.id,
        location=thread_location(thread),
        title=thread_issue_title(pr_number, thread),
        outcome=ThreadOutcome.KEPT,
    )
    if thread.id in keep:
        return filing
    filed = _already_filed(thread)
    if store is None:
        outcome = ThreadOutcome.ALREADY_FILED if filed else ThreadOutcome.TO_FILE
        return filing.model_copy(update={"outcome": outcome})
    if filed:
        resolve_pr_review_thread(thread.id)
        return filing.model_copy(update={"outcome": ThreadOutcome.ALREADY_FILED})
    issue = _file(store, pr_number, thread)
    return filing.model_copy(update={"outcome": ThreadOutcome.FILED, "issue": issue})


def file_thread_issues(
    owner: str,
    repo_name: str,
    pr_number: int,
    *,
    keep: Iterable[str] = (),
    confirm: bool = False,
) -> list[ThreadFiling]:
    """File each unresolved thread of release pull request `pr_number` not in `keep` as a
    follow-up issue, reply naming it and resolve the thread, one thread after another; without
    `confirm`, read the threads and write nothing.

    Raises `ThreadFilingRefusedError` for any other pull request, before its threads are read.
    A failed write stops the run where it failed, so a thread whose issue was not opened gets no
    reply and stays open; the rerun picks it up.
    """
    _require_release_pr(owner, repo_name, pr_number)
    threads = list_pr_review_threads(owner, repo_name, pr_number, unresolved_only=True)
    store = roadmap_store.get_roadmap_store(f"{owner}/{repo_name}") if confirm else None
    kept = frozenset(keep)
    return [_handle(thread, pr_number, kept, store) for thread in threads]


def describe_filing(filing: ThreadFiling, *, confirm: bool) -> str:
    """One line saying what the run did, or would do, with a thread."""
    texts = MESSAGES.pr
    template = {
        ThreadOutcome.KEPT: texts.thread_kept,
        ThreadOutcome.TO_FILE: texts.thread_to_file,
        ThreadOutcome.FILED: texts.thread_filed,
        ThreadOutcome.ALREADY_FILED: (
            texts.thread_resolved_filed if confirm else texts.thread_seen_filed
        ),
    }[filing.outcome]
    return template.format(
        thread=filing.thread_id, location=filing.location, title=filing.title, issue=filing.issue
    )


def plan_thread_issues(repo: str, pr_number: int) -> list[PlannedRequest]:
    """The requests `file_thread_issues` makes with `confirm`, in order and with no value
    read (#412); each gh command is the argv the real run builds, with placeholders."""
    texts = MESSAGES.pr
    owner, repo_name = repo.split("/", 1)
    on_release = texts.threads_plan_release.format(number=pr_number)
    unfiled = both(on_release, texts.threads_plan_unfiled)
    not_kept = both(on_release, texts.threads_plan_not_kept)
    each = texts.threads_plan_each
    details = pr_details_argv(owner, repo_name, pr_number)
    threads = [CONST_GH_CLI, *review_threads_args(owner, repo_name, pr_number)]
    labels = [CONST_ROADMAP_SOURCE_AGENT_LABEL]
    issue = [CONST_GH_CLI, *create_issue_args(repo, "<title>", "<body>", labels)]
    reply = [CONST_GH_CLI, *reply_thread_args("<thread-id>", "<reply>")]
    resolve = [CONST_GH_CLI, *resolve_thread_args("<thread-id>")]
    return [
        PlannedRequest("REST read", details[2], argv=tuple(details)),
        PlannedRequest(
            "GraphQL read",
            f"{repo}#{pr_number}",
            argv=tuple(threads),
            condition=on_release,
            repeat=texts.threads_plan_page,
        ),
        PlannedRequest(
            "REST write", f"repos/{repo}/issues", argv=tuple(issue), condition=unfiled, repeat=each
        ),
        PlannedRequest(
            "GraphQL write", "<thread-id>", argv=tuple(reply), condition=unfiled, repeat=each
        ),
        PlannedRequest(
            "GraphQL write", "<thread-id>", argv=tuple(resolve), condition=not_kept, repeat=each
        ),
    ]


__all__ = [
    "ThreadFiling",
    "ThreadOutcome",
    "describe_filing",
    "file_thread_issues",
    "plan_thread_issues",
    "thread_issue_body",
    "thread_issue_title",
    "thread_location",
]
