"""A roadmap job posts no comment that repeats its own recent comment (#4793).

The store refuses a comment of a job when the same text, with its commits, digests and run IDs
left out, is in the trailing run of that job's comments on the item and is less than seven days
old. A person's reply or another job's comment ends the run, so the job's answer to it posts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER,
    CONST_ROADMAP_JOB_COMMENT_MARKERS,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.roadmap.stores.comment_repeat import COMMENT_JOBS
from devops_cli.roadmap.stores.store import CloseReason, GitHubState
from devops_cli.telemetry.instruments import ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL
from tests.support.fakes.otlp import FakeCollector
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

_WAITS = "Refine cannot set this item to Ready at {sha} while #3566 stays open."
_STOPPED = "Stopped at docs."
_CLEARED = (
    "Cleared the stop at docs by the rule `digest`: the runner image changed, from "
    "sha256:59fd1dd8fc8586f5c4fc86d4fe6818fa0a6706468788fcfc6508544092eb788e to sha256:{digest}."
)


def _refine(text: str) -> str:
    return f"{CONST_ROADMAP_REFINE_COMMENT_MARKER}\n{text}"


def _implement(text: str) -> str:
    return f"{CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER}\n{text}"


class _Clock:
    """A clock that stands still until a test moves it."""

    def __init__(self) -> None:
        self.now = datetime(2026, 11, 4, 8, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def store(clock: _Clock) -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(clock=clock)


def _bodies(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [comment.body for comment in store.comments_on(number)]


def test_a_job_comment_posts_once_and_the_same_text_at_a_new_commit_is_refused(
    store: InMemoryRoadmapStore,
) -> None:
    """Refine names the commit it read, which moves between rounds while the facts stay."""
    number = store.seed_issue("waits")
    first = _refine(_WAITS.format(sha="a9d6d9fd373f"))

    store.comment(number, first)
    store.comment(number, _refine(_WAITS.format(sha="0232651a6e35")))

    assert (_bodies(store, number), store.writes) == ([first], ["comment"])


def test_a_changed_fact_posts_a_new_comment(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("waits")
    first = _refine(_WAITS.format(sha="a9d6d9fd373f"))
    changed = _refine(
        "Refine cannot set this item to Ready at 0232651a6e35 while #3567 stays open."
    )

    store.comment(number, first)
    store.comment(number, changed)

    assert _bodies(store, number) == [first, changed]


def test_a_reply_of_a_person_ends_the_run_so_the_same_answer_posts_again(
    store: InMemoryRoadmapStore,
) -> None:
    """A job that reads the replies after its last comment sees the reply as answered only when
    its answer follows the reply."""
    number = store.seed_issue("waits")
    asked = _refine(_WAITS.format(sha="a9d6d9fd373f"))

    store.comment(number, asked)
    store.as_actor("alice").comment(number, "#3566 is not needed.")
    store.comment(number, asked)

    assert _bodies(store, number) == [asked, "#3566 is not needed.", asked]


def test_a_comment_of_another_job_ends_the_run(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("returned")
    asked = _refine(_WAITS.format(sha="a9d6d9fd373f"))
    returned = f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nThe plan waits on #3566."

    store.comment(number, asked)
    store.comment(number, returned)
    store.comment(number, asked)

    assert _bodies(store, number) == [asked, returned, asked]


def test_flapping_comments_of_one_job_post_once_each(store: InMemoryRoadmapStore) -> None:
    """A stop and its clear that alternate, each at a new image digest, post one time each."""
    number = store.seed_issue("flaps")
    digests = ("a90f6ade2b0e8f17e7e6ceb55a64b5ec8cc7571040ea99968cc09598b784566c", "1" * 64)

    for digest in digests:
        store.comment(number, _implement(_STOPPED))
        store.comment(number, _implement(_CLEARED.format(digest=digest)))

    assert _bodies(store, number) == [
        _implement(_STOPPED),
        _implement(_CLEARED.format(digest=digests[0])),
    ]


@pytest.mark.parametrize(("days", "posted"), [(6, 1), (7, 2)], ids=["six-days", "seven-days"])
def test_a_repeat_seven_days_after_the_first_posts_again(
    store: InMemoryRoadmapStore, clock: _Clock, days: int, posted: int
) -> None:
    """A wait that lasts a week gets one comment each week."""
    number = store.seed_issue("waits")

    store.comment(number, _refine(_WAITS.format(sha="a9d6d9fd373f")))
    clock.now += timedelta(days=days)
    store.comment(number, _refine(_WAITS.format(sha="0232651a6e35")))

    assert len(_bodies(store, number)) == posted


def test_a_comment_of_a_person_is_never_refused(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("asked")

    store.comment(number, "Any update?")
    store.comment(number, "Any update?")

    assert _bodies(store, number) == ["Any update?", "Any update?"]


def test_a_close_posts_no_repeat_and_still_closes(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue("superseded")
    said = _refine("Superseded by #2399.")
    store.comment(number, said)

    store.close(number, CloseReason.NOT_PLANNED, comment=said)

    held = next(issue for issue in store.issues() if issue.number == number)
    assert (_bodies(store, number), held.state) == ([said], GitHubState.CLOSED)


def test_a_refused_repeat_counts_once_under_the_row_of_its_job(
    store: InMemoryRoadmapStore, otlp: FakeCollector
) -> None:
    number = store.seed_issue("waits")
    for _ in range(2):
        store.comment(number, _refine(_WAITS.format(sha="a9d6d9fd373f")))
        store.comment(number, _refine(_WAITS.format(sha="a9d6d9fd373f")))
    store.comment(number, _implement(_STOPPED))
    store.comment(number, _implement(_STOPPED))

    assert sorted(
        (attrs["row"], value)
        for attrs, value in otlp.points(ROADMAP_COMMENT_REPEATS_REFUSED_TOTAL.name)
    ) == [("implement", 1.0), ("refine", 3.0)]


def test_each_job_marker_names_a_job_and_the_counter_has_at_most_12_series() -> None:
    """The implement job marks its comments too, so a reader of a person's replies leaves them
    out."""
    jobs = {job for _, job in COMMENT_JOBS}
    assert (
        CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER in CONST_ROADMAP_JOB_COMMENT_MARKERS,
        [marker for marker, _ in COMMENT_JOBS] == list(CONST_ROADMAP_JOB_COMMENT_MARKERS),
        len(jobs) <= 12,
    ) == (True, True, True)
