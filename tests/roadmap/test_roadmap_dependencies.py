"""The shared dependency reason of the stage and the implement jobs (#4009, #6449)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from devops_cli.lang import MESSAGES
from devops_cli.roadmap.dependencies import open_dependency
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ItemField,
    RefineRecordKey,
    encode_job_record,
    with_record,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

PRIORITY = "P2-Medium"


def _seed(
    store: InMemoryRoadmapStore,
    title: str,
    *,
    body: str = "",
    record: Mapping[str, Any] | None = None,
    state: GitHubState = GitHubState.OPEN,
) -> int:
    """An issue whose body holds `body` and the job record `record`."""
    block = encode_job_record({}, record) if record else None
    return store.seed_issue(
        title,
        body=with_record(body, block),
        fields={ItemField.PRIORITY: PRIORITY},
        state=state,
    )


def _reason(store: InMemoryRoadmapStore, number: int) -> str | None:
    """The reason that `open_dependency` gives for issue `number`, over the open items."""
    item = store.item(number)
    assert item is not None
    return open_dependency(item, store, store.open_items())


def test_the_reason_of_an_item_in_a_cycle_names_the_cycle() -> None:
    """The Dependencies section of A names the open B, and the record of B names A, so the reason
    for A names the path back to A and not only the open issue B (#6449)."""
    store = InMemoryRoadmapStore()
    first = _seed(store, "fix(roadmap): the first")
    second = _seed(
        store, "fix(roadmap): the second", record={RefineRecordKey.BLOCKED_BY: str(first)}
    )
    store.write_issue_body(first, f"### Dependencies\n#{second}\n")

    reason = _reason(store, first)

    assert reason is not None
    assert f"#{first} → #{second} → #{first}" in reason


def test_the_reason_of_an_item_whose_open_dependency_is_in_no_cycle_names_no_cycle() -> None:
    """A depends on the open B, and B depends on no open item, so the reason stays the open-issue
    reason and names no cycle (#6449)."""
    store = InMemoryRoadmapStore()
    blocker = _seed(store, "fix(roadmap): the blocker")
    waiting = _seed(store, "fix(roadmap): the waiting item", body=f"### Dependencies\n#{blocker}\n")

    reason = _reason(store, waiting)

    assert reason == MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{blocker}")
    assert "→" not in reason


def test_the_reason_of_an_item_whose_body_names_no_open_issue_is_none() -> None:
    """The record of A names the open B and the body names no open issue, so the reason is None: an
    item that declares no open dependency gets no reason (#6449)."""
    store = InMemoryRoadmapStore()
    blocker = _seed(store, "fix(roadmap): the blocker")
    recorded = _seed(
        store, "fix(roadmap): the recorded item", record={RefineRecordKey.BLOCKED_BY: str(blocker)}
    )

    assert _reason(store, recorded) is None


def test_a_related_mention_gives_no_reason_and_a_depends_on_line_gives_it() -> None:
    """The Dependencies section of one item says `Related: #N`, and that of another says `Depends
    on #N`, with #N open. The related mention gives no reason, and the blocker line gives the
    reason that names #N (#6451)."""
    store = InMemoryRoadmapStore()
    blocker = _seed(store, "fix(roadmap): the open issue")
    related = _seed(
        store, "fix(roadmap): the related item", body=f"### Dependencies\n\nRelated: #{blocker}\n"
    )
    waiting = _seed(
        store,
        "fix(roadmap): the waiting item",
        body=f"### Dependencies\n\nDepends on #{blocker}\n",
    )

    assert (_reason(store, related), _reason(store, waiting)) == (
        None,
        MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{blocker}"),
    )


def test_the_reason_of_a_held_item_names_the_hold_issue_and_no_link() -> None:
    """The hold line of the freeze names the open hold issue first, its parentheses name the open
    tracker, and a later line names an open related issue. The stage and the implement jobs give a
    reason that names only the hold issue, so the close of that issue lifts the hold (#6451, #6521).
    """
    store = InMemoryRoadmapStore()
    tracker = _seed(store, "refactor(roadmap): the re-architecture")
    hold = _seed(store, "chore(roadmap): hold incremental work")
    related = _seed(store, "fix(roadmap): the related item")
    held = _seed(
        store,
        "fix(roadmap): the held item",
        body=(
            f"### Dependencies\n\n- #{hold} (hold: incremental work on the stage, implement and "
            f"fix-checks jobs waits for the re-architecture of #{tracker})\n\nRelated: #{related}\n"
        ),
    )

    assert _reason(store, held) == MESSAGES.roadmap.stage_left_dependency.format(issues=f"#{hold}")
