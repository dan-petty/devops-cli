"""`devops roadmap close`: close each delivered item with a summary, and cut the release once
it holds no open item (#743).

Item pull requests target `release/vX.Y.Z`, and GitHub honours `Closes #N` only in a pull request
into the default branch, so this job does the closing: it reads every pull request merged into
the current release's branch, and closes as completed each open issue a body closes with a
closing keyword, commenting first with what changed (the pull request, its merge commit, the
first section of its body and its changed-file count) and how it was verified (each check run
with its bucket, and the Acceptance Criteria of the issue's task file at the merge commit). The
comment is a fixed template: pull request text is untrusted data and no model reads it.

A pull request whose check runs can't be read closes nothing; the run names it and fails, and
the next run retries. Issues already closed get nothing, so a second run writes nothing.

A milestone can close while an item delivered into its branch is still open: release.yml, the
release tag, reprioritize, a person or the web UI closes it whatever its items. So closure also
reads the branch of each closed Release that still holds an open issue, first, and closes the
open items of that Release its pull requests deliver; the rest it names, and none of them holds
the current release's cut (#1362). An item a person reopened it names and never closes, since a
job never reverts a person's change (ADR 0002). With no such Release, a run reads what it read
before.

The current release is the lowest-numbered open Release. It is due to be cut when it holds no
open item, at least one item closed as completed, and no release pull request, open or merged:
one from `release/vX.Y.Z` into the default branch with the `release` label and the Release's
milestone. The cut itself is the caller's: `devops roadmap close` runs #982's `cut_release`,
whose commit bumps the version, collects `changelog.d/` into the version's `CHANGELOG.md`
section, deleting the fragments, and renders `docs/ROADMAP.md` (#1450).
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath

from devops_cli.config.constants import (
    CONST_AGENT_TASKS_DIR,
    CONST_CHANGELOG_FILENAME,
    CONST_CHANGELOG_FRAGMENTS_DIR,
    CONST_GH_ISSUE_STATE_REASON_REOPENED,
    CONST_INIT_PY_PATH,
    CONST_PYPROJECT_FILENAME,
    CONST_ROADMAP_DOCUMENT_PATH,
    CONST_UV_LOCK_FILENAME,
)
from devops_cli.config.defaults import (
    DEFAULT_RELEASE_LABEL,
    DEFAULT_ROADMAP_CLOSE_SUMMARY_CHARS,
)
from devops_cli.dry_run.requests import PlannedRequest
from devops_cli.exceptions.git import GitHubFileNotFoundError
from devops_cli.github.check_verdict import CheckVerdictSummary
from devops_cli.github.issue_closure import extract_linked_issues
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.store import (
    CloseReason,
    GitHubState,
    IssueRecord,
    MergedPullRequest,
    PullRequestState,
    Release,
    RoadmapStore,
    in_release,
    release_cut_branch,
)

ChecksReader = Callable[[MergedPullRequest], CheckVerdictSummary]
"""Reads a merged pull request's check runs at its head commit."""

CUT_FILES: tuple[str, ...] = (
    CONST_PYPROJECT_FILENAME,
    str(CONST_INIT_PY_PATH),
    CONST_UV_LOCK_FILENAME,
    CONST_CHANGELOG_FILENAME,
    CONST_ROADMAP_DOCUMENT_PATH,
)
"""The files the cut commit changes, besides the fragments it deletes."""


class Hold(StrEnum):
    """Why the current release is not cut."""

    NO_RELEASE = "no_release"
    UNREAD = "unread"
    OPEN_ITEMS = "open_items"
    NOTHING_DELIVERED = "nothing_delivered"
    PR_OPEN = "pr_open"
    PR_MERGED = "pr_merged"


@dataclass(frozen=True)
class Closing:
    """One issue the run closes as completed, the pull request that delivered it, the comment."""

    number: int
    pull_request: int
    comment: str


@dataclass(frozen=True)
class Cut:
    """The cut the run makes: the release pull request from `branch` into `base`."""

    version: str
    branch: str
    base: str
    title: str
    files: tuple[str, ...] = CUT_FILES
    fragments: tuple[str, ...] = ()
    missing_fragments: tuple[int, ...] = ()


@dataclass(frozen=True)
class ShippedClosure:
    """What the run does in a closed Release that still holds an open issue: the issues it
    closes, the pull requests whose check runs could not be read, the items left open, and the
    items a person reopened, which it never closes."""

    release: str
    closings: tuple[Closing, ...] = ()
    unread: tuple[str, ...] = ()
    open_items: tuple[IssueRecord, ...] = ()
    reopened: tuple[IssueRecord, ...] = ()


@dataclass(frozen=True)
class ClosePlan:
    """What a close run does. `closings` and `unread` cover the shipped releases first, each
    also in its `shipped` entry, then the current release; `open_items` and the hold are the
    current release's own. A dry run (`dry_run`) made no request, so it holds only the requests
    a run makes (`requests`) and the writes `--confirm` adds (`write_requests`)."""

    repo: str
    release: str | None = None
    closings: tuple[Closing, ...] = ()
    unread: tuple[str, ...] = ()
    open_items: tuple[IssueRecord, ...] = ()
    shipped: tuple[ShippedClosure, ...] = ()
    hold: Hold | None = None
    hold_pull_request: int | None = None
    cut: Cut | None = None
    dry_run: bool = False
    requests: tuple[PlannedRequest, ...] = ()
    write_requests: tuple[PlannedRequest, ...] = ()

    @property
    def has_writes(self) -> bool:
        return bool(self.closings or self.cut)


# ── Reading the pull request text ──


def _headings(text: str) -> list[tuple[int, int, str]]:
    """Each top-level heading of the Markdown `text`: its line, level and text."""
    from markdown_it import MarkdownIt

    tokens = MarkdownIt("commonmark").parse(text)
    return [
        (token.map[0], int(token.tag[1:]), tokens[index + 1].content.strip())
        for index, token in enumerate(tokens)
        if token.type == "heading_open" and token.level == 0 and token.map
    ]


def _trimmed(lines: Sequence[str]) -> list[str]:
    kept = list(lines)
    while kept and not kept[-1].strip():
        kept.pop()
    while kept and not kept[0].strip():
        kept.pop(0)
    return kept


def first_section(body: str) -> str:
    """The body's first section: its text before the first heading, or else its first heading's
    section, up to the next heading."""
    lines = body.splitlines()
    starts = [line for line, _, _ in _headings(body)]
    lead = _trimmed(lines[: starts[0]] if starts else lines)
    if lead or not starts:
        return "\n".join(lead)
    end = starts[1] if len(starts) > 1 else len(lines)
    return "\n".join(_trimmed(lines[starts[0] : end]))


def acceptance_criteria(text: str) -> list[str]:
    """The lines of the task file's Acceptance Criteria section, up to the next heading of the
    same or a higher level; none when it has no such section."""
    lines = text.splitlines()
    headings = _headings(text)
    wanted = MESSAGES.roadmap.close_criteria_heading.casefold()
    for index, (start, level, title) in enumerate(headings):
        if title.casefold() == wanted:
            later = [line for line, depth, _ in headings[index + 1 :] if depth <= level]
            return _trimmed(lines[start + 1 : later[0] if later else len(lines)])
    return []


def _quoted(text: str) -> str:
    """`text` capped at the configured length, as a Markdown quote."""
    capped = (
        text
        if len(text) <= DEFAULT_ROADMAP_CLOSE_SUMMARY_CHARS
        else (text[:DEFAULT_ROADMAP_CLOSE_SUMMARY_CHARS].rstrip() + "…")
    )
    return "\n".join(f"> {line}" if line else ">" for line in capped.splitlines())


def task_files(pull_request: MergedPullRequest, number: int) -> list[str]:
    """The task files of issue `number` the pull request added or changed."""
    pattern = f"{CONST_AGENT_TASKS_DIR}/task-{number}-*.md"
    return [path for path in pull_request.changed_paths if PurePosixPath(path).full_match(pattern)]


def closure_comment(
    pull_request: MergedPullRequest,
    branch: str,
    checks: CheckVerdictSummary,
    criteria: Sequence[tuple[str, Sequence[str]]],
) -> str:
    """The two-part comment closing an issue: what changed, and how it was verified."""
    texts = MESSAGES.roadmap
    summary = first_section(pull_request.body)
    changed = [
        texts.close_comment_changed,
        texts.close_comment_merged.format(
            url=pull_request.url, branch=branch, commit=pull_request.merge_commit
        ),
        *([_quoted(summary)] if summary else []),
        texts.close_comment_files.format(count=len(pull_request.changed_paths)),
    ]
    runs = [
        texts.close_comment_check.format(name=item.name, bucket=item.bucket.value)
        for item in checks.items
    ]
    verified = [
        texts.close_comment_verified,
        texts.close_comment_checks.format(commit=pull_request.head_commit),
        "\n".join(runs) if runs else texts.close_comment_no_checks,
    ]
    for path, lines in criteria:
        verified.append(texts.close_comment_task.format(path=path))
        verified.append("\n".join(lines) if lines else texts.close_comment_no_criteria)
    if not criteria:
        verified.append(texts.close_comment_no_task)
    return "\n\n".join([*changed, *verified]) + "\n"


# ── Planning ──


def current_release(releases: Sequence[Release]) -> Release | None:
    """The current release: the lowest-numbered open Release."""
    open_releases = [release for release in releases if release.state is GitHubState.OPEN]
    return min(open_releases, key=lambda release: release.version, default=None)


def _criteria(
    store: RoadmapStore, pull_request: MergedPullRequest, number: int
) -> list[tuple[str, list[str]]]:
    found = []
    for path in task_files(pull_request, number):
        try:
            text = store.repository_file(path, ref=pull_request.merge_commit)
        except GitHubFileNotFoundError:
            continue
        found.append((path, acceptance_criteria(text)))
    return found


def _closings(
    store: RoadmapStore,
    *,
    repo: str,
    branch: str,
    merged: Sequence[MergedPullRequest],
    issues: dict[int, IssueRecord],
    checks: ChecksReader,
) -> tuple[list[Closing], list[str]]:
    closings: list[Closing] = []
    unread: list[str] = []
    planned: set[int] = set()
    for pull_request in merged:
        targets = [
            linked.number
            for linked in extract_linked_issues(pull_request.body, repo)
            if linked.number in issues
            and issues[linked.number].state is GitHubState.OPEN
            and linked.number not in planned
        ]
        if not targets:
            continue
        verdicts = checks(pull_request)
        if verdicts.unread_reason:
            unread.append(
                MESSAGES.roadmap.close_unread.format(
                    number=pull_request.number,
                    issues=", ".join(f"#{n}" for n in targets),
                    reason=verdicts.unread_reason,
                )
            )
            continue
        for number in targets:
            criteria = _criteria(store, pull_request, number)
            comment = closure_comment(pull_request, branch, verdicts, criteria)
            closings.append(
                Closing(number=number, pull_request=pull_request.number, comment=comment)
            )
            planned.add(number)
    return closings, unread


def _fragments(
    store: RoadmapStore, numbers: Sequence[int], ref: str
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """The fragments of the completed items present on `ref`, and the items with none."""
    present: list[str] = []
    missing: list[int] = []
    for number in numbers:
        path = f"{CONST_CHANGELOG_FRAGMENTS_DIR}/{number}.md"
        try:
            store.repository_file(path, ref=ref)
        except GitHubFileNotFoundError:
            missing.append(number)
            continue
        present.append(path)
    return tuple(present), tuple(missing)


def _counts_open(release: Release) -> bool:
    """Whether a closed Release's milestone counts an open issue or pull request: an upper
    bound, so a run with no current release reads the issues only when one may hold an item."""
    return release.state is GitHubState.CLOSED and release.open_issues > 0


def _release_items(issues: dict[int, IssueRecord], release: Release) -> dict[int, IssueRecord]:
    return {n: issue for n, issue in issues.items() if in_release(issue.release, release.version)}


def _holds_open(issues: dict[int, IssueRecord]) -> bool:
    return any(issue.state is GitHubState.OPEN for issue in issues.values())


def _reopened(issue: IssueRecord) -> bool:
    """Whether a person reopened the issue: no roadmap job reopens one (ADR 0002)."""
    return (
        issue.state is GitHubState.OPEN
        and issue.state_reason == CONST_GH_ISSUE_STATE_REASON_REOPENED
    )


def _shipped_closure(
    store: RoadmapStore,
    *,
    repo: str,
    release: Release,
    issues: dict[int, IssueRecord],
    checks: ChecksReader,
) -> ShippedClosure:
    """Close the open items of the closed `release` that its branch's pull requests deliver,
    and name the rest; `issues` are its own, so an item moved out of it is never closed here.
    An item a person reopened is named and never closed, and with no other item open the
    release's pull requests are not read."""
    reopened = tuple(issue for issue in issues.values() if _reopened(issue))
    closable = {
        number: issue
        for number, issue in issues.items()
        if issue.state is GitHubState.OPEN and not _reopened(issue)
    }
    if not closable:
        return ShippedClosure(release=release.title, reopened=reopened)
    branch = release_cut_branch(str(release.version))
    closings, unread = _closings(
        store,
        repo=repo,
        branch=branch,
        merged=store.merged_pull_requests(branch),
        issues=closable,
        checks=checks,
    )
    closing = {closed.number for closed in closings}
    return ShippedClosure(
        release=release.title,
        closings=tuple(closings),
        unread=tuple(unread),
        open_items=tuple(issue for issue in closable.values() if issue.number not in closing),
        reopened=reopened,
    )


def _without(shipped: ShippedClosure, closed: Collection[int]) -> ShippedClosure:
    """`shipped` without the items the current release's pull requests close, which the run
    names as closings, not also as left open."""
    return replace(
        shipped,
        open_items=tuple(issue for issue in shipped.open_items if issue.number not in closed),
        reopened=tuple(issue for issue in shipped.reopened if issue.number not in closed),
    )


def plan_close(store: RoadmapStore, *, repo: str, checks: ChecksReader) -> ClosePlan:
    """Read what the run closes, in each closed Release that still holds an open issue and then
    in the current release, and whether it cuts the current release; write nothing."""
    releases = store.releases()
    release = current_release(releases)
    if release is None and not any(_counts_open(closed) for closed in releases):
        return ClosePlan(repo=repo, hold=Hold.NO_RELEASE)
    issues = {issue.number: issue for issue in store.issues()}
    owned = (
        (closed, _release_items(issues, closed))
        for closed in releases
        if closed.state is GitHubState.CLOSED
    )
    shipped = tuple(
        _shipped_closure(store, repo=repo, release=closed, issues=own, checks=checks)
        for closed, own in owned
        if _holds_open(own)
    )
    plan = ClosePlan(
        repo=repo,
        closings=tuple(closing for part in shipped for closing in part.closings),
        unread=tuple(line for part in shipped for line in part.unread),
        shipped=shipped,
    )
    if release is None:
        return replace(plan, hold=Hold.NO_RELEASE)
    planned = {closing.number for closing in plan.closings}
    unplanned = {number: issue for number, issue in issues.items() if number not in planned}
    current = _plan_current(store, plan, release=release, issues=unplanned, checks=checks)
    closed = {closing.number for closing in current.closings}
    return replace(current, shipped=tuple(_without(part, closed) for part in current.shipped))


def _plan_current(
    store: RoadmapStore,
    plan: ClosePlan,
    *,
    release: Release,
    issues: dict[int, IssueRecord],
    checks: ChecksReader,
) -> ClosePlan:
    """`plan` with the current release's closings after the shipped ones, and its cut or what
    holds it, which reads only the current release's items and pull requests."""
    from devops_cli.commands.release import _format_release_title

    version = str(release.version)
    branch = release_cut_branch(version)
    merged = store.merged_pull_requests(branch)
    closings, unread = _closings(
        store, repo=plan.repo, branch=branch, merged=merged, issues=issues, checks=checks
    )
    closing = {closed.number for closed in closings}
    items = [issue for issue in issues.values() if in_release(issue.release, release.version)]
    still_open = tuple(
        issue for issue in items if issue.state is GitHubState.OPEN and issue.number not in closing
    )
    completed = sorted(
        issue.number
        for issue in items
        if issue.number in closing or issue.state_reason == CloseReason.COMPLETED.value
    )
    plan = replace(
        plan,
        release=release.title,
        closings=(*plan.closings, *closings),
        unread=(*plan.unread, *unread),
        open_items=still_open,
    )
    held = _held(unread, still_open, completed)
    if held is not None:
        return replace(plan, hold=held)
    default = store.default_branch().name
    cuts = [
        pull_request
        for pull_request in store.release_pull_requests(version)
        if pull_request.head == branch
        and pull_request.base == default
        and DEFAULT_RELEASE_LABEL in pull_request.labels
    ]
    for state, hold in (
        (PullRequestState.OPEN, Hold.PR_OPEN),
        (PullRequestState.MERGED, Hold.PR_MERGED),
    ):
        found = next((pull_request for pull_request in cuts if pull_request.state is state), None)
        if found is not None:
            return replace(plan, hold=hold, hold_pull_request=found.number)
    fragments, missing = _fragments(store, completed, branch)
    cut = Cut(
        version=version,
        branch=branch,
        base=default,
        title=_format_release_title(version),
        fragments=fragments,
        missing_fragments=missing,
    )
    return replace(plan, cut=cut)


def _held(
    unread: Sequence[str], open_items: Sequence[IssueRecord], completed: Sequence[int]
) -> Hold | None:
    """What holds the current release's cut, from its own reads alone."""
    if unread:
        return Hold.UNREAD
    if open_items:
        return Hold.OPEN_ITEMS
    if not completed:
        return Hold.NOTHING_DELIVERED
    return None


def dry_run_close(repo: str, *, ref: str | None) -> ClosePlan:
    """The result a dry run returns, having made no request."""
    from devops_cli.roadmap.request_plan import close_requests

    reads, writes = close_requests(repo, ref)
    return ClosePlan(repo=repo, dry_run=True, requests=reads, write_requests=writes)


def apply_close(store: RoadmapStore, plan: ClosePlan, cut: Callable[[Cut], None]) -> None:
    """Close each planned issue, comment first, then make the planned cut."""
    for closing in plan.closings:
        store.close_issue(closing.number, CloseReason.COMPLETED, closing.comment)
    if plan.cut is not None:
        cut(plan.cut)


# ── Reporting ──


def render_close(plan: ClosePlan) -> str:
    """The plan as text: each shipped release it reads, then the current release's closings
    with their comments, then the cut or what holds it."""
    texts = MESSAGES.roadmap
    lines = [texts.close_title.format(repo=plan.repo, release=plan.release or "-"), ""]
    for shipped in plan.shipped:
        lines.extend(_shipped_lines(shipped))
    if plan.release is not None or not plan.shipped:
        lines.extend(_current_lines(plan))
    if plan.cut is not None:
        lines.extend(_cut_lines(plan.cut))
    elif plan.hold is not None:
        lines.append(
            texts.close_holds[plan.hold.value].format(
                release=plan.release, number=plan.hold_pull_request
            )
        )
        lines.extend(_item_lines(plan.open_items))
    return "\n".join(lines).rstrip() + "\n"


def _current_lines(plan: ClosePlan) -> list[str]:
    """The current release's closings and unread pull requests, which follow the shipped ones'
    in the plan, under a heading when a shipped release comes before them."""
    texts = MESSAGES.roadmap
    heading = [texts.close_current_heading.format(release=plan.release), ""]
    closings = plan.closings[sum(len(shipped.closings) for shipped in plan.shipped) :]
    unread = plan.unread[sum(len(shipped.unread) for shipped in plan.shipped) :]
    return [
        *(heading if plan.shipped else []),
        *_closing_lines(closings),
        *([] if closings or unread else [texts.close_nothing, ""]),
        *unread,
    ]


def _closing_lines(closings: Sequence[Closing]) -> list[str]:
    texts = MESSAGES.roadmap
    lines: list[str] = []
    for closing in closings:
        lines.append(
            texts.close_closing.format(number=closing.number, pull_request=closing.pull_request)
        )
        lines.extend(f"    {line}" if line else "" for line in closing.comment.splitlines())
        lines.append("")
    return lines


def _item_lines(items: Sequence[IssueRecord]) -> list[str]:
    texts = MESSAGES.roadmap
    return [texts.close_open_item.format(number=issue.number, title=issue.title) for issue in items]


def _shipped_lines(shipped: ShippedClosure) -> list[str]:
    texts = MESSAGES.roadmap
    lines = [texts.close_shipped_heading.format(release=shipped.release), ""]
    lines.extend(_closing_lines(shipped.closings))
    lines.extend(shipped.unread)
    if shipped.open_items:
        lines.append(texts.close_shipped_open.format(release=shipped.release))
        lines.extend(_item_lines(shipped.open_items))
    if shipped.reopened:
        lines.append(texts.close_shipped_reopened.format(release=shipped.release))
        lines.extend(_item_lines(shipped.reopened))
    return [*lines, ""]


def _cut_lines(cut: Cut) -> list[str]:
    texts = MESSAGES.roadmap
    lines = [
        texts.close_cut.format(branch=cut.branch, base=cut.base, title=cut.title),
        texts.close_cut_files.format(files=", ".join(cut.files)),
        texts.close_cut_fragments.format(
            version=cut.version, fragments=", ".join(cut.fragments) or texts.close_none
        ),
    ]
    if cut.missing_fragments:
        missing = ", ".join(f"#{number}" for number in cut.missing_fragments)
        lines.append(texts.close_cut_missing.format(items=missing))
    return lines


__all__ = [
    "CUT_FILES",
    "ClosePlan",
    "Closing",
    "Cut",
    "Hold",
    "ShippedClosure",
    "acceptance_criteria",
    "apply_close",
    "closure_comment",
    "current_release",
    "dry_run_close",
    "first_section",
    "plan_close",
    "render_close",
    "task_files",
]
