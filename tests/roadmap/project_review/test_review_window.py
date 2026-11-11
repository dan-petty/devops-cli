"""The window of a project review (#4686): the options name one window, a tag becomes its commit,
a time becomes the last first-parent commit at or before it, and every time compares in UTC. The
base commit and the start time are out of the window, and the head commit and the end time are in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.roadmap import RoadmapReviewError
from devops_cli.roadmap.project_review.data import ReviewWindow, WindowKind
from devops_cli.roadmap.project_review.window import (
    PeriodRequest,
    Tag,
    VersionRequest,
    parse_window,
    read_tags,
    resolve_window,
    tags_in,
)
from tests.support.fakes.git import GitFake

NOW = datetime(2026, 10, 6, 12, 34, 56, tzinfo=UTC)
START = datetime(2026, 9, 25, 10, tzinfo=UTC)
V110 = datetime(2026, 10, 3, 10, tzinfo=UTC)
V111 = datetime(2026, 10, 5, 6, 30, tzinfo=UTC)


@pytest.fixture
def checkout(git_fake: GitFake, tmp_path: Path) -> Path:
    """The repository of the scenario `review_window`, as git answered for it."""
    git_fake.replay("review_window")
    return tmp_path / "project"


def _resolve(checkout: Path, **options: Any) -> ReviewWindow:
    return resolve_window(checkout, parse_window(now=NOW, **options), read_tags(checkout))


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"version": "v1.0.0..v1.1.0", "week": "2026-W40"},
        {"since": "2026-10-01T00:00:00Z"},
        {"until": "2026-10-01T00:00:00Z", "last": "7d"},
    ],
)
def test_the_options_name_exactly_one_window(options: dict[str, str]) -> None:
    with pytest.raises(RoadmapReviewError, match="Give one window") as caught:
        parse_window(now=NOW, **options)

    assert (caught.value.error_code, caught.value.exit_code) == ("ROADMAP_REVIEW_FAILED", 1)


@pytest.mark.parametrize(
    ("options", "message"),
    [
        ({"version": "v1.0.0"}, "--version takes two tags as A..B, not 'v1.0.0'"),
        ({"version": "v1.0.0...v1.1.0"}, "--version takes two tags"),
        ({"week": "2026-45"}, "--week takes an ISO week"),
        ({"last": "7"}, "--last takes a number of days"),
        ({"since": "yesterday", "until": "2026-10-01"}, "--since takes an ISO 8601 time"),
        ({"since": "2026-10-02", "until": "2026-10-01"}, "is not after its start"),
    ],
)
def test_a_malformed_window_is_refused_with_its_option(
    options: dict[str, str], message: str
) -> None:
    with pytest.raises(RoadmapReviewError, match=message):
        parse_window(now=NOW, **options)


def test_a_week_runs_from_monday_to_monday_in_utc_after_the_week_before() -> None:
    assert parse_window(week="2026-W45", now=NOW) == PeriodRequest(
        WindowKind.WEEK,
        "2026-W45",
        datetime(2026, 11, 2, tzinfo=UTC),
        datetime(2026, 11, 9, tzinfo=UTC),
        "2026-W44",
    )


def test_two_times_become_utc_and_a_time_with_no_offset_is_utc() -> None:
    request = parse_window(since="2026-11-04T07:51:23-07:00", until="2026-11-11T14:51:23", now=NOW)

    assert request == PeriodRequest(
        WindowKind.PERIOD,
        "20261104T1451Z..20261111T1451Z",
        datetime(2026, 11, 4, 14, 51, 23, tzinfo=UTC),
        datetime(2026, 11, 11, 14, 51, 23, tzinfo=UTC),
        "20261028T1451Z..20261104T1451Z",
    )


def test_the_last_days_end_at_the_start_of_this_minute() -> None:
    assert parse_window(last="7d", now=NOW) == PeriodRequest(
        WindowKind.PERIOD,
        "20260929T1234Z..20261006T1234Z",
        datetime(2026, 9, 29, 12, 34, tzinfo=UTC),
        datetime(2026, 10, 6, 12, 34, tzinfo=UTC),
        "20260922T1234Z..20260929T1234Z",
    )


def test_a_version_window_id_is_safe_for_a_path() -> None:
    assert parse_window(version="release/1.0..v1.1", now=NOW) == VersionRequest(
        "release-1.0..v1.1", "release/1.0", "v1.1"
    )


def test_tags_written_in_two_time_zones_compare_by_the_instant(checkout: Path) -> None:
    tags = read_tags(checkout)
    week = _resolve(checkout, week="2026-W40")

    assert tags == [Tag("v1.0.0", START), Tag("v1.1.0", V110), Tag("v1.1.1", V111)]
    assert tags_in(tags, week.start, week.end) == [Tag("v1.1.0", V110)]


def test_the_base_tag_is_out_of_a_version_window_and_the_head_tag_is_in(checkout: Path) -> None:
    tags = read_tags(checkout)
    window = _resolve(checkout, version="v1.0.0..v1.1.1")

    assert window.model_dump(exclude={"base_sha", "head_sha"}) == {
        "kind": WindowKind.VERSION,
        "id": "v1.0.0..v1.1.1",
        "start": START,
        "end": V111,
        "previous_id": None,
    }
    assert tags_in(tags, window.start, window.end) == [Tag("v1.1.0", V110), Tag("v1.1.1", V111)]


def test_a_version_window_names_the_window_before_with_as_many_releases(checkout: Path) -> None:
    assert _resolve(checkout, version="v1.1.0..v1.1.1").previous_id == "v1.0.0..v1.1.0"


def test_a_period_takes_the_last_first_parent_commit_at_or_before_each_time(
    checkout: Path,
) -> None:
    period = _resolve(checkout, since="2026-10-03T10:00:00Z", until="2026-10-05T06:30:00Z")
    tags = _resolve(checkout, version="v1.1.0..v1.1.1")

    assert (period.base_sha, period.head_sha) == (tags.base_sha, tags.head_sha)
    assert period.previous_id == "20261001T1330Z..20261003T1000Z"


def test_an_unknown_tag_and_a_time_before_the_history_are_refused(checkout: Path) -> None:
    with pytest.raises(RoadmapReviewError, match=r"no commit for the tag 'v9\.9\.9'"):
        _resolve(checkout, version="v1.0.0..v9.9.9")
    with pytest.raises(RoadmapReviewError, match="HEAD has no first-parent commit at or before"):
        _resolve(checkout, week="2026-W38")
