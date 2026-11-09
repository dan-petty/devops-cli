"""The clear rules of a stop (#2912, #3481, #3721): the Service takes an item out of Blocked when a
person asks for a retry, when the Job of the item ended without a result and the class of the stop
has the action `retry`, or when the runner image changed since the stop and the class of the stop
has the action `retry`, within the limits of the item.

The roadmap is in memory. The digest of the CronJob template is a function that a test counts.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_COMMENT_MARKER as MARKER
from devops_cli.exceptions import GitHubRateLimitError
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.digest_clears import (
    DigestClear,
    encode_clears,
    last_clear_comment,
    recorded_clears,
)
from devops_cli.roadmap.failure import ACTION_BY_CLASS, FailureAction, FailureClass
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.stop_clear import ClearLimits, StopsCleared, clear_stops
from devops_cli.roadmap.stores.store import ImplementRecordKey, IssueComment, Item, ItemField
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
NO_PLANS = PlannedChanges("main", {}, {})
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LIMITS = ClearLimits(per_class=1, per_item=3, continuations=2)
RETRY_CLASSES = [c for c, action in ACTION_BY_CLASS.items() if action is FailureAction.RETRY]
OTHER_CLASSES = [c for c, action in ACTION_BY_CLASS.items() if action is not FailureAction.RETRY]


class Template:
    """The digest of CronJob `devops-cli-runner`, and how often a round read it."""

    def __init__(self, digest: str | None, *, error: Exception | None = None) -> None:
        self.digest = digest
        self.error = error
        self.reads = 0

    def __call__(self) -> str | None:
        self.reads += 1
        if self.error is not None:
            raise self.error
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
    implement_failure: str | None = "provider",
    **marks: str,
) -> int:
    """An item that a stop of the job set Blocked, with its stop comment. The class of the stop is
    `provider`, whose action is `retry`."""
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
            ImplementRecordKey.FAILURE: implement_failure,
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
    store: InMemoryRoadmapStore,
    template: Template,
    planned: PlannedChanges = NO_PLANS,
    *,
    limits: ClearLimits = LIMITS,
    now: datetime = NOW,
) -> StopsCleared:
    return clear_stops(store, planned=planned, digest=template, limits=limits, now=now)


def _entry(klass: FailureClass, digest: str = DIGEST_A, age: timedelta = timedelta(days=2)) -> str:
    """The record of one earlier digest clear, `age` before `NOW`."""
    return encode_clears((DigestClear(failure_class=klass, digest=digest, time=NOW - age),))


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


def test_a_clear_removes_the_failure_class_and_the_check_with_the_stop_and_keeps_the_log(
    store: InMemoryRoadmapStore,
) -> None:
    """The next Job hands the log to its first step and clears it in its first record write
    (#4071)."""
    number = _blocked(
        store,
        implement_failure="timeout",
        implement_check="static",
        implement_check_log="a.py:3: error: bad",
    )

    _clear(store, Template(DIGEST_B))

    record = _record(store, number)
    assert [
        record.get(k) for k in ("implement.failure", "implement.check", "implement.check_log")
    ] == [None, None, "a.py:3: error: bad"]


def test_a_clear_keeps_the_conflicted_files_for_the_next_job(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store, implement_conflict='["docs/a.md"]')

    _clear(store, Template(DIGEST_B))

    assert _record(store, number).get("implement.conflict") == '["docs/a.md"]'


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


def test_a_digest_that_cannot_be_read_is_read_once_and_fails_each_item_that_needs_it(
    store: InMemoryRoadmapStore,
) -> None:
    """One read of the CronJob fails for the whole pass. The retry rule needs no digest, so an
    item with a retry still clears."""
    waiting = [_blocked(store) for _ in range(4)]
    retried = _blocked(store)
    store.seed_comment(retried, "implement: retry", author_association="OWNER")
    template = Template(None, error=ClusterJobError("CronJob devops/devops-cli-runner not found"))

    cleared = _clear(store, template)

    assert (
        template.reads,
        cleared.cleared,
        [failure.number for failure in cleared.failed],
        [_item(store, number).status for number in waiting],
    ) == (1, (retried,), waiting, ["Blocked"] * 4)


def test_an_idle_pass_reads_the_comments_of_each_stop_and_nothing_else(
    store: InMemoryRoadmapStore,
) -> None:
    """The cost of a Blocked stop that no rule clears is one request for each round: the listing
    of its comments. The issue is read again only before a write."""
    numbers = [_blocked(store) for _ in range(3)]
    reads: list[str] = []
    real_item, real_comments = store.item, store.comments_on

    def item(number: int) -> Item | None:
        reads.append("item")
        return real_item(number)

    def comments_on(number: int) -> list[IssueComment]:
        reads.append("comments")
        return real_comments(number)

    store.item = item  # type: ignore[method-assign]
    store.comments_on = comments_on  # type: ignore[method-assign]

    cleared = _clear(store, Template(DIGEST_A))

    assert (cleared.cleared, reads) == ((), ["comments"] * len(numbers))


def test_a_new_digest_does_not_clear_a_stop_for_a_lost_test(store: InMemoryRoadmapStore) -> None:
    """A new image cannot restore a test, and a step that repeats the run spends the same tokens
    (#3490)."""
    number = _blocked(store, implement_failure=FailureClass.TESTS_LOST.value)

    assert _clear(store, Template(DIGEST_B)).cleared == ()
    assert _item(store, number).status == "Blocked"


def test_the_action_table_has_retry_classes_and_others() -> None:
    """The rule reads the table, so a test holds the classes that the cases below name."""
    assert {"provider", "timeout", "ci_infra"} <= {c.value for c in RETRY_CLASSES}
    assert {"plan_defect", "refused_tool", "premise_false", "test"} <= {
        c.value for c in OTHER_CLASSES
    }


@pytest.mark.parametrize("text", ["implement_comment_stopped", "implement_job_report_stopped"])
def test_a_stop_comment_names_the_class_rule_and_the_limits_of_the_digest_clear(text: str) -> None:
    """The stop comments must not promise a clear of every stop by a new runner image."""
    body = " ".join(getattr(MESSAGES.roadmap, text).split())

    assert "one time" not in body
    assert "only if a retry can fix the class of the stop" in body
    assert "roadmap.implement.digest_clears_per_class" in body
    assert "roadmap.implement.digest_clears_per_item" in body


def test_the_report_of_a_job_with_no_result_names_the_continuation_the_retry_and_the_image() -> (
    None
):
    """The report comes before the clear, so it says what the Service does next (#3721)."""
    body = " ".join(MESSAGES.roadmap.implement_job_report_stopped.split())

    assert "starts a new Job" in body
    assert "roadmap.implement.continuations_per_item" in body
    assert "comment `implement: retry`" in body
    assert "A new runner image also clears the stop" in body


@pytest.mark.parametrize("klass", OTHER_CLASSES)
def test_a_new_digest_alone_does_not_clear_a_stop_of_a_class_that_a_retry_cannot_fix(
    store: InMemoryRoadmapStore, klass: FailureClass
) -> None:
    number = _blocked(store, implement_failure=klass.value)
    template = Template(DIGEST_B)

    cleared = _clear(store, template)

    assert (
        cleared.cleared,
        _item(store, number).status,
        template.reads,
        len(_bodies(store, number)),
    ) == ((), "Blocked", 0, 1)


@pytest.mark.parametrize("klass", OTHER_CLASSES)
@pytest.mark.parametrize("association", ["OWNER", "MEMBER", "COLLABORATOR"])
def test_implement_retry_still_clears_a_stop_of_any_class(
    store: InMemoryRoadmapStore, klass: FailureClass, association: str
) -> None:
    number = _blocked(store, implement_failure=klass.value)
    store.seed_comment(number, "implement: retry", author_association=association)

    cleared = _clear(store, Template(DIGEST_A))

    assert (
        cleared.cleared,
        _item(store, number).status,
        "rule `retry`" in _bodies(store, number)[-1],
    ) == ((number,), "Ready", True)


def test_a_new_digest_does_not_clear_a_stop_with_no_class_on_record(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, implement_failure=None)

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_new_digest_does_not_clear_a_stop_with_a_class_the_table_does_not_know(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, implement_failure="made_up")

    cleared = _clear(store, Template(DIGEST_B))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


@pytest.mark.parametrize("klass", RETRY_CLASSES)
def test_a_new_digest_clears_a_stop_of_a_retry_class_and_records_the_clear(
    store: InMemoryRoadmapStore, klass: FailureClass
) -> None:
    number = _blocked(store, implement_failure=klass.value)

    cleared = _clear(store, Template(DIGEST_B))

    assert (
        cleared.cleared,
        _item(store, number).status,
        recorded_clears(_item(store, number)),
    ) == ((number,), "Ready", (DigestClear(failure_class=klass, digest=DIGEST_B, time=NOW),))


def test_a_clear_by_retry_keeps_the_record_of_the_clears_and_adds_none(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, implement_digest_clears=_entry(FailureClass.PROVIDER))
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    _clear(store, Template(DIGEST_B))

    assert [c.digest for c in recorded_clears(_item(store, number))] == [DIGEST_A]


@pytest.mark.parametrize("klass", RETRY_CLASSES)
def test_a_stop_at_the_class_limit_stays_until_implement_retry(
    store: InMemoryRoadmapStore, klass: FailureClass
) -> None:
    number = _blocked(store, implement_failure=klass.value, implement_digest_clears=_entry(klass))
    template = Template(DIGEST_B)

    held = _clear(store, template)
    store.seed_comment(number, "implement: retry", author_association="OWNER")
    retried = _clear(store, template)

    assert (held.cleared, retried.cleared, _item(store, number).status) == ((), (number,), "Ready")


def test_a_second_retry_class_clears_below_the_item_limit(store: InMemoryRoadmapStore) -> None:
    number = _blocked(
        store, implement_failure="timeout", implement_digest_clears=_entry(FailureClass.PROVIDER)
    )

    cleared = _clear(store, Template(DIGEST_B))

    assert (
        cleared.cleared,
        [c.failure_class.value for c in recorded_clears(_item(store, number))],
    ) == ((number,), ["provider", "timeout"])


def test_a_stop_at_the_item_limit_stays_until_implement_retry(
    store: InMemoryRoadmapStore,
) -> None:
    earlier = encode_clears(
        tuple(
            DigestClear(failure_class=klass, digest=DIGEST_A, time=NOW - timedelta(days=2))
            for klass in (FailureClass.TIMEOUT, FailureClass.CI_INFRA, FailureClass.PARSER)
        )
    )
    number = _blocked(store, implement_failure="provider", implement_digest_clears=earlier)
    template = Template(DIGEST_B)

    held = _clear(store, template)
    store.seed_comment(number, "implement: retry", author_association="OWNER")
    retried = _clear(store, template)

    assert (held.cleared, retried.cleared) == ((), (number,))


def test_the_limits_are_values_of_the_pass(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store, implement_digest_clears=_entry(FailureClass.PROVIDER))

    wide = _clear(
        store, Template(DIGEST_B), limits=ClearLimits(per_class=2, per_item=3, continuations=2)
    )

    assert (wide.cleared, len(recorded_clears(_item(store, number)))) == ((number,), 2)


@pytest.mark.parametrize("limits", [ClearLimits(0, 3, 2), ClearLimits(1, 0, 2)])
def test_a_limit_of_zero_turns_the_clear_by_digest_off(
    store: InMemoryRoadmapStore, limits: ClearLimits
) -> None:
    number = _blocked(store)

    cleared = _clear(store, Template(DIGEST_B), limits=limits)

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_clear_by_digest_writes_one_comment_in_a_day_and_records_each_clear(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, implement_failure="timeout")
    first = _clear(store, Template(DIGEST_B))
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={
            ImplementRecordKey.STOPPED: "group 2",
            ImplementRecordKey.FAILURE: "ci_infra",
            ImplementRecordKey.JOB_DIGEST: DIGEST_B,
        },
    )
    comments = len(_bodies(store, number))

    second = _clear(store, Template(DIGEST_A), now=NOW + timedelta(hours=23))

    assert (
        first.cleared,
        second.cleared,
        len(_bodies(store, number)) - comments,
        len(recorded_clears(_item(store, number))),
        last_clear_comment(_item(store, number)),
    ) == ((number,), (number,), 0, 2, NOW)


def test_a_clear_by_digest_after_a_day_writes_a_comment_and_sets_the_time(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(
        store,
        implement_failure="timeout",
        implement_digest_clears=_entry(FailureClass.PROVIDER),
        implement_digest_clear_commented_at=(NOW - timedelta(hours=24)).isoformat(),
    )
    comments = len(_bodies(store, number))

    _clear(store, Template(DIGEST_B))

    assert (len(_bodies(store, number)) - comments, last_clear_comment(_item(store, number))) == (
        1,
        NOW,
    )


def test_the_comment_of_a_clear_by_digest_names_the_class_and_the_limits(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, implement_failure="timeout")

    _clear(store, Template(DIGEST_B))

    comment = _bodies(store, number)[-1]
    assert (
        "`timeout`" in comment,
        "1 for each class" in comment,
        "3 for each item" in comment,
    ) == (
        True,
        True,
        True,
    )


def test_a_clear_by_retry_is_never_held_back_by_the_comment_cap(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(
        store, implement_digest_clear_commented_at=(NOW - timedelta(hours=1)).isoformat()
    )
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    _clear(store, Template(DIGEST_A))

    assert "rule `retry`" in _bodies(store, number)[-1]


@pytest.mark.parametrize("mark", ["implement_digest_clears", "implement_digest_clear_commented_at"])
def test_a_record_that_does_not_parse_stops_the_clear_by_digest_but_not_a_retry(
    store: InMemoryRoadmapStore, mark: str
) -> None:
    number = _blocked(store, **{mark: "not valid"})
    held = _clear(store, Template(DIGEST_B))
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    retried = _clear(store, Template(DIGEST_B))

    assert (held.cleared, held.failed, retried.cleared) == ((), (), (number,))


# ── A Job that ended without a result is continued (#3721) ──────────────────────────────────


def _continuations(store: InMemoryRoadmapStore, number: int) -> str | None:
    return _record(store, number).get("implement.continuations")


def _stop_again(store: InMemoryRoadmapStore, number: int, klass: str = "ci_infra") -> None:
    """The Job that a continuation started ends without a result, and a round reports it."""
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        "Blocked",
        marks={
            ImplementRecordKey.STOPPED: "job",
            ImplementRecordKey.FAILURE: klass,
            ImplementRecordKey.JOB_STATE: "failed",
        },
    )


@pytest.mark.parametrize("klass", RETRY_CLASSES)
def test_a_job_that_ended_without_a_result_is_continued_whatever_the_digest(
    store: InMemoryRoadmapStore, klass: FailureClass
) -> None:
    number = _blocked(store, stopped="job", implement_failure=klass.value)
    template = Template(DIGEST_A)

    cleared = _clear(store, template)

    comment = _bodies(store, number)[-1]
    record = _record(store, number)
    assert (
        cleared.cleared,
        _item(store, number).status,
        record.get("implement.stopped"),
        record.get("implement.failure"),
        _continuations(store, number),
        record.get("implement.digest_clears"),
        template.reads,
        comment.startswith(MARKER),
        "rule `continue`" in comment,
        f"`{klass.value}`" in comment,
        "continuation 1 of 2" in comment,
    ) == ((number,), "Ready", None, None, "1", None, 0, True, True, True, True)


@pytest.mark.parametrize("klass", OTHER_CLASSES)
def test_a_job_that_ended_without_a_result_waits_for_a_person_when_a_retry_cannot_fix_its_class(
    store: InMemoryRoadmapStore, klass: FailureClass
) -> None:
    number = _blocked(store, stopped="job", implement_failure=klass.value)

    held = _clear(store, Template(DIGEST_A))
    store.seed_comment(number, "implement: retry", author_association="OWNER")
    retried = _clear(store, Template(DIGEST_A))

    assert (held.cleared, _continuations(store, number), retried.cleared) == ((), None, (number,))


def test_a_stop_that_the_runner_wrote_is_not_a_continuation(store: InMemoryRoadmapStore) -> None:
    """A stop of a step has its own class and its own rules (#3053, #3065). Only the stop of a Job
    that left no result is a run that a kill, an eviction or a stall cut."""
    number = _blocked(store, stopped="group 2", implement_failure="provider")

    cleared = _clear(store, Template(DIGEST_A))

    assert (cleared.cleared, _item(store, number).status, _continuations(store, number)) == (
        (),
        "Blocked",
        None,
    )


def test_a_job_stop_with_no_class_is_not_continued(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store, stopped="job", implement_failure=None)

    cleared = _clear(store, Template(DIGEST_A))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_the_continuations_of_an_item_stop_at_the_limit_and_the_last_comment_says_so(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(store, stopped="job", implement_failure="ci_infra")
    template = Template(DIGEST_A)
    cleared: list[tuple[int, ...]] = []

    for _ in range(3):
        cleared.append(_clear(store, template).cleared)
        _stop_again(store, number)
    after_limit = _clear(store, template)

    comments = [b for b in _bodies(store, number) if "rule `continue`" in b]
    assert (
        cleared,
        after_limit.cleared,
        _item(store, number).status,
        _continuations(store, number),
        ["continuation 1 of 2" in comments[0], "continuation 2 of 2" in comments[1]],
        [
            len(comments),
            "No continuation is left" in comments[0],
            "No continuation is left" in comments[1],
        ],
    ) == (
        [(number,), (number,), ()],
        (),
        "Blocked",
        "2",
        [True, True],
        [2, False, True],
    )


def test_a_new_runner_image_clears_a_stop_at_the_continuation_limit_by_the_digest_rule(
    store: InMemoryRoadmapStore,
) -> None:
    """No continuation is left, but a new image is a retry signal: the rule `digest` clears."""
    number = _blocked(
        store, stopped="job", implement_failure="ci_infra", implement_continuations="2"
    )

    held = _clear(store, Template(DIGEST_A))
    cleared = _clear(store, Template(DIGEST_B))

    comment = _bodies(store, number)[-1]
    assert (
        held.cleared,
        cleared.cleared,
        "rule `digest`" in comment,
        _continuations(store, number),
    ) == (
        (),
        (number,),
        True,
        "2",
    )


def test_a_person_retry_clears_a_stop_at_the_continuation_limit(
    store: InMemoryRoadmapStore,
) -> None:
    number = _blocked(
        store, stopped="job", implement_failure="ci_infra", implement_continuations="2"
    )
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    cleared = _clear(store, Template(DIGEST_A))

    comment = _bodies(store, number)[-1]
    assert (cleared.cleared, "rule `retry`" in comment, _continuations(store, number)) == (
        (number,),
        True,
        "2",
    )


def test_a_limit_of_zero_turns_the_continuation_off(store: InMemoryRoadmapStore) -> None:
    number = _blocked(store, stopped="job", implement_failure="ci_infra")

    cleared = _clear(store, Template(DIGEST_A), limits=ClearLimits(1, 3, 0))

    assert (cleared.cleared, _item(store, number).status) == ((), "Blocked")


def test_a_continuation_spends_no_clear_by_digest(store: InMemoryRoadmapStore) -> None:
    """A new image and a Job that ended without a result: the continuation runs first, and the
    digest rule keeps its budget for the next stop."""
    number = _blocked(store, stopped="job", implement_failure="timeout")

    cleared = _clear(store, Template(DIGEST_B))

    assert (
        cleared.cleared,
        recorded_clears(_item(store, number)),
        _continuations(store, number),
    ) == (
        (number,),
        (),
        "1",
    )


@pytest.mark.parametrize("text", ["two", "-1", "1.5"])
def test_a_continuation_count_that_is_no_count_stops_the_continuation_but_not_a_retry(
    store: InMemoryRoadmapStore, text: str
) -> None:
    number = _blocked(
        store, stopped="job", implement_failure="ci_infra", implement_continuations=text
    )
    held = _clear(store, Template(DIGEST_A))
    store.seed_comment(number, "implement: retry", author_association="OWNER")

    retried = _clear(store, Template(DIGEST_A))

    assert (held.cleared, held.failed, retried.cleared) == ((), (), (number,))
