"""The recorded wait of an item: a round reads no comment of an item that nothing changed, and what
ends the record (#1335).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER,
)
from devops_cli.roadmap.refine.refine import (
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    IssueComment,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CITED_PATH,
    READY,
    REPO,
    refine_comment_at,
    refine_round,
    require_item,
    seed_item,
    seed_item_blocked_in_code,
    seed_person_wait,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


# ── An item nothing changed costs no comment read (#3667) ─────────────────────────────────


@pytest.fixture
def comment_reads(store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """The number of each issue whose comments the store is asked to list."""
    reads: list[int] = []
    original = store.comments_on

    def counted(number: int) -> list[IssueComment]:
        reads.append(number)
        return original(number)

    monkeypatch.setattr(store, "comments_on", counted)
    return reads


def _recorded_wait(
    store: InMemoryRoadmapStore, source: Path, model_fake: ModelFake, *, blocked: bool = True
) -> int:
    """An item whose block cites `src/sample.py`, after the round that refined it and the round
    that read its comments once and recorded what they gave."""
    number = seed_item_blocked_in_code(store, model_fake, blocked=blocked)
    refine_round(store, source)
    refine_round(store, source)
    return number


@pytest.mark.parametrize("blocked", [True, False], ids=["blocked", "suspected-block"])
def test_a_round_reads_no_comment_of_a_waiting_item_that_nothing_changed(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    comment_reads: list[int],
    blocked: bool,
) -> None:
    number = _recorded_wait(store, git_repo, model_fake, blocked=blocked)
    comment_reads.clear()
    calls = model_fake.call_count

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step.value) for w in again.waiting_items],
        again.refined_items,
        comment_reads,
        model_fake.call_count - calls,
    ) == ([(number, "blocked" if blocked else "person")], [], [], 0)


def test_the_round_that_reads_the_comments_of_a_waiting_item_records_what_they_gave(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """The count of comments the listing carried, the time of refine's last comment, and the
    issues and paths that the text of the wait names."""
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    number = seed_person_wait(store, f"Does #{named} cover `{CITED_PATH}:2`?")

    refine_round(store, git_repo)

    record = require_item(store, number).job_record
    assert (
        record.get(RefineRecordKey.COMMENTS_SEEN),
        record.get(RefineRecordKey.COMMENTED_AT),
        record.get(RefineRecordKey.WAIT_REFS),
    ) == ("1", refine_comment_at(store, number).isoformat(), f"#{named},{CITED_PATH}")


def test_a_closed_blocker_ends_a_recorded_wait_while_the_updated_at_of_the_item_stays(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    number = _recorded_wait(store, git_repo, model_fake)
    blocker = int(require_item(store, number).job_record[RefineRecordKey.BLOCKED_BY])
    updated = require_item(store, number).updated_at
    store.as_actor("alice").close_by_hand(blocker, CloseReason.COMPLETED)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        require_item(store, number).updated_at,
        [r.item.number for r in again.refined_items],
        again.waiting_items,
    ) == (updated, [number], [])


def test_a_changed_cited_path_ends_a_recorded_wait_while_the_updated_at_of_the_item_stays(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    number = _recorded_wait(store, git_repo, model_fake)
    updated = require_item(store, number).updated_at
    store.seed_commit(CITED_PATH, at=refine_comment_at(store, number) + timedelta(minutes=5))

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        require_item(store, number).updated_at,
        [r.item.number for r in again.refined_items],
        again.waiting_items,
    ) == (updated, [number], [])


def test_a_closed_issue_the_wait_text_names_ends_a_recorded_wait_of_a_person(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    number = seed_person_wait(store, f"Does the work of #{named} cover this item?")
    model_fake.answer(READY)
    refine_round(store, git_repo)
    store.as_actor("alice").close_by_hand(named, CloseReason.COMPLETED)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert ([r.item.number for r in again.refined_items], again.waiting_items) == ([number], [])


def test_a_reply_ends_a_recorded_wait_because_the_count_of_comments_moved(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, comment_reads: list[int]
) -> None:
    number = _recorded_wait(store, git_repo, model_fake, blocked=False)
    store.as_actor("alice").comment(number, "The block is gone.")
    model_fake.answer(READY)
    comment_reads.clear()

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [r.item.number for r in again.refined_items],
        again.waiting_items,
        comment_reads.count(number) >= 1,
    ) == ([number], [], True)


def test_a_comment_of_another_job_costs_one_read_and_then_the_wait_is_recorded_again(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    comment_reads: list[int],
) -> None:
    """A comment that is no reply moves the count: the next round reads the comments once,
    finds the item still waiting, and records the new count, so the round after reads none."""
    number = _recorded_wait(store, git_repo, model_fake)
    store.seed_comment(number, f"{CONST_ROADMAP_ALTERNATIVES_COMMENT_MARKER}\nNo tool covers it.")
    comment_reads.clear()

    refine_round(store, git_repo)
    read_once = list(comment_reads)
    comment_reads.clear()
    refine_round(store, git_repo)

    assert (read_once, comment_reads) == ([number], [])
