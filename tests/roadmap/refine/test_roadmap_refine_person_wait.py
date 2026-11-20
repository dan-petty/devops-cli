"""The wait on a person: what gives the item a new look, and the bounds of the check (#1335). A wait
that older rules set gets one new look (#4795)."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake
import pytest

from devops_cli.config import constants
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.refine.refine import (
    apply_refine,
    plan_refine,
    refine_left_out,
    select_candidates,
    text_paths,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_refine import (
    CITED_PATH,
    QUESTION,
    READY,
    REFINE_MARKER,
    REPO,
    BodyReadCountingStore,
    refine_comment_at,
    refine_round,
    require_item,
    seed_item,
    seed_person_wait,
    stage_returns,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_person_wait_whose_question_names_an_issue_that_closed_after_it_gets_a_new_look(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    number = seed_person_wait(store, f"Does the work of #{named} cover this item?")
    model_fake.answer(READY)
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(named, CloseReason.COMPLETED)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in waiting.waiting_items if w.item.number == number],
        [r.item.number for r in again.refined_items],
    ) == ([number], [number])


def test_a_person_wait_ends_when_an_issue_that_a_reply_the_round_read_names_closes(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """The questions of refine may name no issue, while the comment of a person that the round
    read does: the wait text holds both."""
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    number = seed_item(store, "New", "P1-High")
    store.set_marks(
        require_item(store, number),
        {
            RefineRecordKey.BODY_HASH: hash_text(require_item(store, number).body),
            RefineRecordKey.NEXT_STEP: "person",
        },
    )
    store.as_actor("alice").comment(number, f"This waits for #{named}.")
    store.seed_comment(number, f"{REFINE_MARKER}\nA person answers these questions.")
    model_fake.answer(READY)
    waiting = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").close_by_hand(named, CloseReason.COMPLETED)

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in waiting.waiting_items],
        [r.item.number for r in again.refined_items],
    ) == ([number], [number])


@pytest.mark.parametrize("closes_after", [False, True], ids=["closed-before", "other-repository"])
def test_a_person_wait_keeps_waiting_when_the_issue_it_names_is_no_new_cause(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake, closes_after: bool
) -> None:
    """An issue that closed before the wait began is no cause that ended, and the number of an
    issue of another repository names no issue of this one."""
    store.seed_visibility(is_private=True)
    named = seed_item(store, "In Progress", "P1-High")
    person = store.as_actor("alice")
    if not closes_after:
        person.close_by_hand(named, CloseReason.COMPLETED)
    reference = f"other/repo#{named}" if closes_after else f"#{named}"
    number = seed_person_wait(store, f"Does the work of {reference} cover this item?")
    if closes_after:
        person.close_by_hand(named, CloseReason.COMPLETED)
    calls = model_fake.call_count

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in plan.waiting_items],
        plan.refined_items,
        model_fake.call_count - calls,
    ) == ([number], [], 0)


def test_a_person_wait_whose_text_names_a_path_that_changed_gets_a_new_look_with_no_block_paths(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    store.seed_visibility(is_private=True)
    number = seed_person_wait(store, f"Should `{CITED_PATH}:2` return a name?", paths=None)
    model_fake.answer(READY)
    store.seed_commit("src/other.py", at=datetime.now(UTC) + timedelta(minutes=5))
    unchanged = plan_refine(store, repo=REPO, source=git_repo)
    store.seed_commit(CITED_PATH, at=datetime.now(UTC) + timedelta(minutes=5))

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [w.item.number for w in unchanged.waiting_items],
        [r.item.number for r in again.refined_items],
    ) == ([number], [number])


def test_a_round_gives_no_more_new_looks_than_its_limit(
    git_repo: Path, store: InMemoryRoadmapStore, model_fake: ModelFake
) -> None:
    """Four items that the stage job returned, and a limit of two: the round refines two and
    makes two model calls. The others wait for a later round."""
    store.seed_visibility(is_private=True)
    for _ in range(4):
        seed_item(store, "New", "P1-High")
    model_fake.answer(READY)
    apply_refine(store, plan_refine(store, repo=REPO, source=git_repo, limit=10))
    for item in store.open_items():
        stage_returns(store, item.number)
    calls = model_fake.call_count

    limited = plan_refine(store, repo=REPO, source=git_repo, limit=2)

    assert (len(limited.refined_items), model_fake.call_count - calls) == (2, 2)


def test_the_check_of_a_wait_text_reads_at_most_the_bound_of_issues_and_of_paths(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A wait text that names twelve issues and twelve paths costs the bound of reads for each."""
    store.seed_visibility(is_private=True)
    named = [seed_item(store, "In Progress", "P1-High") for _ in range(12)]
    paths = [f"src/gone_{index}.py" for index in range(12)]
    text = " ".join([*(f"#{number}" for number in named), *(f"`{path}`" for path in paths)])
    number = seed_person_wait(store, text)
    store.reads.clear()

    _, waiting = select_candidates(store, limit=3)

    bound = constants.CONST_ROADMAP_REFINE_MAX_WAIT_CHECKS
    assert (
        [w.item.number for w in waiting if w.item.number == number],
        dict(Counter(store.reads)),
    ) == (
        [number],
        {"item": bound, "path_changed_at": bound},
    )


# ── A wait records only the paths that the tree holds (#6444) ──────────────────────────────


class _PathReads(InMemoryRoadmapStore):
    """The roadmap that keeps each path whose commits a wait check reads."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.path_reads: list[str] = []

    def path_changed_at(self, path: str) -> datetime | None:
        """The time of the last commit that changed `path`, kept for the test."""
        self.path_reads.append(path)
        return super().path_changed_at(path)


def test_a_wait_text_keeps_only_the_paths_of_the_tree(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """A decimal, a version, a dotted setting and a domain use the characters of a file name, and
    take no slot of the five: the two files that the text names are watched (#6444)."""
    store.seed_visibility(is_private=True)
    number = seed_person_wait(
        store,
        "0.202 and v1.37.2 and ai.portkey_url and deps.dev are named before CONTEXT.md and "
        "src/sample.py",
    )

    refine_round(store, git_repo)

    assert require_item(store, number).job_record.get(RefineRecordKey.WAIT_REFS) == (
        "CONTEXT.md,src/sample.py"
    )


def test_a_wait_text_keeps_the_first_five_paths_of_the_tree() -> None:
    """The cap counts the paths that the tree holds, so the first five real paths take its
    slots."""
    paths = [f"src/file_{index}.py" for index in range(6)]

    assert (
        text_paths(" ".join(f"`{path}`" for path in paths), tracked_paths=frozenset(paths))
        == paths[:5]
    )


def test_a_path_that_a_period_or_a_comma_follows_is_a_path() -> None:
    """A file that ends a sentence, or a clause, is a path of the wait."""
    tree = frozenset({"src/devops_cli/commands/ai.py", "AGENTS.md"})

    assert (
        text_paths("Read src/devops_cli/commands/ai.py.", tracked_paths=tree),
        text_paths("See AGENTS.md,", tracked_paths=tree),
    ) == (["src/devops_cli/commands/ai.py"], ["AGENTS.md"])


def test_a_run_of_paths_keeps_each_path() -> None:
    """The space after one path starts the next one, so each path of a run is a path (#6444)."""
    assert text_paths("Read a.py b.py c.py d.py") == ["a.py", "b.py", "c.py", "d.py"]


def test_a_directory_of_the_tree_is_a_path() -> None:
    """The tree holds a directory through the paths under it."""
    assert text_paths("foo.bar holds the record", tracked_paths=frozenset({"foo.bar/x.py"})) == [
        "foo.bar"
    ]


def test_a_false_path_of_a_wait_text_reads_no_commits(git_repo: Path) -> None:
    """A value that the tree does not hold never reaches the read of the commits of a path."""
    store = _PathReads(repo=REPO)
    store.seed_visibility(is_private=True)
    seed_person_wait(store, "0.202 and src/sample.py are named")

    plan_refine(store, repo=REPO, source=git_repo)

    assert store.path_reads == ["src/sample.py"]


def test_the_explain_verdict_reads_the_tree_for_the_paths_of_the_wait(
    git_repo: Path, store: InMemoryRoadmapStore
) -> None:
    """`devops roadmap explain` gives the answer of a round: a commit that changed the file that
    the wait names ends the wait, and a tree that does not hold the file keeps it."""
    store.seed_visibility(is_private=True)
    number = seed_person_wait(store, f"Should `{CITED_PATH}:2` return a name?")
    store.seed_commit(CITED_PATH, at=refine_comment_at(store, number) + timedelta(minutes=5))

    held = refine_left_out(store, require_item(store, number), tracked_paths=frozenset())
    ended = refine_left_out(
        store, require_item(store, number), tracked_paths=frozenset({CITED_PATH})
    )

    assert (held is not None, ended) == (True, None)


# ── A wait that older rules set gets one new look (#4795) ─────────────────────────────────

_DAY_BEFORE = timedelta(days=-1)
_HOUR_AFTER = timedelta(hours=1)


def _wait_set_at(commented: timedelta, rules: timedelta | None) -> tuple[InMemoryRoadmapStore, int]:
    """A New item that waits on a person since refine's comment at `commented` from the time of the
    current rules, whose job record holds the rules of `rules` from that time as the version of the
    rules of that round, or no version, as a round wrote it before rounds recorded one. The clock
    of the roadmap then reads now."""
    current = constants.CONST_ROADMAP_REFINE_RULES_SINCE
    clock = [current + commented]
    store = BodyReadCountingStore(repo=REPO, clock=lambda: clock[0])
    store.seed_visibility(is_private=True)
    number = seed_person_wait(store, "Which store holds the record?")
    if rules is not None:
        version = (current + rules).isoformat()
        store.set_marks(require_item(store, number), {RefineRecordKey.RULES: version})
    clock[0] = datetime.now(UTC)
    return store, number


@pytest.mark.parametrize(
    ("commented", "rules"),
    [(_DAY_BEFORE, None), (_HOUR_AFTER, _DAY_BEFORE)],
    ids=["comment-before-the-rules", "older-recorded-rules"],
)
def test_a_person_wait_that_older_rules_set_gets_one_new_look_on_an_unchanged_body(
    git_repo: Path, model_fake: ModelFake, commented: timedelta, rules: timedelta | None
) -> None:
    """A rule that changed since the round that left the wait could set another step. The next
    round refines the item once and records the current rules. When the new proposal asks a
    person again, a round after it leaves the item in its wait with no model call."""
    store, number = _wait_set_at(commented, rules)
    model_fake.answer(QUESTION)
    first = refine_round(store, git_repo)
    calls = model_fake.call_count

    again = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [r.item.number for r in first.refined_items],
        require_item(store, number).job_record.get(RefineRecordKey.RULES),
        [(w.item.number, w.step.value) for w in again.waiting_items],
        model_fake.call_count - calls,
    ) == (
        [number],
        constants.CONST_ROADMAP_REFINE_RULES_SINCE.isoformat(),
        [(number, "person")],
        0,
    )


@pytest.mark.parametrize(
    ("commented", "rules"),
    [(_HOUR_AFTER, None), (_DAY_BEFORE, timedelta(0))],
    ids=["comment-after-the-rules", "current-recorded-rules"],
)
def test_a_person_wait_that_the_current_rules_set_gets_no_new_look(
    git_repo: Path, model_fake: ModelFake, commented: timedelta, rules: timedelta | None
) -> None:
    """The version that the job record holds counts before the time of refine's comment."""
    store, number = _wait_set_at(commented, rules)
    calls = model_fake.call_count

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        [(w.item.number, w.step.value) for w in plan.waiting_items],
        plan.refined_items,
        model_fake.call_count - calls,
    ) == ([(number, "person")], [], 0)


@pytest.mark.parametrize("no_zone", [False, True], ids=["no-time", "no-zone"])
def test_a_recorded_version_that_is_no_time_counts_as_none_and_one_with_no_zone_as_utc(
    git_repo: Path, model_fake: ModelFake, caplog: pytest.LogCaptureFixture, no_zone: bool
) -> None:
    """A hand edit of the job record can write a version that is no time, which gives way to the
    time of refine's comment with a warning, or a time with no zone, which is a UTC time. Both
    waits here are older than the rules."""
    older = constants.CONST_ROADMAP_REFINE_RULES_SINCE + _DAY_BEFORE
    store, number = _wait_set_at(_HOUR_AFTER if no_zone else _DAY_BEFORE, None)
    version = older.replace(tzinfo=None).isoformat() if no_zone else "not a time"
    store.set_marks(require_item(store, number), {RefineRecordKey.RULES: version})
    model_fake.answer(READY)

    plan = plan_refine(store, repo=REPO, source=git_repo)

    warned = f"The rules version recorded on #{number} is not a time."
    assert (
        [r.item.number for r in plan.refined_items],
        [r.getMessage() for r in caplog.records if r.getMessage() == warned],
    ) == ([number], [] if no_zone else [warned])
