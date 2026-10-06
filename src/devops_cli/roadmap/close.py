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

The current release is the lowest-numbered open Release. It is due to be cut when it holds no
open item, at least one item closed as completed, and no release pull request, open or merged:
one from `release/vX.Y.Z` into the default branch with the `release` label and the Release's
milestone. The cut itself is the caller's: `devops roadmap close` runs #982's `cut_release`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import PurePosixPath

from devops_cli.config.constants import (
    CONST_AGENT_TASKS_DIR,
    CONST_CHANGELOG_FRAGMENTS_DIR,
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
    CONST_ROADMAP_DOCUMENT_PATH,
)
"""The files the cut commit changes."""


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
class ClosePlan:
    """What a close run does. A dry run (`dry_run`) made no request, so it holds only the
    requests a run makes (`requests`) and the writes `--confirm` adds (`write_requests`)."""

    repo: str
    release: str | None = None
    closings: tuple[Closing, ...] = ()
    unread: tuple[str, ...] = ()
    open_items: tuple[IssueRecord, ...] = ()
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


def plan_close(store: RoadmapStore, *, repo: str, checks: ChecksReader) -> ClosePlan:
    """Read what the run closes, and whether it cuts the current release; write nothing."""
    from devops_cli.commands.release import _format_release_title

    release = current_release(store.releases())
    if release is None:
        return ClosePlan(repo=repo, hold=Hold.NO_RELEASE)
    branch = f"release/{release.title}"
    merged = store.merged_pull_requests(branch)
    issues = {issue.number: issue for issue in store.issues()}
    closings, unread = _closings(
        store, repo=repo, branch=branch, merged=merged, issues=issues, checks=checks
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
    plan = ClosePlan(
        repo=repo,
        release=release.title,
        closings=tuple(closings),
        unread=tuple(unread),
        open_items=still_open,
    )
    held = _held(plan, completed)
    if held is not None:
        return replace(plan, hold=held)
    version = str(release.version)
    cut_branch = release_cut_branch(version)
    default = store.default_branch().name
    cuts = [
        pull_request
        for pull_request in store.release_pull_requests(version)
        if pull_request.head == cut_branch
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
        branch=cut_branch,
        base=default,
        title=_format_release_title(version),
        fragments=fragments,
        missing_fragments=missing,
    )
    return replace(plan, cut=cut)


def _held(plan: ClosePlan, completed: Sequence[int]) -> Hold | None:
    if plan.unread:
        return Hold.UNREAD
    if plan.open_items:
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
    """The plan as text: each closing with its comment, then the cut or what holds it."""
    texts = MESSAGES.roadmap
    lines = [texts.close_title.format(repo=plan.repo, release=plan.release or "-"), ""]
    for closing in plan.closings:
        lines.append(
            texts.close_closing.format(number=closing.number, pull_request=closing.pull_request)
        )
        lines.extend(f"    {line}" if line else "" for line in closing.comment.splitlines())
        lines.append("")
    if not plan.closings and not plan.unread:
        lines.extend([texts.close_nothing, ""])
    lines.extend(plan.unread)
    if plan.cut is not None:
        lines.extend(_cut_lines(plan.cut))
    elif plan.hold is not None:
        lines.append(
            texts.close_holds[plan.hold.value].format(
                release=plan.release, number=plan.hold_pull_request
            )
        )
        lines.extend(
            texts.close_open_item.format(number=issue.number, title=issue.title)
            for issue in plan.open_items
        )
    return "\n".join(lines).rstrip() + "\n"


def _cut_lines(cut: Cut) -> list[str]:
    texts = MESSAGES.roadmap
    lines = [
        texts.close_cut.format(branch=cut.branch, base=cut.base, title=cut.title),
        texts.close_cut_files.format(files=", ".join(cut.files)),
        texts.close_cut_fragments.format(fragments=", ".join(cut.fragments) or texts.close_none),
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
