"""The window of a project review: two first-parent commits and two UTC times, half-open (#4686).

A person names the window as two version tags (`--version A..B`), one ISO week (`--week`), two
times (`--since`, `--until`) or the days up to now (`--last`). A tag becomes its commit, and the
times of the window are the commit times of the two tags. A time becomes the last first-parent
commit of the default branch at or before it. Each time is an aware UTC value before any compare,
so tags written in different time zones compare by the instant. The base commit and the start time
are out of the window, and the head commit and the end time are in.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, assert_never

from packaging.version import InvalidVersion, Version

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.project_review.data import ReviewWindow, WindowKind
from devops_cli.roadmap.project_review.git_read import (
    commit_before_args,
    commit_line,
    default_ref_args,
    run_git,
    tag_args,
    tag_commit_args,
    try_git,
)

_ID_TIME: Final = "%Y%m%dT%H%MZ"
_LAST: Final = re.compile(r"(?P<days>[1-9][0-9]*)d")
# A character that a window id does not hold: the id is a path segment and a key.
_UNSAFE: Final = re.compile(r"[^A-Za-z0-9._-]")
_WEEK: Final = timedelta(days=7)
# The ref of a checkout with no origin: its own HEAD.
_LOCAL_HEAD: Final = "HEAD"


@dataclass(frozen=True)
class Tag:
    """A release tag and its creation time in UTC."""

    name: str
    created: datetime


@dataclass(frozen=True)
class VersionRequest:
    """A window between two version tags: the base tag is out, and the head tag is in."""

    id: str
    base_tag: str
    head_tag: str


@dataclass(frozen=True)
class PeriodRequest:
    """A window between two UTC times: an ISO week, two times, or the days up to now."""

    kind: WindowKind
    id: str
    start: datetime
    end: datetime
    previous_id: str


WindowRequest = VersionRequest | PeriodRequest


def _refuse(text: str) -> RoadmapReviewError:
    return RoadmapReviewError(text)


def _utc(text: str, option: str) -> datetime:
    """`text` as an aware UTC time. A time with no offset is in UTC."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as exc:
        raise _refuse(MESSAGES.roadmap.review_bad_time.format(option=option, text=text)) from exc
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def _period_id(start: datetime, end: datetime) -> str:
    return f"{start:{_ID_TIME}}..{end:{_ID_TIME}}"


def _week_id(start: datetime) -> str:
    year, week, _ = start.isocalendar()
    return f"{year}-W{week:02d}"


def _period(kind: WindowKind, start: datetime, end: datetime) -> PeriodRequest:
    if end <= start:
        raise _refuse(MESSAGES.roadmap.review_empty_window.format(start=start, end=end))
    if kind is WindowKind.WEEK:
        return PeriodRequest(kind, _week_id(start), start, end, _week_id(start - _WEEK))
    before = start - (end - start)
    return PeriodRequest(kind, _period_id(start, end), start, end, _period_id(before, start))


def _version_id(base: str, head: str) -> str:
    return f"{_UNSAFE.sub('-', base)}..{_UNSAFE.sub('-', head)}"


def _version(text: str) -> VersionRequest:
    base, dots, head = text.partition("..")
    if not dots or not base or not head or head.startswith("."):
        raise _refuse(MESSAGES.roadmap.review_bad_version.format(text=text))
    return VersionRequest(_version_id(base, head), base, head)


def _week(text: str) -> PeriodRequest:
    try:
        start = datetime.strptime(f"{text}-1", "%G-W%V-%u").replace(tzinfo=UTC)
    except ValueError as exc:
        raise _refuse(MESSAGES.roadmap.review_bad_week.format(text=text)) from exc
    return _period(WindowKind.WEEK, start, start + _WEEK)


def _last(text: str, now: datetime) -> PeriodRequest:
    found = _LAST.fullmatch(text)
    if found is None:
        raise _refuse(MESSAGES.roadmap.review_bad_last.format(text=text))
    end = now.astimezone(UTC).replace(second=0, microsecond=0)
    return _period(WindowKind.PERIOD, end - timedelta(days=int(found["days"])), end)


def parse_window(
    *,
    version: str | None = None,
    since: str | None = None,
    until: str | None = None,
    week: str | None = None,
    last: str | None = None,
    now: datetime,
) -> WindowRequest:
    """The one window that the options name. `now` ends a `--last` window."""
    named = [given for given in (version, since or until, week, last) if given]
    if len(named) != 1 or (since is None) != (until is None):
        raise _refuse(MESSAGES.roadmap.review_one_window)
    if version:
        return _version(version)
    if week:
        return _week(week)
    if last:
        return _last(last, now)
    return _period(WindowKind.PERIOD, _utc(since or "", "--since"), _utc(until or "", "--until"))


def read_tags(checkout: Path) -> list[Tag]:
    """The release tags of the checkout, with their creation times in UTC, oldest first."""
    tags = []
    for line in run_git(checkout, tag_args()).splitlines():
        name, _, seconds = line.rpartition("\t")
        if name and seconds:
            tags.append(Tag(name, datetime.fromtimestamp(int(seconds), UTC)))
    return sorted(tags, key=lambda tag: (tag.created, tag.name))


def tags_in(tags: Sequence[Tag], start: datetime, end: datetime) -> list[Tag]:
    """The tags created after `start` and at or before `end`."""
    return [tag for tag in tags if start < tag.created <= end]


def _version_of(name: str) -> Version | None:
    try:
        return Version(name)
    except InvalidVersion:
        return None


def _previous_version_id(base: str, count: int, tags: Sequence[Tag]) -> str | None:
    """The version window that ends at `base` and holds `count` releases, in version order."""
    ordered = sorted(
        (version, tag.name) for tag in tags if (version := _version_of(tag.name)) is not None
    )
    names = [name for _, name in ordered]
    if count < 1 or base not in names or names.index(base) < count:
        return None
    return _version_id(names[names.index(base) - count], base)


def _tag_commit(checkout: Path, tag: str) -> tuple[str, datetime]:
    found = try_git(checkout, tag_commit_args(tag))
    line = commit_line(found) if found else None
    if line is None:
        raise _refuse(MESSAGES.roadmap.review_unknown_tag.format(tag=tag))
    return line


def _commit_before(checkout: Path, ref: str, at: datetime) -> str:
    line = commit_line(run_git(checkout, commit_before_args(ref, f"@{int(at.timestamp())}")))
    if line is None:
        raise _refuse(MESSAGES.roadmap.review_no_commit.format(ref=ref, time=at.isoformat()))
    return line[0]


def default_ref(checkout: Path) -> str:
    """The default branch of the origin, or the HEAD of a checkout with no origin."""
    found = try_git(checkout, default_ref_args())
    return found.strip() if found and found.strip() else _LOCAL_HEAD


def resolve_window(checkout: Path, request: WindowRequest, tags: Sequence[Tag]) -> ReviewWindow:
    """The commits and the UTC times of the window that `request` names."""
    match request:
        case VersionRequest():
            base, start = _tag_commit(checkout, request.base_tag)
            head, end = _tag_commit(checkout, request.head_tag)
            if end <= start:
                raise _refuse(MESSAGES.roadmap.review_empty_window.format(start=start, end=end))
            count = len(tags_in(tags, start, end))
            previous = _previous_version_id(request.base_tag, count, tags)
            kind = WindowKind.VERSION
        case PeriodRequest():
            ref = default_ref(checkout)
            start, end, kind = request.start, request.end, request.kind
            base, head = _commit_before(checkout, ref, start), _commit_before(checkout, ref, end)
            previous = request.previous_id
        case _:
            assert_never(request)
    return ReviewWindow(
        kind=kind,
        id=request.id,
        base_sha=base,
        head_sha=head,
        start=start,
        end=end,
        previous_id=previous,
    )
