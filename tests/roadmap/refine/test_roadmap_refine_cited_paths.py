"""The paths that an item cites: refine records them, and a change of one on main gives a waiting
item a new look (#1335), one for each change (#4793).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest
import time_machine

from devops_cli.roadmap.refine.refine import (
    RefinementProposal,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CITED_PATH,
    QUESTION,
    READY,
    REPO,
    block_in_code,
    refine_comment_at,
    refine_round,
    require_item,
    seed_item,
    seed_item_blocked_in_code,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.parametrize("blocked", [True, False], ids=["blocked", "suspected-block"])
def test_a_waiting_item_whose_cited_path_changes_on_main_after_refines_comment_is_refined_again(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, blocked: bool
) -> None:
    """Refine records the path that its proposal cites as the cause of the block. A commit on
    the default branch that changes that path after refine's last comment ends the wait: the
    next round refines the item again, with no reply and no body edit (#2005)."""
    number = seed_item_blocked_in_code(store, model_fake, blocked=blocked)
    refine_round(store, git_repo)
    calls = model_fake.call_count

    store.seed_commit(CITED_PATH, at=refine_comment_at(store, number) + timedelta(minutes=5))
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        require_item(store, number).job_record.get(RefineRecordKey.BLOCK_PATHS),
        [r.item.number for r in again.refined_items],
        again.waiting_items,
        model_fake.call_count - calls,
    ) == (CITED_PATH, [number], [], 1)


@pytest.mark.parametrize("blocked", [True, False], ids=["blocked", "suspected-block"])
def test_each_change_of_a_cited_path_gives_one_new_look_when_the_look_finds_the_same_wait(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, blocked: bool
) -> None:
    """A commit changes the cited path after refine's comment, and the new look finds the same
    wait, so the store refuses the repeat of the comment. The round of that look starts the wait
    again: the rounds after it make no model call until the next change (#4793)."""
    looks: list[int] = []
    with time_machine.travel(datetime(2026, 11, 12, 9, tzinfo=UTC), tick=False) as clock:
        number = seed_item_blocked_in_code(store, model_fake, blocked=blocked)
        refine_round(store, git_repo)
        for _change in range(2):
            calls = model_fake.call_count
            clock.shift(timedelta(minutes=10))
            store.seed_commit(CITED_PATH, at=datetime.now(UTC))
            for _round in range(3):
                clock.shift(timedelta(minutes=17))
                refine_round(store, git_repo)
            looks.append(model_fake.call_count - calls)

    assert (looks, len(store.comments_on(number))) == ([1, 1], 1)


def test_a_waiting_item_whose_cited_path_does_not_change_keeps_waiting_with_no_model_call(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """A commit that changed the cited path before refine's last comment, and a later commit
    that changed another path, leave the item waiting on its blocker, and the round makes no
    model call (#2005)."""
    number = seed_item_blocked_in_code(store, model_fake)
    refine_round(store, git_repo)
    calls = model_fake.call_count

    commented = refine_comment_at(store, number)
    store.seed_commit(CITED_PATH, at=commented - timedelta(days=1))
    store.seed_commit("CONTEXT.md", at=commented + timedelta(minutes=5))
    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step) for w in again.waiting_items],
        again.refined_items,
        model_fake.call_count - calls,
    ) == ([(number, "blocked")], [], 0)


def test_refine_records_each_cited_path_the_checkout_holds_once_and_names_them_in_its_comment(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Refine keeps a cited path once and without its line, only when the checkout holds it at
    the refined commit, and never a path outside the repository. Its comment names the files
    whose change ends the wait (#2005)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    cited = ["src/sample.py:1", "src/missing.py", "../CONTEXT.md", "/etc/hosts"]
    cited += ["src/sample.py", "CONTEXT.md"]
    model_fake.answer(block_in_code(None).model_copy(update={"block_paths": cited}))

    refine_round(store, git_repo)

    (comment,) = store.comments_on(number)
    assert (
        require_item(store, number).job_record.get(RefineRecordKey.BLOCK_PATHS),
        comment.body.splitlines()[-1],
    ) == (
        "src/sample.py,CONTEXT.md",
        "The next refine round also looks at the item again when a commit on the default "
        "branch changes one of these files: `src/sample.py`, `CONTEXT.md`.",
    )


@pytest.mark.parametrize("proposal", [READY, QUESTION], ids=["ready", "question"])
def test_a_proposal_that_names_no_block_records_no_cited_path(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    model_fake: ModelFake,
    proposal: RefinementProposal,
) -> None:
    """A path is recorded only as the cause of a block: a proposal with no suspected block and
    no open dependency records none, and its comment names none (#2005)."""
    store.seed_visibility(is_private=True)
    number = seed_item(store, "New", "P1-High")
    model_fake.answer(proposal.model_copy(update={"block_paths": [CITED_PATH]}))

    refine_round(store, git_repo)

    assert (
        require_item(store, number).job_record.get(RefineRecordKey.BLOCK_PATHS),
        [CITED_PATH in comment.body for comment in store.comments_on(number)],
    ) == (None, [False])
