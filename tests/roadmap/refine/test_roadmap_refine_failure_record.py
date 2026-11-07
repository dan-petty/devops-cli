"""The record that refine keeps for an item that is too big to refine or that fails: when it
settles the item, and when the next round takes it again (#1335).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass
import httpx2
import pytest

from devops_cli.ai.client.models import (
    AIClientError,
    ReplyRejectedError,
    StructuredOutputValidationError,
)
from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STATUS_READY,
)
from devops_cli.exceptions import RoadmapRefineError
from devops_cli.roadmap.body_hash import hash_text
from devops_cli.roadmap.refine.refine import (
    RefinementProposal,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.stores.store import (
    ItemField,
    RefineRecordKey,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore, JobWrite
from tests.support.roadmap_refine import (
    CRITERION,
    CRITERION_JSON,
    FIRST,
    GATEWAY_ATTEMPTS,
    NO_OPEN_TOOL,
    PLACED,
    REPO,
    SCHEMA_MISS,
    Answer,
    BodyReadCountingStore,
    MockLLMClient,
    refine_round,
    requests_per_item,
    require_item,
    run_refine_adapter,
    seed_new_items,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_too_big_needs_split(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    """A proposal that does not fit one pull request leaves the item New and records it as
    needing a split; no job moves it out of its milestone."""
    num = store.seed_issue("Heavy task", body="Big work", milestone=FIRST, fields=PLACED)
    item = require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")
    store.set_field(item, ItemField.PRIORITY, "P1-High")

    proposal = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement="Too big",
        acceptance_criteria=[CRITERION],
        key_questions=[],
        fits_one_pr=False,
        split_offs=["Part 1", "Part 2"],
    )
    llm = MockLLMClient(proposal=proposal)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=num, model=llm)
    applied = apply_refine(store, plan)
    updated = store.item(num)
    assert updated is not None
    assert (
        updated.status,
        updated.milestone,
        updated.job_record.get(RefineRecordKey.NEEDS_SPLIT),
        applied.split_count == 1,
    ) == ("New", FIRST, "true", True)


def test_size_limit_guard(git_repo: Path, store: InMemoryRoadmapStore) -> None:
    num = store.seed_issue("Item", body="Initial", fields=PLACED)
    item = require_item(store, num)
    store.set_field(item, ItemField.STATUS, "New")

    # Proposal with massive text pushing past 65,536 chars
    huge_text = "A" * 70000
    huge_proposal = RefinementProposal(
        existing_tool=NO_OPEN_TOOL,
        problem_statement=huge_text,
        acceptance_criteria=[CRITERION],
    )
    llm = MockLLMClient(proposal=huge_proposal)

    plan = plan_refine(store, repo=REPO, source=git_repo, item_number=num, model=llm)
    refined = plan.refined_items[0]
    assert (
        plan.has_writes,
        refined.skip_reason is not None and "exceed" in refined.skip_reason,
        refined.record_only,
    ) == (True, True, True)


def _writes_to(store: InMemoryRoadmapStore, number: int) -> list[JobWrite]:
    """What jobs wrote to issue `number`, oldest first."""
    return [write for write in store.job_writes() if write.number == number]


def _refine_record(store: InMemoryRoadmapStore, number: int) -> tuple[str | None, ...]:
    """The body hash, the section hash and the failed body hash in issue `number`'s job record."""
    record = require_item(store, number).job_record
    return tuple(
        record.get(key)
        for key in (
            RefineRecordKey.BODY_HASH,
            RefineRecordKey.SECTION_HASH,
            RefineRecordKey.FAILED_BODY_HASH,
        )
    )


_FIRST_BODY_HASH = hash_text("Body P1-High")


# A proposal whose section alone would take the body past the size the guard allows.
_TOO_BIG_PROPOSAL = json.dumps(
    {
        "existing_tool": NO_OPEN_TOOL,
        "problem_statement": "A" * CONST_ROADMAP_REFINE_MAX_BODY_CHARS,
        "acceptance_criteria": [CRITERION_JSON],
    }
)


def test_an_item_whose_refined_body_is_too_big_is_selected_once_and_its_body_never_written(
    git_repo: Path,
    store: BodyReadCountingStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """The size guard records the body it saw and writes none: the next round finds the item
    waiting on a body edit and sends no request, whatever a person comments, until a person
    edits it (#1526, #1539, #1758)."""
    first, *_ = seed_new_items(store)
    sent = scripted_gateway({first: _TOO_BIG_PROPOSAL})

    first_round = refine_round(store, git_repo)
    after_first = (len(sent), store.read_issue_body(first), _writes_to(store, first))
    store.as_actor("alice").comment(first, "Please try again.")
    second_round = plan_refine(store, repo=REPO, source=git_repo)
    after_second = (
        len(sent),
        second_round.refined_items,
        [(w.item.number, w.step) for w in second_round.waiting_items],
    )
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")
    third_round = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        first_round.has_writes,
        after_first,
        after_second,
        [refined.item.number for refined in third_round.refined_items],
    ) == (
        True,
        (
            3,
            "Body P1-High",
            [
                JobWrite("set_mark", first, RefineRecordKey.BODY_HASH.value, _FIRST_BODY_HASH),
                JobWrite("set_mark", first, RefineRecordKey.SECTION_HASH.value, None),
                JobWrite("set_mark", first, RefineRecordKey.NEXT_STEP.value, "edit"),
            ],
        ),
        (3, [], [(first, "edit")]),
        [first],
    )


def test_two_replies_that_never_validate_on_the_same_body_settle_the_item(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """A reply that never fits the schema is the item's doing: the first failure records the
    body it saw and settles nothing, the second on the same body settles the item to wait on a
    body edit, and a person's edit unsettles it (#1526, #1539, #1758)."""
    first, *_ = seed_new_items(store)
    sent = scripted_gateway({first: SCHEMA_MISS})

    refine_round(store, git_repo)
    after_first = (len(sent), _refine_record(store, first))
    refine_round(store, git_repo)
    after_second = (len(sent), _refine_record(store, first))
    third_round = refine_round(store, git_repo)
    after_third = (
        len(sent),
        third_round.failed_items,
        [(w.item.number, w.step) for w in third_round.waiting_items],
    )
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")
    edited = plan_refine(store, repo=REPO, source=git_repo)

    assert (
        after_first,
        after_second,
        after_third,
        [failure.item.number for failure in edited.failed_items],
    ) == (
        (4, (None, None, _FIRST_BODY_HASH)),
        (6, (_FIRST_BODY_HASH, None, None)),
        (6, [], [(first, "edit")]),
        [first],
    )


def test_a_failure_followed_by_a_success_refines_the_item_and_clears_the_failure(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """One reply that never fits the schema does not stop the item: the next round refines it,
    and its record no longer holds the failure (#1526, #1539)."""
    first, *_ = seed_new_items(store)
    answers: dict[int | None, Answer] = {first: SCHEMA_MISS}
    scripted_gateway(answers)

    refine_round(store, git_repo)
    failed = _refine_record(store, first)
    del answers[first]
    refine_round(store, git_repo)

    item = require_item(store, first)
    body_hash, _, failed_body_hash = _refine_record(store, first)
    assert (
        failed,
        (body_hash, failed_body_hash),
        CONST_ROADMAP_REFINE_START_MARKER in store.read_issue_body(first),
        item.status,
    ) == (
        (None, None, _FIRST_BODY_HASH),
        (_FIRST_BODY_HASH, None),
        True,
        CONST_ROADMAP_STATUS_READY,
    )


def test_a_gateway_failure_records_nothing_and_the_next_round_selects_the_item_again(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """A timeout says nothing about the item, so however often it repeats, no record is written
    and the item stays due (#1539)."""
    first, second, third = seed_new_items(store)
    sent = scripted_gateway({first: httpx2.Response(504, text="Gateway Timeout")})

    rounds = [refine_round(store, git_repo), refine_round(store, git_repo)]

    assert (
        [[failure.item.number for failure in plan.failed_items] for plan in rounds],
        requests_per_item(sent),
        _writes_to(store, first),
        _refine_record(store, first),
    ) == (
        [[first], [first]],
        {first: 2 * GATEWAY_ATTEMPTS, second: 1, third: 1},
        [],
        (None, None, None),
    )


# Replies that leave an item too big to refine, or failing on its own text.
_TROUBLE_REPLIES = pytest.mark.parametrize(
    "reply", [_TOO_BIG_PROPOSAL, SCHEMA_MISS], ids=["too-big", "schema-miss"]
)


@pytest.mark.parametrize(
    ("reply", "marks", "exit_code"),
    [
        pytest.param(
            _TOO_BIG_PROPOSAL,
            [
                (RefineRecordKey.BODY_HASH.value, _FIRST_BODY_HASH),
                (RefineRecordKey.SECTION_HASH.value, None),
                ("refine.next_step", "edit"),
            ],
            0,
            id="too-big",
        ),
        pytest.param(
            SCHEMA_MISS,
            [(RefineRecordKey.FAILED_BODY_HASH.value, _FIRST_BODY_HASH)],
            1,
            id="schema-miss",
        ),
    ],
)
def test_a_round_whose_only_item_is_too_big_or_fails_still_records_it_through_the_cli(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    reply: str,
    marks: list[tuple[str, str | None]],
    exit_code: int,
    cli: Callable[..., Any],
) -> None:
    """With nothing else to write, `devops roadmap refine --confirm` still applies the plan:
    the item's record is written and its body is not (#1539)."""
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: reply})

    args = ["refine", "--repo", REPO, "--source", str(git_repo), "--confirm"]
    result = cli(["roadmap", *args])

    assert (result.exit_code, _writes_to(store, first)) == (
        exit_code,
        [JobWrite("set_mark", first, key, value) for key, value in marks],
    )


def test_the_runs_refine_job_records_an_item_too_big_to_refine(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
) -> None:
    """The refine job of `devops roadmap run` applies a plan whose only write is the record of
    an item too big to refine (#1539)."""
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: _TOO_BIG_PROPOSAL})

    run_refine_adapter(store, repo=REPO, clone_path=git_repo)

    assert _writes_to(store, first) == [
        JobWrite("set_mark", first, RefineRecordKey.BODY_HASH.value, _FIRST_BODY_HASH),
        JobWrite("set_mark", first, RefineRecordKey.SECTION_HASH.value, None),
        JobWrite("set_mark", first, RefineRecordKey.NEXT_STEP.value, "edit"),
    ]


@_TROUBLE_REPLIES
def test_planning_a_round_writes_no_body_and_no_record_for_an_item_too_big_or_failing(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    reply: str,
) -> None:
    """`--plan` writes nothing, though the plan holds a record to write (#1539)."""
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: reply})

    plan = plan_refine(store, repo=REPO, source=git_repo)

    assert (plan.has_writes, _writes_to(store, first), store.read_issue_body(first)) == (
        True,
        [],
        "Body P1-High",
    )


@_TROUBLE_REPLIES
def test_a_body_edited_between_the_plan_and_the_apply_is_recorded_as_neither_too_big_nor_failed(
    git_repo: Path,
    store: InMemoryRoadmapStore,
    scripted_gateway: Callable[..., list[httpx2.Request]],
    caplog: pytest.LogCaptureFixture,
    reply: str,
) -> None:
    """The record is of the body the model saw: a body a person changed since is left unrecorded,
    with the warning every skipped write has (#1539)."""
    (first,) = seed_new_items(store, ("P1-High",))
    scripted_gateway({first: reply})
    plan = plan_refine(store, repo=REPO, source=git_repo)
    store.as_actor("alice").write_issue_body(first, "Body P1-High, edited")
    caplog.clear()

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine.refine"):
        apply_refine(store, plan)

    assert (_writes_to(store, first), caplog.messages) == (
        [],
        [f"Skipping #{first}: the body changed between the read and the write."],
    )


@pytest.mark.parametrize(
    ("error", "recorded"),
    [
        pytest.param(
            StructuredOutputValidationError("never valid", violations=2), True, id="schema"
        ),
        pytest.param(ReplyRejectedError("refused", reply="x"), True, id="rejected"),
        pytest.param(AIClientError("timed out"), False, id="transport"),
    ],
)
def test_only_a_failure_the_items_own_text_caused_is_recorded(
    git_repo: Path, store: InMemoryRoadmapStore, error: AIClientError, recorded: bool
) -> None:
    """A reply the model gave about the item that never validated or was refused is recorded; a
    failure that says nothing about the item, such as a timeout, is not (#1539)."""
    person = store.as_actor("alice")
    number = person.seed_issue("Item", body="Body", fields=PLACED)
    person.set_field(require_item(store, number), ItemField.STATUS, "New")

    plan = plan_refine(
        store, repo=REPO, source=git_repo, item_number=number, model=MockLLMClient(fail_with=error)
    )
    apply_refine(store, plan)

    assert (plan.has_writes, _writes_to(store, number)) == (
        recorded,
        [JobWrite("set_mark", number, RefineRecordKey.FAILED_BODY_HASH.value, hash_text("Body"))]
        if recorded
        else [],
    )


def test_refine_raises_its_own_error_naming_each_failed_item() -> None:
    """Verify RoadmapRefineError carries the failed items' numbers and its error code."""
    error = RoadmapRefineError("refine failed", failed_items=[3, 5])
    assert (error.failed_items, error.error_code, error.exit_code) == (
        (3, 5),
        "ROADMAP_REFINE_FAILED",
        1,
    )
