"""`devops roadmap retitle` records a skip mark for an item it leaves (#4038). The mark holds a
hash of what the decision read: the title, the body and the `stage.pr` mark. The selection leaves
out an item whose recorded hash is the current one, so a round does not read the comments of the
item again, does not call the model for it, and does not let it hold a place of the limit."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from devops_cli.roadmap.retitle import RetitleReply, apply_retitle, long_title_items, plan_retitle
from devops_cli.roadmap.stores.store import ItemField, StageRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore, JobWrite

REPO = "example/roadmap"
LONG = "Shorten the title of an item that a job leaves out because it is too long"
OLD = f"fix(roadmap): {LONG}"
OTHER_LONG = "Shorten the title of an item that a person edited after the job left it"
NEW_SUMMARY = "Shorten the long title of an item"
# The key of `RetitleRecordKey.SKIPPED`. The tests name it as text, so that they fail in the call
# phase, and not at the import, while the key family does not exist.
SKIPPED = "retitle.skipped"
JOB_COMMENT = "<!-- devops roadmap intake: reason -->\nPlaced."


class Clock:
    """A clock that a test moves, so that the order of events is exact."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        self.now += timedelta(minutes=1)
        return self.now


class FakeModel:
    """Records each request and answers from a list of summaries, the last one repeated. A
    summary over the limit fails the title form, so the item is left."""

    def __init__(self, *summaries: str) -> None:
        self.requests: list[str] = []
        self._summaries = list(summaries) or [LONG]

    def summarize(self, request: str) -> RetitleReply:
        self.requests.append(request)
        index = min(len(self.requests), len(self._summaries)) - 1
        return RetitleReply(summary=self._summaries[index])


class CountingStore(InMemoryRoadmapStore):
    """The reads that the decision of one item costs: its comments, its title changes and the
    title of its plan pull request. `open_items` is the one read that every round makes."""

    def __init__(self) -> None:
        super().__init__(repo=REPO, clock=Clock())
        self.decision_reads: list[str] = []

    def comments_on(self, number: int) -> Any:
        self.decision_reads.append("comments_on")
        return super().comments_on(number)

    def last_renamed_at(self, number: int) -> Any:
        self.decision_reads.append("last_renamed_at")
        return super().last_renamed_at(number)

    def pull_title(self, number: int) -> Any:
        self.decision_reads.append("pull_title")
        return super().pull_title(number)


@pytest.fixture
def store() -> CountingStore:
    return CountingStore()


def _item(store: InMemoryRoadmapStore, title: str = OLD, status: str = "Ready") -> int:
    return store.seed_issue(
        title,
        body="It asks for one change.",
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: status},
    )


def _planned_without_title(store: InMemoryRoadmapStore) -> int:
    number = _item(store, status="Planned")
    pull = store.seed_pull("docs(openspec): not a plan title", head_ref=f"docs/{number}-plan")
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull)})
    return number


def _person_edited(store: InMemoryRoadmapStore) -> int:
    number = _item(store)
    store.comment(number, JOB_COMMENT)
    store.rename_by_hand(number, f"fix(roadmap): {OTHER_LONG}")
    return number


def _round(store: InMemoryRoadmapStore, model: FakeModel, *, limit: int | None = None) -> Any:
    """One round of the job: the plan, then the writes."""
    plan = plan_retitle(store, repo=REPO, model=model, limit=limit)
    apply_retitle(store, plan)
    return plan


def _skip_marks(store: InMemoryRoadmapStore) -> list[JobWrite]:
    return [w for w in store.job_writes() if w.key == SKIPPED]


def _numbers(store: InMemoryRoadmapStore) -> list[int]:
    return [item.number for item in long_title_items(store)]


# The three reasons for a skip each leave one mark, and the next round does not take the item.


@pytest.mark.parametrize("reason", ["model_failed", "person_edit", "no_plan_title"])
def test_skip_mark_leaves_an_item_that_fails_to_shorten_out_of_the_next_round(
    store: CountingStore, reason: str
) -> None:
    number = {
        "model_failed": lambda: _item(store),
        "person_edit": lambda: _person_edited(store),
        "no_plan_title": lambda: _planned_without_title(store),
    }[reason]()
    model = FakeModel()

    first = _round(store, model)
    second = _round(store, model)

    assert [skip.item.number for skip in first.skips] == [number]
    assert [w.number for w in _skip_marks(store)] == [number]
    assert _numbers(store) == []
    assert (second.changes, second.skips) == ((), ())


def test_skip_mark_holds_a_hash_of_the_inputs_and_not_a_link_to_a_failure_class(
    store: CountingStore,
) -> None:
    _item(store)

    _round(store, FakeModel())

    (mark,) = _skip_marks(store)
    assert mark.value is not None
    assert len(mark.value) == 64
    assert int(mark.value, 16) >= 0
    assert OLD not in mark.value


def test_skip_mark_is_written_for_a_skip_only_and_never_for_a_new_title(
    store: CountingStore,
) -> None:
    _item(store)

    _round(store, FakeModel(NEW_SUMMARY))

    assert _skip_marks(store) == []


def test_skip_mark_does_not_change_the_hash_that_it_holds(store: CountingStore) -> None:
    """The mark rides in the record block of the body, which the body of an item leaves out, so
    the write does not return the item to the selection."""
    number = _item(store)
    _round(store, FakeModel())

    item = store.item(number)
    assert item is not None
    assert {str(k): v for k, v in item.job_record.items()}.get(SKIPPED)
    assert "retitle.skipped" not in item.body
    assert _numbers(store) == []


def test_skip_mark_frees_the_place_of_the_limit_for_the_next_item(store: CountingStore) -> None:
    first = _item(store)
    second = _item(store, f"fix(roadmap): {OTHER_LONG}")
    model = FakeModel(LONG, LONG, NEW_SUMMARY)

    one = _round(store, model, limit=1)
    two = _round(store, model, limit=1)

    assert [skip.item.number for skip in one.skips] == [first]
    assert [change.item.number for change in two.changes] == [second]


# A change to what the decision read returns the item to the selection.


def _change_title(store: InMemoryRoadmapStore, number: int) -> None:
    store.rename_by_hand(number, f"fix(roadmap): {OTHER_LONG}")


def _change_body(store: InMemoryRoadmapStore, number: int) -> None:
    store.write_issue_body(number, "It asks for one change, and now it says why.")


def _change_plan_pull(store: InMemoryRoadmapStore, number: int) -> None:
    pull = store.seed_pull("docs(openspec): plan #1 Add a title repair", head_ref="docs/plan")
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {StageRecordKey.PR: str(pull)})


@pytest.mark.parametrize(
    "change", [_change_title, _change_body, _change_plan_pull], ids=["title", "body", "stage_pr"]
)
def test_returns_when_changed_the_title_the_body_or_the_plan_pull(
    store: CountingStore, change: Any
) -> None:
    number = _item(store)
    _round(store, FakeModel())
    assert _numbers(store) == []

    change(store, number)

    assert _numbers(store) == [number]


def test_returns_when_changed_and_the_new_round_decides_the_item_again(
    store: CountingStore,
) -> None:
    number = _item(store)
    _round(store, FakeModel())
    _change_body(store, number)
    model = FakeModel(NEW_SUMMARY)

    plan = _round(store, model)

    assert [c.item.number for c in plan.changes] == [number]
    assert len(model.requests) == 1


def test_returns_when_changed_a_mark_that_is_not_the_current_hash_selects_the_item(
    store: CountingStore,
) -> None:
    from devops_cli.roadmap.stores.store import RetitleRecordKey

    number = _item(store)
    item = store.item(number)
    assert item is not None
    store.set_marks(item, {RetitleRecordKey.SKIPPED: "0" * 64})

    assert _numbers(store) == [number]


def test_returns_when_changed_a_comment_leaves_the_item_out(store: CountingStore) -> None:
    number = _item(store)
    _round(store, FakeModel())

    store.comment(number, "A person asks about the title.")

    assert _numbers(store) == []


# The cost: one write once, and no read and no model call after it.


def test_request_count_a_skipped_item_costs_one_write_once(store: CountingStore) -> None:
    _item(store)
    model = FakeModel()

    _round(store, model)
    writes_after_first = len(_skip_marks(store))
    _round(store, model)
    _round(store, model)

    assert (writes_after_first, len(_skip_marks(store))) == (1, 1)


def test_request_count_a_skipped_item_costs_no_read_and_no_model_call_in_the_next_round(
    store: CountingStore,
) -> None:
    _item(store)
    model = FakeModel()
    _round(store, model)
    reads, requests = list(store.decision_reads), len(model.requests)
    assert (reads, requests) == (["comments_on", "last_renamed_at"], 2)

    _round(store, model)

    assert store.decision_reads == reads
    assert len(model.requests) == requests


def test_request_count_a_skip_with_a_comment_adds_the_mark_to_the_one_comment(
    store: CountingStore,
) -> None:
    number = _planned_without_title(store)
    model = FakeModel()

    _round(store, model)
    _round(store, model)

    assert [w.number for w in _skip_marks(store)] == [number]
    assert len(store.comments_on(number)) == 1
    assert model.requests == []


def test_request_count_the_dry_run_plan_lists_the_write_of_the_mark() -> None:
    from devops_cli.roadmap.request_plan import retitle_requests

    _, writes = retitle_requests(REPO)

    bodies = [w for w in writes if w.stdin and '"body"' in w.stdin]
    assert len(bodies) == 1
    assert bodies[0].condition
