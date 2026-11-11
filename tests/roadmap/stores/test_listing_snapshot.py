"""The snapshot of the issue listing that intake keeps between runs, and the incremental read of the
issues changed since it (#4448).
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from devops_cli.exceptions.security import SecurityError
from devops_cli.github.session import get_github_session
from devops_cli.roadmap.stores.github_store import GitHubRoadmapStore
from devops_cli.roadmap.stores.listing_snapshot import (
    FileSnapshotStore,
    IncrementalListing,
    ListingSnapshot,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.roadmap_github_store import REPO, RecordedGh, issue_payload

STARTED = datetime(2026, 1, 1, 10, 0, tzinfo=UTC)
REPOSITORY_URL = f"https://api.github.com/repos/{REPO}"
FULL = f"/repos/{REPO}/issues?state=all&per_page=100"


def _since(at: str) -> str:
    """The path of the read of the issues changed since `at`, newest change first."""
    return f"/repos/{REPO}/issues?state=all&sort=updated&direction=desc&since={at}&per_page=100"


def _issue(number: int, *, updated: str = "2026-01-01T09:00:00Z", **changes: Any) -> Any:
    """Issue `number` as the listing gives it, last changed at `updated`."""
    return issue_payload(
        number, updated_at=updated, repository_url=REPOSITORY_URL, body="Text", **changes
    )


def _store(
    root: Path, *, at: datetime = STARTED, full: bool = False, version: str = "1.0.0"
) -> GitHubRoadmapStore:
    """A store that reads its listing at `at` through the snapshot that `root` holds."""
    listing = IncrementalListing(
        FileSnapshotStore(root), full=full, clock=lambda: at, version=version
    )
    return GitHubRoadmapStore(
        REPO, runner=RecordedGh({}), session=get_github_session(), listing=listing
    )


def _kept(root: Path) -> ListingSnapshot:
    kept = FileSnapshotStore(root).load(REPO)
    assert kept is not None
    return kept


def _queries(github_api: GitHubApiFake) -> list[dict[str, str]]:
    """The query of each request sent, in order."""
    return [dict(request.url.params) for request in github_api.sent]


def _first_run(github_api: GitHubApiFake, root: Path, *issues: Any) -> None:
    """Read the whole listing of `issues` once, which keeps the first snapshot."""
    github_api.route("GET", FULL, github_json(list(issues)))
    _store(root).issues()
    github_api.sent.clear()


def test_a_run_with_no_snapshot_reads_the_whole_listing_and_keeps_it(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    github_api.route("GET", FULL, github_json([_issue(n) for n in (3, 2, 1)]))
    numbers = [issue.number for issue in _store(tmp_path).issues()]
    kept = _kept(tmp_path)
    assert (numbers, _queries(github_api), [i.number for i in kept.issues], kept.full_at) == (
        [3, 2, 1],
        [{"state": "all", "per_page": "100"}],
        [3, 2, 1],
        STARTED,
    )


def test_a_later_run_reads_only_the_issues_changed_since_the_watermark(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """120 issues are kept; 20 of them change. The run sends one request, and each changed issue
    replaces its record."""
    _first_run(github_api, tmp_path, *(_issue(n) for n in range(120, 0, -1)))
    changed = [
        _issue(n, updated="2026-01-01T10:30:00Z", title=f"new title {n}") for n in range(20, 0, -1)
    ]
    github_api.route("GET", _since("2026-01-01T08:59:00Z"), github_json(changed))
    issues = _store(tmp_path, at=STARTED + timedelta(hours=1)).issues()
    titles = {issue.number: issue.title for issue in issues}
    assert (_queries(github_api), len(issues), titles[20], titles[21] == titles[120]) == (
        [
            {
                "state": "all",
                "sort": "updated",
                "direction": "desc",
                "since": "2026-01-01T08:59:00Z",
                "per_page": "100",
            }
        ],
        120,
        "new title 20",
        True,
    )


def test_an_unchanged_issue_comes_from_the_snapshot_and_is_not_read_again(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """The record of an issue that GitHub did not list as changed is the one the snapshot
    holds, so its body is not parsed again."""
    _first_run(github_api, tmp_path, _issue(2), _issue(1))
    kept = _kept(tmp_path)
    edited = kept.model_copy(
        update={"issues": tuple(i.model_copy(update={"body": "kept"}) for i in kept.issues)}
    )
    FileSnapshotStore(tmp_path).save(edited)
    github_api.route(
        "GET",
        _since("2026-01-01T08:59:00Z"),
        github_json([_issue(2, updated="2026-01-01T10:30:00Z")]),
    )
    bodies = {i.number: i.body for i in _store(tmp_path, at=STARTED + timedelta(hours=1)).issues()}
    assert bodies == {2: "Text", 1: "kept"}


@pytest.mark.parametrize(
    ("started", "newest", "watermark"),
    [
        # An issue changed during the read: the start of the read, less the overlap.
        (STARTED, "2026-01-01T10:00:30Z", "2026-01-01T09:59:00+00:00"),
        # The local clock is ahead of GitHub's: GitHub's newest change, less the overlap.
        (STARTED + timedelta(minutes=10), "2026-01-01T10:00:00Z", "2026-01-01T09:59:00+00:00"),
    ],
)
def test_the_watermark_is_the_earlier_of_the_start_and_the_newest_change_less_a_minute(
    github_api: GitHubApiFake, tmp_path: Path, started: datetime, newest: str, watermark: str
) -> None:
    github_api.route("GET", FULL, github_json([_issue(2, updated=newest), _issue(1)]))
    _store(tmp_path, at=started).issues()
    assert _kept(tmp_path).watermark.isoformat() == watermark


@pytest.mark.parametrize(
    ("later", "changes"),
    [
        ({"full": True}, "the flag"),
        ({"version": "2.0.0"}, "another version"),
        ({"at": STARTED + timedelta(hours=25)}, "an old full read"),
    ],
)
def test_the_whole_listing_is_read_again_and_replaces_the_snapshot(
    github_api: GitHubApiFake, tmp_path: Path, later: dict[str, Any], changes: str
) -> None:
    """`--full`, a snapshot that another version wrote, and a snapshot whose last full read is
    older than a day are read in full, not from the watermark."""
    _first_run(github_api, tmp_path, _issue(2), _issue(1))
    github_api.route("GET", FULL, github_json([_issue(3), _issue(1)]))
    numbers = [i.number for i in _store(tmp_path, **later).issues()]
    assert (_queries(github_api), numbers, [i.number for i in _kept(tmp_path).issues]) == (
        [{"state": "all", "per_page": "100"}],
        [3, 1],
        [3, 1],
    ), changes


def test_a_snapshot_that_cannot_be_read_is_reported_and_read_again_in_full(
    github_api: GitHubApiFake, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = FileSnapshotStore(tmp_path).path(REPO)
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")
    github_api.route("GET", FULL, github_json([_issue(1)]))
    with caplog.at_level(logging.WARNING):
        numbers = [i.number for i in _store(tmp_path).issues()]
    assert (numbers, [i.number for i in _kept(tmp_path).issues], str(path) in caplog.text) == (
        [1],
        [1],
        True,
    )


def test_a_directory_in_place_of_the_snapshot_is_reported_and_the_run_reads_in_full(
    github_api: GitHubApiFake, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The read and the write of the snapshot both fail, and the run still returns the whole
    listing."""
    path = FileSnapshotStore(tmp_path).path(REPO)
    path.mkdir(parents=True)
    github_api.route("GET", FULL, github_json([_issue(1)]))
    with caplog.at_level(logging.WARNING):
        numbers = [i.number for i in _store(tmp_path).issues()]
    reports = [r.getMessage() for r in caplog.records if str(path) in r.getMessage()]
    assert (numbers, [r.split(str(path))[0] for r in reports], path.is_dir()) == (
        [1],
        [
            "Intake reads the whole issue listing, because it cannot read the snapshot ",
            "Intake did not keep the snapshot ",
        ],
        True,
    )


@pytest.mark.skipif(os.geteuid() == 0, reason="root writes into a read-only directory")
def test_a_failed_snapshot_write_keeps_the_old_snapshot_and_is_reported(
    github_api: GitHubApiFake, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _first_run(github_api, tmp_path, _issue(1))
    path = FileSnapshotStore(tmp_path).path(REPO)
    before = path.read_bytes()
    github_api.route(
        "GET",
        _since("2026-01-01T08:59:00Z"),
        github_json([_issue(2, updated="2026-01-01T10:30:00Z")]),
    )
    path.parent.chmod(0o500)
    try:
        with caplog.at_level(logging.WARNING):
            numbers = [i.number for i in _store(tmp_path, at=STARTED + timedelta(hours=1)).issues()]
    finally:
        path.parent.chmod(0o700)
    assert (numbers, path.read_bytes() == before, str(path) in caplog.text) == ([2, 1], True, True)


def test_a_sub_issue_that_joins_or_leaves_a_parent_moves_the_count_of_the_parent(
    github_api: GitHubApiFake, tmp_path: Path
) -> None:
    """GitHub does not move the `updated_at` of a parent when a sub-issue joins it, so the
    changed sub-issue moves the count of its parent: #11 joins #10, and #13 leaves #12."""
    _first_run(
        github_api,
        tmp_path,
        _issue(13, parent_issue_url=f"{REPOSITORY_URL}/issues/12"),
        _issue(12, sub_issues_summary={"total": 1}),
        _issue(11),
        _issue(10, sub_issues_summary={"total": 2}),
    )
    changed = [
        _issue(13, updated="2026-01-01T10:30:00Z"),
        _issue(11, updated="2026-01-01T10:30:00Z", parent_issue_url=f"{REPOSITORY_URL}/issues/10"),
    ]
    github_api.route("GET", _since("2026-01-01T08:59:00Z"), github_json(changed))
    issues = _store(tmp_path, at=STARTED + timedelta(hours=1)).issues()
    assert {i.number: (i.parent, i.sub_issues) for i in issues} == {
        13: (None, 0),
        12: (None, 0),
        11: (10, 0),
        10: (None, 3),
    }


def test_a_repository_name_that_climbs_out_of_the_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(SecurityError, match="Path traversal detected in Repository"):
        FileSnapshotStore(tmp_path).path("../outside")
