"""The row `pr_conflicts`: the Service comments on a ready delivery pull request that has merge
conflicts with the default branch (#4027).

GitHub sends no event when a merge into the default branch makes a conflict with an open pull
request, so the row polls. A round reads the open pull requests from the store and reads each one
that is not a draft through the GitHub session, which gives `mergeable` and `mergeable_state`. It
posts its comments through the session too, since the store comments only on issues. A
delivery pull request is one into the default branch whose body closes exactly one issue, and that
issue is an open Item. The round judges each delivery pull request with `merge_conflict`, the
judgment of `devops pr check-readiness`:

- A conflict gets one comment that names the default branch, unless the ledger records the same
  head commit. A new head commit with a conflict gets a new comment.
- A pull request with no conflict leaves the ledger, so a conflict that returns gets the comment
  again. A clean pull request that is only behind the default branch gets no action: an open pull
  request gets no catch-up update (docs/SDLC.md, Phase 1).
- A state that GitHub has not computed changes nothing. The next round reads it again.

The ledger `pr_conflicts.json` lies beside `schedule.json`. A missing ledger reads as empty, and
a lost ledger costs one more comment for each conflict. A ledger that cannot be read fails the row.
A failed read of GitHub fails the row and no other row. The round sends the gauge of the
conflicted delivery pull requests at its end.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic import ValidationError as MalformedRecordError

from devops_cli.exceptions import RoadmapRunError
from devops_cli.github.client import PullStatus
from devops_cli.github.merge_readiness import merge_conflict
from devops_cli.github.session import get_github_session
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.release_feed import closing_numbers
from devops_cli.roadmap.stores.store import GitHubState, RoadmapStore
from devops_cli.telemetry.instruments import ROADMAP_CONFLICTED_PULLS, emit

logger = logging.getLogger(__name__)

_HEAD_CHARS = 12
"""The characters of the head commit that the comment shows."""


class ConflictLedger(BaseModel):
    """The head commit at which the row last found each pull request conflicted, by number
    (`pr_conflicts.json`)."""

    conflicted: dict[int, str] = Field(default_factory=dict[int, str])

    @classmethod
    def read(cls, path: Path) -> ConflictLedger:
        """The ledger at `path`, empty when there is none. One that exists and cannot be read
        raises RoadmapRunError that names the file."""
        if not path.exists():
            return cls()
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, MalformedRecordError) as exc:
            reason = str(exc).splitlines()[0][:200]
            raise RoadmapRunError(
                MESSAGES.roadmap.pr_conflicts_ledger_unreadable.format(path=path, reason=reason),
                details={"path": str(path)[:256]},
            ) from exc

    def write(self, path: Path) -> None:
        """Write the ledger to `path` atomically."""
        from devops_cli.output.file_writer import write_json_file

        write_json_file(path, self.model_dump(mode="json"), indent=2, atomic=True)


@dataclass(frozen=True)
class ConflictRound:
    """What a round found: the delivery pull requests with a conflict, and the ones of them that
    it commented on."""

    conflicted: tuple[int, ...] = ()
    commented: tuple[int, ...] = ()


def _delivers_an_item(store: RoadmapStore, pull: PullStatus) -> bool:
    """Whether `pull` is an open pull request that is not a draft, merges into the default branch
    and closes exactly one issue that is an open Item."""
    if pull.state != "open" or pull.draft or not pull.base_ref:
        return False
    if pull.base_ref != pull.default_branch:
        return False
    closed = closing_numbers(pull.body)
    if len(closed) != 1:
        return False
    item = store.item(closed[0])
    return item is not None and item.state is GitHubState.OPEN


def watch_conflicts(store: RoadmapStore, *, repo: str, ledger_path: Path) -> ConflictRound:
    """Comment once on each ready delivery pull request of `repo` that has merge conflicts, and
    send the gauge of those pull requests. The ledger at `ledger_path` is written also when a read
    fails, so a comment that the round posted is not posted again."""
    ledger = ConflictLedger.read(ledger_path)
    recorded = dict(ledger.conflicted)
    judged: set[int] = set()
    conflicted: list[int] = []
    commented: list[int] = []
    client = get_github_session().client
    try:
        for listed in store.open_pulls():
            if listed.draft:
                continue
            pull = client.get_pull_status(repo, listed.number)
            if not _delivers_an_item(store, pull):
                continue
            judged.add(listed.number)
            conflict = merge_conflict(pull.mergeable, pull.mergeable_state)
            if conflict is None:
                continue
            if not conflict:
                recorded.pop(listed.number, None)
                continue
            conflicted.append(listed.number)
            if recorded.get(listed.number) != pull.head_sha:
                note = MESSAGES.roadmap.pr_conflicts_comment.format(
                    number=listed.number, base=pull.base_ref, head=pull.head_sha[:_HEAD_CHARS]
                )
                client.comment_on_pull(repo, listed.number, note)
                commented.append(listed.number)
            recorded[listed.number] = pull.head_sha
        recorded = {number: head for number, head in recorded.items() if number in judged}
    finally:
        ConflictLedger(conflicted=recorded).write(ledger_path)
    emit(ROADMAP_CONFLICTED_PULLS, len(conflicted), {"repo": repo})
    if conflicted:
        logger.info(
            "The pr_conflicts row of %s found %d conflicted pull request(s) and commented on %d",
            repo,
            len(conflicted),
            len(commented),
        )
    return ConflictRound(conflicted=tuple(conflicted), commented=tuple(commented))
