"""The release pull request's remaining review threads, filed as follow-up issues (#1345).

Once the release pull request's Copilot passes are spent, the stop rule in `RELEASE_CYCLE.md`
Step 3 lets a remaining review comment block the release only if it is a regression the release
introduces; every other one becomes a follow-up issue. A person runs `file_thread_issues`, which
files each unresolved thread not kept as one issue through the roadmap store, with no milestone,
labelled `source/agent` when Copilot started the thread, replies in the thread naming the issue,
and resolves the thread, in that order. A `--keep` id that names no unresolved thread stops the
run before any write, since the regression it meant to keep would be filed and resolved.

A rerun opens no second issue for a thread. The reply ends with a marker line giving the issue's
number, which counts only in a reply the account running the command wrote, so a thread whose
reply landed is only resolved. A thread whose issue was opened but whose reply failed is matched
to that issue by the link to its first comment, which the issue's body ends a line with, so it
gets the reply and is resolved. A failed reply or resolve names the issue already opened.

An issue quotes its thread's comments inside a fence longer than any in them, so a mention or an
issue reference in a comment neither notifies nor links. No model is called: `devops roadmap
intake` places the issue later, as an open issue not on the board.

This module is apart from `pr_threads.py`, which `pr_monitor.py` imports, because it reads the
pull request through `pr_monitor.py`.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_PR_THREAD_FILED_MARKER,
    CONST_PR_THREAD_FILED_MARKER_RE,
    CONST_ROADMAP_SOURCE_AGENT_LABEL,
)
from devops_cli.config.defaults import DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS
from devops_cli.dry_run.requests import PlannedRequest, both
from devops_cli.exceptions.git import GitHubOperationError, ThreadFilingRefusedError
from devops_cli.github.pr_branches import require_open_release_pr
from devops_cli.github.pr_monitor import fetch_pr_details, is_copilot_login, pr_details_argv
from devops_cli.github.pr_threads import (
    ReviewThread,
    list_pr_review_threads,
    read_viewer_login,
    reply_pr_review_thread,
    reply_thread_args,
    resolve_pr_review_thread,
    resolve_thread_args,
    review_threads_args,
    thread_comments_args,
    viewer_args,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import store as roadmap_store
from devops_cli.roadmap.github_store import create_issue_args, issues_endpoint, listing_page_args
from devops_cli.roadmap.store import GitHubState, IssueRecord, RoadmapStore

_FENCE_MIN = 3


class ThreadAction(StrEnum):
    """What a filing run does with one unresolved thread."""

    KEEP = "keep"
    FILE = "file"
    REUSE = "reuse"
    RESOLVE = "resolve"


class ThreadFiling(BaseModel):
    """One unresolved thread, what the run does or would do with it, and the issue it names."""

    model_config = ConfigDict(frozen=True)

    thread_id: str
    location: str
    title: str
    action: ThreadAction
    issue: int | None = None
    outdated: bool = False


def thread_location(thread: ReviewThread) -> str:
    """Where the thread sits: `path:line`, or the line it was opened on once a later push moved
    it out of the diff; for a thread on a whole file, its path and its first comment's id, which
    tell two such threads on one file apart."""
    line = thread.line if thread.line is not None else thread.original_line
    if line is not None:
        return f"{thread.path}:{line}"
    first = thread.comments[0].id if thread.comments else thread.id
    return MESSAGES.pr.thread_location_file.format(path=thread.path, comment=first)


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


def _first_link(thread: ReviewThread) -> str:
    """The link to the thread's first comment; empty when GitHub gave none."""
    return thread.comments[0].url if thread.comments else ""


def thread_issue_body(pr_number: int, thread: ReviewThread) -> str:
    """The follow-up issue's body: the thread's comments inside a fence, then a line holding its
    location and ending with the link to its first comment."""
    text = _thread_text(thread)
    fence = _fence_for(text)
    url = _first_link(thread)
    location = thread_location(thread)
    source = MESSAGES.pr.thread_issue_source.format(location=location, url=url) if url else location
    intro = MESSAGES.pr.thread_issue_intro.format(number=pr_number)
    return f"{intro}\n\n{fence}\n{text}\n{fence}\n\n{source}\n"


def _filed_issue(thread: ReviewThread, viewer: str) -> int | None:
    """The issue an earlier run by `viewer` filed the thread as: the number on a line, matched
    whole, of a reply `viewer` wrote; never the first comment, never anyone else's reply."""
    own = viewer.casefold()
    replies = (c.body for c in thread.comments[1:] if c.author.casefold() == own)
    lines = (line for body in replies for line in body.splitlines())
    found = (CONST_PR_THREAD_FILED_MARKER_RE.fullmatch(line) for line in lines)
    return next((int(match.group(1)) for match in found if match), None)


def _ends_a_line_with(body: str, url: str) -> bool:
    """Whether a line of `body` ends with `url`, as a follow-up issue's source line does."""
    return any(line.rstrip().endswith(url) for line in body.splitlines())


def _linking_issue(issues: Sequence[IssueRecord], url: str) -> int | None:
    """The first open issue whose body ends a line with `url`; None for an empty link."""
    if not url:
        return None
    linking = (
        issue.number
        for issue in issues
        if issue.state is GitHubState.OPEN and _ends_a_line_with(issue.body, url)
    )
    return next(linking, None)


@dataclass
class _FilingRun:
    """One run's reads, each made once and only when a thread needs it."""

    repo: str

    @cached_property
    def viewer(self) -> str:
        """The account the replies are written as."""
        return read_viewer_login()

    @cached_property
    def store(self) -> RoadmapStore:
        """The roadmap store the issues are opened and found through."""
        return roadmap_store.get_roadmap_store(self.repo)

    @cached_property
    def issues(self) -> list[IssueRecord]:
        """Every issue the store lists, read once, to find one that already links a thread."""
        return self.store.issues()


def _require_known(keep: frozenset[str], threads: Sequence[ReviewThread], number: int) -> None:
    """Refuse a `--keep` id that names no unresolved thread, before anything is written: the
    regression a mistyped id meant to keep would be filed and resolved."""
    unknown = sorted(keep - {thread.id for thread in threads})
    if not unknown:
        return
    ids = ", ".join(unknown)
    raise ThreadFilingRefusedError(
        MESSAGES.pr.threads_unknown_keep.format(ids=ids, number=number),
        details={"pull_request": number, "unknown_keep": ids},
    )


def _decide(
    thread: ReviewThread, pr_number: int, keep: frozenset[str], run: _FilingRun
) -> ThreadFiling:
    """What the run does with one thread: keep it, resolve it when the viewer's reply names its
    issue, reply and resolve when an open issue links it, and otherwise file it."""
    filing = ThreadFiling(
        thread_id=thread.id,
        location=thread_location(thread),
        title=thread_issue_title(pr_number, thread),
        action=ThreadAction.KEEP,
        outdated=thread.is_outdated,
    )
    if thread.id in keep:
        return filing
    filed = _filed_issue(thread, run.viewer)
    if filed is not None:
        return filing.model_copy(update={"action": ThreadAction.RESOLVE, "issue": filed})
    linking = _linking_issue(run.issues, _first_link(thread))
    if linking is not None:
        return filing.model_copy(update={"action": ThreadAction.REUSE, "issue": linking})
    return filing.model_copy(update={"action": ThreadAction.FILE})


def _open_issue(thread: ReviewThread, pr_number: int, run: _FilingRun) -> int:
    """Open the thread's issue, labelled `source/agent` only when Copilot started the thread,
    since the label says a model wrote the text."""
    copilot = bool(thread.comments) and is_copilot_login(thread.comments[0].author)
    labels = (CONST_ROADMAP_SOURCE_AGENT_LABEL,) if copilot else ()
    title, body = thread_issue_title(pr_number, thread), thread_issue_body(pr_number, thread)
    return run.store.create_issue(title, body, labels=labels).number


def _answer(filing: ThreadFiling, *, reply: bool) -> None:
    """Reply in the thread naming its issue when `reply`, then resolve it. A failure names the
    issue, which is open, and the thread, which a rerun finishes without a second issue."""
    issue = filing.issue
    try:
        if reply:
            named = MESSAGES.pr.thread_filed_reply.format(issue=issue)
            marker = CONST_PR_THREAD_FILED_MARKER.format(issue=issue)
            reply_pr_review_thread(filing.thread_id, f"{named}\n\n{marker}")
        resolve_pr_review_thread(filing.thread_id)
    except GitHubOperationError as exc:
        error = str(exc)
        raise GitHubOperationError(
            MESSAGES.pr.thread_answer_failed.format(
                thread=filing.thread_id, location=filing.location, issue=issue, error=error
            ),
            operation="threads_file_issues.answer",
            details={"thread": filing.thread_id, "issue": issue, "error": error[:256]},
        ) from exc


def _carry_out(
    filing: ThreadFiling, thread: ReviewThread, pr_number: int, run: _FilingRun
) -> ThreadFiling:
    """Do what `filing` says: open the issue first when the thread has none, then reply naming
    it unless the viewer's reply already does, then resolve the thread."""
    if filing.action is ThreadAction.KEEP:
        return filing
    if filing.action is ThreadAction.FILE:
        filing = filing.model_copy(update={"issue": _open_issue(thread, pr_number, run)})
    _answer(filing, reply=filing.action is not ThreadAction.RESOLVE)
    return filing


def file_thread_issues(
    owner: str,
    repo_name: str,
    pr_number: int,
    *,
    keep: Iterable[str] = (),
    confirm: bool = False,
) -> Iterator[ThreadFiling]:
    """File each unresolved thread of the open release pull request `pr_number` not in `keep`
    as a follow-up issue, reply naming it and resolve the thread, one thread after another,
    yielding each as it is done; without `confirm`, make the same reads and yield what each
    thread would get, writing nothing.

    Raises `ThreadFilingRefusedError` before any thread is read when the pull request is not
    open or not the release pull request, and before any write when a `keep` id names no
    unresolved thread. A failed write stops the run where it failed, after the threads before it
    were yielded; a failed reply or resolve names the issue it had opened.
    """
    require_open_release_pr(
        fetch_pr_details(owner, repo_name, pr_number),
        pr_number,
        refused=ThreadFilingRefusedError,
        not_open=MESSAGES.pr.threads_not_open,
        not_release=MESSAGES.pr.threads_not_release_pr,
    )
    threads = list_pr_review_threads(owner, repo_name, pr_number, unresolved_only=True)
    kept = frozenset(keep)
    _require_known(kept, threads, pr_number)
    run = _FilingRun(f"{owner}/{repo_name}")
    for thread in threads:
        filing = _decide(thread, pr_number, kept, run)
        yield _carry_out(filing, thread, pr_number, run) if confirm else filing


def describe_filing(filing: ThreadFiling, *, confirm: bool) -> str:
    """One line saying what the run did, or would do, with a thread, marking an outdated one."""
    texts = MESSAGES.pr
    templates = {
        ThreadAction.KEEP: (texts.thread_kept, texts.thread_kept),
        ThreadAction.FILE: (texts.thread_to_file, texts.thread_filed),
        ThreadAction.REUSE: (texts.thread_to_reuse, texts.thread_reused),
        ThreadAction.RESOLVE: (texts.thread_seen_filed, texts.thread_resolved_filed),
    }
    line = templates[filing.action][confirm].format(
        thread=filing.thread_id, location=filing.location, title=filing.title, issue=filing.issue
    )
    return f"{line} {texts.thread_outdated}" if filing.outdated else line


def _planned(
    method: str, target: str, args: list[str], condition: str = "", repeat: str = ""
) -> PlannedRequest:
    """A planned gh command, its argv the one the real run sends."""
    argv = (CONST_GH_CLI, *args)
    return PlannedRequest(method, target, argv=argv, condition=condition, repeat=repeat)


def plan_thread_issues(repo: str, pr_number: int) -> list[PlannedRequest]:
    """The requests `file_thread_issues` makes with `confirm`, in order and with no value
    read (#412); each gh command is the argv the real run builds, with placeholders."""
    texts = MESSAGES.pr
    owner, repo_name = repo.split("/", 1)
    on_release = texts.threads_plan_release.format(number=pr_number)
    more_comments = both(on_release, texts.threads_plan_more_comments)
    not_kept = both(on_release, texts.threads_plan_not_kept)
    unanswered = both(on_release, texts.threads_plan_unanswered)
    unlinked = both(unanswered, texts.threads_plan_unlinked)
    each, page = texts.threads_plan_each, texts.threads_plan_page
    details = pr_details_argv(owner, repo_name, pr_number)
    issues = listing_page_args(issues_endpoint(repo), "<page>")
    labels = [CONST_ROADMAP_SOURCE_AGENT_LABEL]
    thread = "<thread-id>"
    return [
        PlannedRequest("REST read", details[2], argv=tuple(details)),
        _planned(
            "GraphQL read",
            f"{repo}#{pr_number}",
            review_threads_args(owner, repo_name, pr_number),
            on_release,
            page,
        ),
        _planned(
            "GraphQL read",
            thread,
            thread_comments_args(thread, "<cursor>"),
            more_comments,
            texts.threads_plan_comment_page,
        ),
        _planned("GraphQL read", "viewer", viewer_args(), not_kept),
        _planned("REST read", issues[-1], issues, unanswered, page),
        _planned(
            "REST write",
            f"repos/{repo}/issues",
            create_issue_args(repo, "<title>", "<body>", labels),
            unlinked,
            each,
        ),
        _planned("GraphQL write", thread, reply_thread_args(thread, "<reply>"), unanswered, each),
        _planned("GraphQL write", thread, resolve_thread_args(thread), not_kept, each),
    ]


__all__ = [
    "ThreadAction",
    "ThreadFiling",
    "describe_filing",
    "file_thread_issues",
    "plan_thread_issues",
    "thread_issue_body",
    "thread_issue_title",
    "thread_location",
]
