"""The snapshot of a repository's issue listing that intake keeps between runs (#4448, #3670).

A full read of `state=all` costs one request for each 100 issues and a parse of each body. A CLI
run is a new process, so the conditional answers of the GitHub session (#1692) are gone at its
start; the Service sends each page again in each intake round, and a 304 answer passes the rate
limiter too. With a snapshot, a run reads only the issues and pull requests that GitHub changed
since the snapshot's watermark, through the `since` parameter of the REST listing, and keeps the
parsed record of every other issue. GitHub stays the source of truth (ADR 0001): the snapshot is a
copy of the listing that any run can drop and read again in full.

A run reads the whole listing when no snapshot is kept, when the snapshot cannot be read, when
its records have another schema than `IssueRecord` (`LISTING_SCHEMA_KEY`), when its last full read
is older than `DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS`, and on `--full`. The full read
removes an issue that left the repository, and a change that moved no `updated_at`. A release that
keeps the schema keeps the snapshot.

`SnapshotStore` is the seam of the place that keeps the snapshots. `FileSnapshotStore` keeps them
in the state directory of the roadmap: under the data directory for `devops roadmap intake`, and on
the Service's volume for the intake of the lane of `intake` and the scoped intake of a delivery.
Each other lane of the Service keeps its own snapshots beside them (`lane_listing`, #4854, #5553),
so each file has one writer. A shared store for the pods of the Service can plug in later (#4517).
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, Protocol

from pydantic import BaseModel, ConfigDict, ValidationError

from devops_cli.config.defaults import (
    DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS,
    DEFAULT_ROADMAP_INTAKE_SNAPSHOT_OVERLAP_SECONDS,
)
from devops_cli.core.paths import validate_no_path_traversal
from devops_cli.lang import MESSAGES
from devops_cli.output.file_writer import write_bytes_file
from devops_cli.roadmap.stores.store import IssueRecord

logger = logging.getLogger(__name__)

# The query of the whole listing: every issue and pull request, open and closed.
FULL_LISTING: Final = "state=all"
# The query of the issues and pull requests changed at or after `since`, the newest change first.
CHANGED_LISTING: Final = f"{FULL_LISTING}&sort=updated&direction=desc&since={{since}}"

# The directory of the snapshots in the state directory of the roadmap.
_SNAPSHOT_DIRNAME: Final = "listing"

# The key of the schema of the records that a snapshot holds: the first 16 hex characters of the
# sha256 of the JSON schema of `IssueRecord`. A snapshot with another key is read again in full.
LISTING_SCHEMA_KEY: Final = hashlib.sha256(
    json.dumps(IssueRecord.model_json_schema(), sort_keys=True).encode()
).hexdigest()[:16]

_MAX_AGE: Final = timedelta(hours=DEFAULT_ROADMAP_INTAKE_SNAPSHOT_MAX_AGE_HOURS)
_OVERLAP: Final = timedelta(seconds=DEFAULT_ROADMAP_INTAKE_SNAPSHOT_OVERLAP_SECONDS)


def changed_listing(since: datetime) -> str:
    """The query of the issues and pull requests that changed at or after `since`, the newest
    change first. GitHub pages the listing by offset. An issue that changes during the read moves
    to the first page, which the read has, so no issue moves out of a page the read has not
    reached; the changed issue is read on the next run."""
    return CHANGED_LISTING.format(since=since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))


class ListingSnapshot(BaseModel):
    """The issue listing of `repo` as a run read it: each issue's parsed record, the key of the
    schema of the records, the time of the last full read, and the watermark that the next run
    reads the changes from."""

    model_config = ConfigDict(frozen=True)

    repo: str
    schema_key: str
    full_at: datetime
    watermark: datetime
    issues: tuple[IssueRecord, ...]


class SnapshotStore(Protocol):
    """The place that keeps one snapshot for each repository."""

    def load(self, repo: str) -> ListingSnapshot | None:
        """The snapshot of `repo`, or None when none is kept or it cannot be read."""
        ...

    def save(self, snapshot: ListingSnapshot) -> None:
        """Keep `snapshot` in place of the earlier one of its repository. A snapshot that cannot
        be kept is reported, and the earlier one stays."""
        ...


@dataclass(frozen=True)
class FileSnapshotStore:
    """One JSON file for each repository, `<root>/<owner>/<name>.json`."""

    root: Path

    def path(self, repo: str) -> Path:
        """The file of `repo`; a name that climbs out of `root` raises `SecurityError`."""
        owner, _, name = (
            validate_no_path_traversal(repo, label="Repository").as_posix().partition("/")
        )
        return self.root / owner / f"{name}.json"

    def load(self, repo: str) -> ListingSnapshot | None:
        path = self.path(repo)
        try:
            text = path.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as exc:
            _report(MESSAGES.roadmap.intake_snapshot_unreadable, path, exc)
            return None
        try:
            return ListingSnapshot.model_validate_json(text)
        except ValidationError as exc:
            _report(MESSAGES.roadmap.intake_snapshot_unreadable, path, exc)
            return None

    def save(self, snapshot: ListingSnapshot) -> None:
        """Write the file through a temporary file and a rename in its directory, so a failed
        write leaves the earlier file whole."""
        path = self.path(snapshot.repo)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            write_bytes_file(path, snapshot.model_dump_json().encode(), atomic=True)
        except OSError as exc:
            _report(MESSAGES.roadmap.intake_snapshot_unsaved, path, exc)


def _report(message: str, path: Path, error: Exception) -> None:
    """Log `message` as a warning, with `path` and the first line of `error`."""
    reason = str(error).splitlines()[0][:200] if str(error) else type(error).__name__
    logger.warning(message.format(path=path, reason=reason))


def snapshot_root(state_dir: Path | None = None) -> Path:
    """Where the snapshots are kept: `listing` in `state_dir`, the state directory of the
    roadmap, which is `roadmap` under the data directory when it is None."""
    if state_dir is None:
        from devops_cli.roadmap.run import service_state_dir

        state_dir = service_state_dir()
    return state_dir / _SNAPSHOT_DIRNAME


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class IncrementalListing:
    """How a store reads every issue of a repository: the snapshot that `snapshots` keeps and the
    issues changed since its watermark, or the whole listing when `full` or when no snapshot is
    fit to read from. Each read keeps a new snapshot."""

    snapshots: SnapshotStore
    full: bool = False
    clock: Callable[[], datetime] = _now
    schema_key: str = LISTING_SCHEMA_KEY

    def read(
        self, repo: str, read_issues: Callable[[str], list[IssueRecord]]
    ) -> dict[int, IssueRecord]:
        """Every issue and pull request of `repo` by number, the newest first. `read_issues`
        reads the listing of a query and parses each issue it gets."""
        started = self.clock()
        held = None if self.full else self._fit(self.snapshots.load(repo), started)
        if held is None:
            listed = {issue.number: issue for issue in read_issues(FULL_LISTING)}
            full_at = started
        else:
            listed = merged(held.issues, read_issues(changed_listing(held.watermark)))
            full_at = held.full_at
        self._keep(repo, listed, full_at=full_at, started=started)
        return listed

    def _fit(self, held: ListingSnapshot | None, now: datetime) -> ListingSnapshot | None:
        """`held` when a run can read the changes from it: its records have this schema, and its
        last full read is younger than the max age."""
        if held is None or held.schema_key != self.schema_key or now - held.full_at >= _MAX_AGE:
            return None
        return held

    def _keep(
        self, repo: str, listed: dict[int, IssueRecord], *, full_at: datetime, started: datetime
    ) -> None:
        """Keep the listing as the new snapshot. Its watermark is the earlier of the start of the
        read and GitHub's newest change, less the overlap, so a local clock ahead of GitHub's
        skips no change."""
        changes = [issue.updated_at for issue in listed.values() if issue.updated_at is not None]
        newest = min(started, max(changes)) if changes else started
        self.snapshots.save(
            ListingSnapshot(
                repo=repo,
                schema_key=self.schema_key,
                full_at=full_at,
                watermark=newest - _OVERLAP,
                issues=tuple(listed.values()),
            )
        )


def intake_listing(state_dir: Path | None = None, *, full: bool = False) -> IncrementalListing:
    """How intake reads every issue: the snapshot that `state_dir` keeps, see `snapshot_root`, and
    the issues changed since its watermark, or the whole listing on `full`. `devops roadmap
    intake`, the lane of `intake` in the Service and the scoped intake of a delivery read through
    it (#4448, #3670)."""
    return IncrementalListing(FileSnapshotStore(snapshot_root(state_dir)), full=full)


def lane_listing(state_dir: Path, lane: str) -> IncrementalListing:
    """How the rounds of the Service lane `lane` read every issue: the snapshot that `state_dir`
    keeps for the lane in `listing-<lane>`, apart from the one of intake, and the issues changed
    since its watermark. The lane's worker is the one writer of each file of the lane (#4854)."""
    return IncrementalListing(FileSnapshotStore(state_dir / f"{_SNAPSHOT_DIRNAME}-{lane}"))


def lane_snapshot_dirs(state_dir: Path) -> dict[str, Path]:
    """The snapshot directory `listing-<lane>` of each lane that `state_dir` holds, by the name of
    the lane (#5553). The snapshot of intake, `listing`, is not one of them."""
    prefix = f"{_SNAPSHOT_DIRNAME}-"
    if not state_dir.is_dir():
        return {}
    return {
        path.name.removeprefix(prefix): path
        for path in state_dir.iterdir()
        if path.is_dir() and path.name.startswith(prefix)
    }


def merged(held: Sequence[IssueRecord], changed: Sequence[IssueRecord]) -> dict[int, IssueRecord]:
    """The issues of `held` with each issue of `changed` in place of its record, the highest
    number first, as the full listing gives them.

    GitHub does not move the `updated_at` of a parent when a sub-issue joins or leaves it. So a
    changed issue whose parent changed moves the sub-issue count of each parent that `changed`
    does not hold: one up for the parent it joined, one down for the parent it left."""
    listed = {issue.number: issue for issue in held}
    fresh = {issue.number: issue for issue in changed}
    moves = [
        (left, issue.parent)
        for number, issue in fresh.items()
        if (left := listed[number].parent if number in listed else None) != issue.parent
    ]
    listed |= fresh
    for left, joined in moves:
        for parent, step in ((left, -1), (joined, 1)):
            if parent is not None and parent in listed and parent not in fresh:
                kept = listed[parent]
                listed[parent] = kept.model_copy(
                    update={"sub_issues": max(kept.sub_issues + step, 0)}
                )
    return dict(sorted(listed.items(), reverse=True))


__all__ = [
    "CHANGED_LISTING",
    "FULL_LISTING",
    "LISTING_SCHEMA_KEY",
    "FileSnapshotStore",
    "IncrementalListing",
    "ListingSnapshot",
    "SnapshotStore",
    "changed_listing",
    "intake_listing",
    "lane_listing",
    "lane_snapshot_dirs",
    "merged",
    "snapshot_root",
]
