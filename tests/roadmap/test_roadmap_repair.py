"""The repair pass (#3478): it lists the items that a filler return of the stage job or a stub
refine block stalled, and with a confirm it sets them back. It leaves each item that a person set.

The roadmap is in memory. The texts of the stage comments are the ones that the job wrote before
the return path went away (#3104, #3193, #3109, #3255).
"""

from __future__ import annotations

from typing import Any

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_END_MARKER,
    CONST_ROADMAP_REFINE_START_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.exceptions import GitHubOperationError, GitHubRateLimitError
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.body_hash import extract_section_and_outside, hash_text
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.refine import (
    NextStep,
    RefinementProposal,
    render_proposal_section,
    step_comment,
)
from devops_cli.roadmap.repair import (
    RepairPlan,
    StallKind,
    apply_repair,
    plan_repair,
    render_repair_plan,
)
from devops_cli.roadmap.store import (
    CloseReason,
    ImplementRecordKey,
    Item,
    ItemField,
    RefineRecordKey,
)
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

SHA = "0123456789abcdef0123456789abcdef01234567"
BODY = "Make a report."
_ASKED = "Which module holds the readiness checks? (a person decides)"
RETURN = (
    f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nThe stage job returned the item to New. The premise "
    "of the issue does not hold at the staging commit, so the job planned no change and opened "
    "no pull request.\n\nEvidence:\n\n{evidence}"
)
FILLER = (
    "placeholder",
    "x",
    "none",
    "probe",
    "__PROBE__",
    "Not yet: I need to inspect the repository first.",
)
# The evidence of #3255: a real sentence. The pass lists no return that gives one.
SENTENCE = (
    "The premise is not false: `form_problems` is defined at src/devops_cli/roadmap/stage_form.py:85 "
    "and `title_problems` is imported by a test, so both gates exist and can be tightened."
)


class _Store(InMemoryRoadmapStore):
    """The in-memory roadmap that refuses the write of a Status for the items in `refuse`, and
    answers every write with a rate limit when `limited` is set."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.refuse: set[int] = set()
        self.limited = False

    def set_field(self, item: Item, field: ItemField, value: str | None, **kwargs: Any) -> None:
        if self.limited:
            raise GitHubRateLimitError("Rate limit reached.")
        if item.number in self.refuse:
            raise GitHubOperationError("GitHub answered 502.", operation="roadmap.set_field")
        super().set_field(item, field, value, **kwargs)


@pytest.fixture
def store() -> _Store:
    return _Store(repo=STAGE_REPO)


def _item(store: InMemoryRoadmapStore, number: int) -> Item:
    item = store.item(number)
    assert item is not None
    return item


def _ready(store: InMemoryRoadmapStore, title: str = "fix(cli): a defect") -> int:
    """An item that refine set Ready, as the stage job takes it."""
    number = store.seed_issue(title, body=BODY, fields={ItemField.PRIORITY: "P2-Medium"})
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        "Ready",
        marks={RefineRecordKey.NEXT_STEP: NextStep.READY.value},
    )
    return number


def _returned(store: InMemoryRoadmapStore, evidence: str) -> int:
    """An item that the stage job returned to New: the comment first, then the Status."""
    number = _ready(store)
    store.comment(number, RETURN.format(evidence=evidence))
    store.set_field(_item(store, number), ItemField.STATUS, "New")
    return number


def _stub(store: InMemoryRoadmapStore, problem: str = "x", tool: str = "x") -> int:
    """An item that a stub refine reply blocked: a section with the stub text, the record of its
    hashes and the next step `person`, and the comment that asks a person."""
    number = store.seed_issue(
        "feat(roadmap): a report",
        body=BODY,
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    proposal = RefinementProposal.model_construct(problem_statement=problem, existing_tool=tool)
    section = render_proposal_section(proposal, [], SHA, set())
    body = f"{BODY}\n\n{section}"
    store.write_issue_body(number, body)
    outside, inside = extract_section_and_outside(body)
    assert inside is not None
    store.set_field(
        _item(store, number),
        ItemField.STATUS,
        "New",
        marks={
            RefineRecordKey.BODY_HASH: hash_text(outside),
            RefineRecordKey.SECTION_HASH: hash_text(inside),
            RefineRecordKey.NEXT_STEP: NextStep.PERSON.value,
            RefineRecordKey.TRIES: "2",
            RefineRecordKey.FAILED_CHECK: "missing_source",
            RefineRecordKey.FAILURE: "Searched: nothing",
        },
    )
    asked = step_comment(_item(store, number), NextStep.PERSON, [_ASKED], SHA)
    store.comment(number, asked)
    return number


def _listed(plan: RepairPlan) -> list[tuple[int, StallKind]]:
    return [(stalled.item.number, stalled.kind) for stalled in plan.stalled]


# ── What the pass lists ───────────────────────────────────────────────────────


@pytest.mark.parametrize("evidence", FILLER)
def test_a_filler_return_is_listed(store: InMemoryRoadmapStore, evidence: str) -> None:
    number = _returned(store, evidence)

    plan = plan_repair(store, repo=STAGE_REPO)

    assert _listed(plan) == [(number, StallKind.FILLER_RETURN)]
    assert f"#{number}" in render_repair_plan(plan)


@pytest.mark.parametrize(
    ("problem", "tool"), [("x", "x"), ("x", "A real answer."), ("A real one.", "y")]
)
def test_a_stub_refine_block_is_listed(
    store: InMemoryRoadmapStore, problem: str, tool: str
) -> None:
    number = _stub(store, problem, tool)

    assert _listed(plan_repair(store, repo=STAGE_REPO)) == [(number, StallKind.STUB_REFINE)]


def test_a_dry_listing_writes_nothing(store: InMemoryRoadmapStore) -> None:
    _returned(store, "x")
    _stub(store)
    writes = len(store.job_writes())

    plan_repair(store, repo=STAGE_REPO)

    assert len(store.job_writes()) == writes


def test_nothing_is_stalled_in_a_clean_roadmap(store: InMemoryRoadmapStore) -> None:
    _ready(store)
    store.seed_issue("feat(x): new", fields={ItemField.PRIORITY: "P3-Low", ItemField.STATUS: "New"})

    plan = plan_repair(store, repo=STAGE_REPO)

    assert plan.stalled == ()
    assert MESSAGES.roadmap.repair_nothing in render_repair_plan(plan)


# ── What the pass leaves ──────────────────────────────────────────────────────


def test_a_return_that_gives_evidence_is_left(store: InMemoryRoadmapStore) -> None:
    _returned(store, SENTENCE)

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_stub_block_with_real_texts_is_left(store: InMemoryRoadmapStore) -> None:
    _stub(store, "The item needs a design.", "Pydantic covers the schema check.")

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_status_that_a_person_set_is_left(store: InMemoryRoadmapStore) -> None:
    number = store.seed_issue(
        "fix(cli): a defect",
        body=BODY,
        fields={ItemField.PRIORITY: "P2-Medium", ItemField.STATUS: "New"},
    )
    store.comment(number, RETURN.format(evidence="x"))

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_status_that_a_person_changed_after_the_job_is_left(store: _Store) -> None:
    number = _ready(store)
    store.comment(number, RETURN.format(evidence="x"))
    store.as_actor("alice").set_field(_item(store, number), ItemField.STATUS, "New")

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_reply_after_the_return_is_left(store: InMemoryRoadmapStore) -> None:
    number = _returned(store, "x")
    store.seed_comment(number, "I looked at this one.", author_association="OWNER")

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_reply_after_the_refine_question_is_left(store: InMemoryRoadmapStore) -> None:
    number = _stub(store)
    store.seed_comment(number, "The problem is the report.", author_association="OWNER")

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


@pytest.mark.parametrize("owner", ["Human", "Agent"])
def test_an_item_that_a_person_or_an_agent_owns_is_left(
    store: InMemoryRoadmapStore, owner: str
) -> None:
    number = _returned(store, "x")
    store.set_field(_item(store, number), ItemField.OWNER, owner)

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_an_item_that_a_runner_job_holds_is_left(store: InMemoryRoadmapStore) -> None:
    number = _returned(store, "x")
    store.set_marks(_item(store, number), {ImplementRecordKey.JOB: "devops-cli-runner-1"})

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_closed_item_is_left(store: InMemoryRoadmapStore) -> None:
    number = _returned(store, "x")
    store.close(number, CloseReason.NOT_PLANNED)

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_section_that_a_person_edited_is_left(store: InMemoryRoadmapStore) -> None:
    number = _stub(store)
    edited = store.read_issue_body(number).replace("Problem statement\nx", "Problem statement\nx!")
    store.write_issue_body(number, edited)

    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


# ── What a confirm writes ─────────────────────────────────────────────────────


def test_a_confirm_sets_a_returned_item_back_to_ready(store: InMemoryRoadmapStore) -> None:
    number = _returned(store, "Not yet: I need to inspect the repository first.")

    done = apply_repair(store, plan_repair(store, repo=STAGE_REPO))

    item = _item(store, number)
    assert (done.reset, done.failed) == ((number,), ())
    assert (item.status, item.job_record.get(ItemField.STATUS)) == ("Ready", "Ready")
    assert item.job_record.get(RefineRecordKey.NEXT_STEP) == NextStep.READY.value
    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_confirm_strips_the_stub_section_and_clears_the_refine_block(
    store: InMemoryRoadmapStore,
) -> None:
    number = _stub(store)
    other = store.seed_issue("feat(x): two", body="Two.", fields={ItemField.PRIORITY: "P3-Low"})

    done = apply_repair(store, plan_repair(store, repo=STAGE_REPO))

    item = _item(store, number)
    body = store.read_issue_body(number)
    assert done.reset == (number,)
    assert body == BODY
    assert CONST_ROADMAP_REFINE_START_MARKER not in body
    assert CONST_ROADMAP_REFINE_END_MARKER not in body
    assert {key: item.job_record.get(key) for key in RefineRecordKey} == dict.fromkeys(
        RefineRecordKey
    )
    assert (item.status, store.read_issue_body(other)) == ("New", "Two.")
    assert plan_repair(store, repo=STAGE_REPO).stalled == ()


def test_a_confirm_keeps_the_text_outside_the_section_and_the_alternatives_block(
    store: InMemoryRoadmapStore,
) -> None:
    number = _stub(store)
    body = store.read_issue_body(number)
    store.write_issue_body(number, f"Intro by a person.\n\n{body}")
    outside, inside = extract_section_and_outside(store.read_issue_body(number))
    assert inside is not None
    store.set_marks(
        _item(store, number),
        {RefineRecordKey.BODY_HASH: hash_text(outside)},
    )

    apply_repair(store, plan_repair(store, repo=STAGE_REPO))

    assert store.read_issue_body(number) == f"Intro by a person.\n\n{BODY}"


def test_a_confirm_writes_nothing_for_an_item_that_changed_since_the_listing(
    store: InMemoryRoadmapStore,
) -> None:
    number = _returned(store, "x")
    plan = plan_repair(store, repo=STAGE_REPO)
    store.set_field(_item(store, number), ItemField.OWNER, "Human")
    writes = len(store.job_writes())

    done = apply_repair(store, plan)

    assert (done.reset, done.failed, len(store.job_writes()), _item(store, number).status) == (
        (),
        (),
        writes,
        "New",
    )


def test_a_failed_item_does_not_stop_the_others(store: _Store) -> None:
    first, second = _returned(store, "x"), _returned(store, "probe")
    store.refuse.add(first)

    done = apply_repair(store, plan_repair(store, repo=STAGE_REPO))

    assert (done.reset, [failure.number for failure in done.failed]) == ((second,), [first])
    assert done.failed[0].error == "GitHubOperationError"


def test_a_rate_limit_stops_the_pass(store: _Store) -> None:
    _returned(store, "x")
    plan = plan_repair(store, repo=STAGE_REPO)
    store.limited = True

    with pytest.raises(GitHubRateLimitError) as raised:
        apply_repair(store, plan)

    assert raised.value.error_code == "GITHUB_RATE_LIMIT_UNKNOWN"
