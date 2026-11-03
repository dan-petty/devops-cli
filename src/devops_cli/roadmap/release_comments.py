"""The row `release_comments`: a release comments its version, and the time it runs, on the
closed issues it carries (#2917).

The first pass posts `Released in <tag>` on each closed issue of each release of the window. The
second pass posts `Live since <time>` once the Service and runner image digests of the release run
in the cluster: the newest release of the list whose two digests run, and each older one, are
live. The marker line of a comment is the record that it exists. The ledger only saves requests:
it holds two flags for each release of the window, set after every issue holds its comment, and a
missing ledger reads as empty. A failed read of the cluster or the registry stops no comment of
the `Released in` pass, and fails the row after both passes, naming the releases.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from pathlib import Path

import httpx2
from pydantic import BaseModel, Field
from pydantic import ValidationError as MalformedRecordError

from devops_cli.config.constants import (
    CONST_ROADMAP_RELEASE_COMMENTS_LIST,
    CONST_ROADMAP_RELEASE_COMMENTS_WINDOW_HOURS,
    CONST_ROADMAP_RELEASE_MARKER,
)
from devops_cli.exceptions import RoadmapRunError
from devops_cli.exceptions.docker import RegistryReadError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.release_feed import GitHubReleaseFeed, ReleaseInfo
from devops_cli.roadmap.release_roll import RolledDigests, live_release
from devops_cli.roadmap.store import RoadmapStore

logger = logging.getLogger(__name__)

_RELEASED = "released"
_LIVE = "live"


class ReleaseFlags(BaseModel):
    """The two passes that are done for one release."""

    released: bool = False
    live: bool = False


class ReleaseLedger(BaseModel):
    """The flags of each release of the window, by tag (`release_comments.json`)."""

    releases: dict[str, ReleaseFlags] = Field(default_factory=dict[str, ReleaseFlags])

    @classmethod
    def read(cls, path: Path) -> ReleaseLedger:
        """The ledger at `path`, empty when there is none. One that exists and cannot be read
        raises RoadmapRunError that names the file, as a silent empty read would hide a bad
        write."""
        if not path.exists():
            return cls()
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, MalformedRecordError) as exc:
            reason = str(exc).splitlines()[0][:200]
            raise RoadmapRunError(
                MESSAGES.roadmap.release_ledger_unreadable.format(path=path, reason=reason),
                details={"path": str(path)[:256]},
            ) from exc

    def write(self, path: Path) -> None:
        """Write the ledger to `path` atomically."""
        from devops_cli.output.file_writer import write_json_file

        write_json_file(path, self.model_dump(mode="json"), indent=2, atomic=True)


def marker(tag: str, kind: str) -> str:
    """The first line of the comment of pass `kind` for release `tag`."""
    return CONST_ROADMAP_RELEASE_MARKER.format(tag=tag, kind=kind)


def released_body(release: ReleaseInfo) -> str:
    return (
        f"{marker(release.tag, _RELEASED)}\n"
        f"{MESSAGES.roadmap.release_comment_released.format(tag=release.tag, url=release.url)}"
    )


def live_body(release: ReleaseInfo, now: datetime) -> str:
    time = now.strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"{marker(release.tag, _LIVE)}\n{MESSAGES.roadmap.release_comment_live.format(time=time)}"
    )


def _windowed(releases: Sequence[ReleaseInfo], now: datetime) -> tuple[ReleaseInfo, ...]:
    """The releases published within the window of `now` that are neither a draft nor a
    prerelease, newest first."""
    oldest = now - timedelta(hours=CONST_ROADMAP_RELEASE_COMMENTS_WINDOW_HOURS)
    return tuple(
        release
        for release in releases
        if not release.draft and not release.prerelease and release.published_at >= oldest
    )


def _comment_once(store: RoadmapStore, number: int, first_line: str, body: str) -> None:
    """Post `body` on issue `number` unless one of its comments starts with `first_line`."""
    if not any(c.body.startswith(first_line) for c in store.comments_on(number)):
        store.comment(number, body)


def comment_releases(
    store: RoadmapStore,
    feed: GitHubReleaseFeed,
    *,
    ledger_path: Path,
    now: datetime,
    roll: Callable[[], RolledDigests] | None = None,
    client: httpx2.Client | None = None,
) -> None:
    """Run both passes over the releases of the window, as the module says. `roll` reads the
    digests that the cluster runs, and `client` reads the registry; with either missing, the
    `Live since` pass does not run. Raises RoadmapRunError after both passes when the cluster or
    the registry could not be read, naming the releases it could not check."""
    ledger = ReleaseLedger.read(ledger_path)
    window = _windowed(feed.releases(CONST_ROADMAP_RELEASE_COMMENTS_LIST), now)
    ledger.releases = {
        release.tag: ledger.releases.get(release.tag, ReleaseFlags()) for release in window
    }
    issues: dict[str, tuple[int, ...]] = {}

    def closed(release: ReleaseInfo) -> tuple[int, ...]:
        if release.tag not in issues:
            issues[release.tag] = feed.closed_issues(release)
        return issues[release.tag]

    unchecked: list[str] = []
    try:
        for release in window:
            flags = ledger.releases[release.tag]
            if flags.released:
                continue
            for number in closed(release):
                _comment_once(store, number, marker(release.tag, _RELEASED), released_body(release))
            flags.released = True
        if roll is not None and client is not None:
            unchecked = _live_pass(store, window, ledger, closed, roll, client, now)
    finally:
        ledger.write(ledger_path)
    if unchecked:
        raise RoadmapRunError(
            MESSAGES.roadmap.release_roll_failed.format(
                count=len(unchecked), releases=", ".join(unchecked)
            ),
            details={"releases": [tag[:64] for tag in unchecked][:32]},
        )


def _live_pass(
    store: RoadmapStore,
    window: Sequence[ReleaseInfo],
    ledger: ReleaseLedger,
    closed: Callable[[ReleaseInfo], tuple[int, ...]],
    roll: Callable[[], RolledDigests],
    client: httpx2.Client,
    now: datetime,
) -> list[str]:
    """Post `Live since` on each issue of the newest release whose digests run and of each older
    release that the ledger does not hold as done. Returns the tags that it could not check."""
    waiting = [release for release in window if not ledger.releases[release.tag].live]
    if not waiting:
        return []
    try:
        live = live_release(waiting, roll(), client)
    except (ClusterJobError, RegistryReadError) as exc:
        logger.warning("The release_comments row could not check the images: %s", exc)
        return [release.tag for release in waiting]
    if live is None:
        return []
    for release in waiting[waiting.index(live) :]:
        for number in closed(release):
            _comment_once(store, number, marker(release.tag, _LIVE), live_body(release, now))
        ledger.releases[release.tag].live = True
    return []


__all__ = ["ReleaseLedger", "comment_releases", "live_body", "marker", "released_body"]
