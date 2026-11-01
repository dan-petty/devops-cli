"""The clear rules of a stop (#2912): the Service takes an item out of Blocked when a person asks
for a retry, or one time when the runner image changed since the stop.

The roadmap is in memory. The digest of the CronJob template is a function that a test counts.
"""

from __future__ import annotations

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER as MARKER
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stop_clear import StopsCleared, clear_stops
from devops_cli.roadmap.store import ImplementRecordKey, Item, ItemField
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
NO_PLANS = PlannedChanges("main", {}, {})


class Template:
    """The digest of CronJob `devops-cli-runner`, and how often a round read it."""

    def __init__(self, digest: str | None) -> None:
        self.digest = digest
        self.reads = 0

    def __call__(self) -> str | None:
        self.reads += 1
        return self.digest


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


def _blocked(
    store: InMemoryRoadmapStore,
    *,
    digest: str | None = DIGEST_A,
    status: str = "Blocked",
    stopped: str | None = "group 1",
    **marks: str,
) -> int:
    """An item that a stop of the job set Blocked, with its stop comment."""
    number = store.seed_issue("fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium"})
    item = store.item(number)
    assert item is not None
    store.set_field(
        item,
        ItemField.STATUS,
        status,
        marks={
            ImplementRecordKey.STOPPED: stopped,
            ImplementRecordKey.JOB: "devops-cli-runner-1",
            ImplementRecordKey.JOB_STATE: "failed",
            ImplementRecordKey.JOB_DIGEST: digest,
            **{ImplementRecordKey(key.replace("_", ".", 1)): value for key, value in marks.items()},
        },
    )
    store.seed_comment(number, f"{MARKER}\nStopped at {stopped}.", author_association="NONE")
    return number


def _item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _record(store: InMemoryRoadmapStore, number: int) -> dict[str, str | None]:
    return {str(key): value for key, value in _item(store, number).job_record.items()}


def _bodies(store: InMemoryRoadmapStore, number: int) -> list[str]:
    return [c.body for c in store.comments_on(number)]


def _clear(
    store: InMemoryRoadmapStore, template: Template, planned: PlannedChanges = NO_PLANS
) -> StopsCleared:
    return clear_stops(store, planned=planned, digest=template)


def test_a_new_digest_clears_the_stop_and_the_comment_names_the_rule_and_both_digests(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store)

    cleared = _clear(store, Template(DIGEST_B))

    comment = _bodies(store, number)[-1]
    assert (
        cleared.cleared,
        cleared.failed,
        _item(store, number).status,
        _record(store, number).get("implement.stopped"),
        comment.startswith(MARKER),
        "rule `digest`" in comment,
        DIGEST_A in comment,
        DIGEST_B in comment,
    ) == ((number,), (), "Ready", None, True, True, True, True)


def test_a_cleared_item_whose_plan_is_merged_is_planned(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store)
    plans = PlannedChanges("main", {number: f"{number}-a-change"}, {})

    _clear(store, Template(DIGEST_B), plans)

    assert _item(store, number).status == "Planned"


def test_the_same_digest_clears_nothing_in_ten_rounds(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store)
    template = Template(DIGEST_A)

    rounds = [_clear(store, template) for _ in range(10)]

    assert (
        [r.cleared for r in rounds],
        _item(store, number).status,
        _record(store, number)["implement.stopped"],
        len(_bodies(store, number)),
    ) == ([()] * 10, "Blocked", "group 1", 1)


def test_a_stop_with_no_digest_on_record_is_not_cleared_by_a_digest(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, digest=None)

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_template_with_no_digest_clears_no_stop(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store)

    cleared = _clear(store, Template(None))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_a_retry_of_a_trusted_person_clears_the_stop_on_the_same_digest_at_once(
    store: InMemoryRoadmapStore, association: str
) -> None:
    number = _blocked(store)
    store.seed_comment(number, "implement: retry", author_association=association)

    cleared = _clear(store, Template(DIGEST_A))

    comment = _bodies(store, number)[-1]
    assert (
        cleared.cleared,
        _item(store, number).status,
        _record(store, number).get("implement.stopped"),
        "rule `retry`" in comment,
        "digest" in comment.replace("rule `retry`", ""),
    ) == ((number,), "Ready", None, True, False)


def test_a_retry_wins_over_a_new_digest_in_the_name_of_the_rule(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store)
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    _clear(store, Template(DIGEST_B))

    assert "rule `retry`" in _bodies(store, number)[-1]


def test_a_retry_of_a_stranger_clears_nothing(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store)
    store.seed_comment(number, "implement: retry", author_association="NONE")

    cleared = _clear(store, Template(DIGEST_A))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_retry_made_before_the_stop_comment_is_not_a_retry(
    store: InMemoryRoadmapStore,
) -> None:
    number = store.seed_issue("fix(cli): one", fields={ItemField.PRIORITY: "P2-Medium"})
    store.seed_comment(number, "implement: retry", author_association="OWNER")
    store.seed_comment(number, f"{MARKER}\nStopped at group 1.", author_association="NONE")
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 1", ImplementRecordKey.JOB_DIGEST: DIGEST_A},
    )

    cleared = _clear(store, Template(DIGEST_A))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_second_stop_on_the_new_digest_is_not_cleared_again(
    store: InMemoryRoadmapStore,
) -> None:
    """The next Job records the digest of the template, so the second stop holds the new digest."""
    number = _blocked(store)
    template = Template(DIGEST_B)
    first = _clear(store, template)
    store.set_marks(_item(store, number), {ImplementRecordKey.JOB_DIGEST: DIGEST_B})
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={ImplementRecordKey.STOPPED: "group 2"},
    )

    later = [_clear(store, template) for _ in range(5)]

    assert (first.cleared, [r.cleared for r in later], _item(store, number).status) == (
        (number,),
        [()] * 5,
        "Blocked",
    )


def test_a_third_digest_clears_the_stop_once_more(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store, digest=DIGEST_B)

    cleared = _clear(store, Template(DIGEST_A))

    assert (cleared.cleared, _item(store, number).status) == ((number,), "Ready")


def test_a_template_is_read_once_for_many_items_and_not_at_all_when_none_needs_it(
    store: InMemoryRoadmapStore,
) -> None:
    _blocked(store)
    _blocked(store)
    template = Template(DIGEST_B)
    _clear(store, template)
    idle = Template(DIGEST_B)
    _clear(InMemoryRoadmapStore(repo=STAGE_REPO), idle)

    assert (template.reads, idle.reads) == (1, 0)


def test_an_item_that_a_job_still_holds_is_not_cleared(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store)
    store.set_marks(_item(store, number), {ImplementRecordKey.JOB_STATE: None})

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


@pytest.mark.parametrize("label", ["owner/agent", "owner/human"])
def test_an_item_that_an_agent_or_a_person_claimed_is_not_cleared(
    store: InMemoryRoadmapStore, label: str
) -> None:
    number = _blocked(store)
    store.as_actor("alice").add_label(number, label)

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_blocked_label_that_a_person_set_is_not_cleared(store: InMemoryRoadmapStore) -> None:
    """The record holds `Ready`: a person set `status/blocked` over a stop that was cleared."""
    number = _blocked(store, status="Ready")
    store.remove_label(number, "status/ready")
    store.add_label(number, "status/blocked")

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_blocked_item_with_no_stop_on_record_is_not_cleared(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, stopped=None)

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_change_of_a_person_after_the_cached_read_is_not_written_over(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store)
    real_items = store.items

    def stale(*args: object, **kwargs: object) -> list[Item]:
        listed = real_items(*args, **kwargs)  # type: ignore[arg-type]
        store.remove_label(number, "status/blocked")
        store.add_label(number, "status/in-progress")
        return listed

    store.items = stale  # type: ignore[method-assign]

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, cleared.failed, _item(store, number).status) == (
        (),
        (),
        "In Progress",
    )


def test_one_item_that_fails_does_not_stop_the_others(store: InMemoryRoadmapStore) -> None:
    first = _blocked(store)
    second = _blocked(store)
    real_comment = store.comment

    def comment(number: int, body: str) -> None:
        if number == first:
            raise ClusterJobError("boom")
        real_comment(number, body)

    store.comment = comment  # type: ignore[method-assign]

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, [f.number for f in cleared.failed]) == ((second,), [first])


def test_a_rate_limit_stops_the_pass(store: InMemoryRoadmapStore) -> None:
    _blocked(store)

    def limited(number: int, body: str) -> None:
        raise GitHubRateLimitError("rate limit")

    store.comment = limited  # type: ignore[method-assign]

    with pytest.raises(GitHubRateLimitError, match="rate limit"):
        _clear(store, Template(DIGEST_B))
