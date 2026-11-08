"""A placeholder reply of a model moves no item (#3478).

The refine reply uses one text type, `ReplyText`, for each free-text field. A reply with a
placeholder goes back to the model once. A second one is a placeholder failure of the item: it
writes nothing, asks no person, sets no Status and does not fail the round.

The roadmap is the in-memory store, the model edge is the fake with the real reply check, and git
runs on a temporary repository.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from pydantic import ValidationError

from devops_cli.ai.client.models import StructuredOutputValidationError
from devops_cli.exceptions import RoadmapRefineError
from devops_cli.roadmap import run
from devops_cli.roadmap.failure import FailureClass
from devops_cli.roadmap.pull_form import PLACEHOLDER_ERROR_TYPE
from devops_cli.roadmap.refine.refine import (
    RefineFailure,
    RefinementProposal,
    RefinePlan,
    RefineWriter,
    apply_refine,
    plan_refine,
    raise_for_failed_items,
)
from devops_cli.roadmap.run import FailureLedger, _count_failure, _run_refine_adapter
from devops_cli.roadmap.stores.store import ItemField, RefineRecordKey
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

if TYPE_CHECKING:
    from tests.support.fakes.model import ModelFake

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
FILLER_REFUSAL = "Not yet: I need to inspect the repository first."
CRITERION = {
    "name": "A design",
    "requirement": "The item SHALL have a design.",
    "scenario": "A person reads the item",
    "when": "a person reads the item",
    "then": "the design is in the item",
}
VALID = {
    "problem_statement": "The item needs a design.",
    "existing_tool": "Pydantic covers the schema check.",
    "acceptance_criteria": [CRITERION],
}
STUB = {"problem_statement": "x", "existing_tool": "x"}
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)


def _git(cwd: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)
    return done.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """A checkout of `REPO` whose one commit holds `src/sample.py`."""
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.email", "ci@example.com"), ("user.name", "CI")):
        _git(repo, "config", key, value)
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "remote", "add", "origin", f"https://example.com/{REPO}.git")
    (repo / "src" / "sample.py").write_text("def hello():\n    return 'hi'\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    """A private roadmap with one New P1 backlog item, number 1."""
    roadmap = InMemoryRoadmapStore(repo=REPO, is_private=True)
    roadmap.seed_issue(
        "feat(roadmap): a report",
        body="Make a report.",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    return roadmap


def _plan(store: InMemoryRoadmapStore, git_repo: Path, fake: ModelFake) -> RefinePlan:
    return plan_refine(
        store, repo=REPO, source=git_repo, item_number=1, model=fake.checking_replies()
    )


def _violations(fields: dict[str, Any]) -> list[tuple[str, str]]:
    with pytest.raises(ValidationError) as raised:
        RefinementProposal.model_validate(fields)
    return [(str(e["loc"][0]), e["type"]) for e in raised.value.errors()]


# ── The reply ─────────────────────────────────────────────────────────────────


def test_x_in_both_required_keys_with_empty_criteria_fails_the_schema() -> None:
    assert _violations(STUB | {"acceptance_criteria": []}) == [
        ("problem_statement", PLACEHOLDER_ERROR_TYPE),
        ("existing_tool", PLACEHOLDER_ERROR_TYPE),
    ]


@pytest.mark.parametrize("text", ["x", "y", "none", "probe", "__PROBE__", FILLER_REFUSAL])
def test_a_placeholder_in_a_required_key_fails_the_schema(text: str) -> None:
    assert _violations(VALID | {"problem_statement": text}) == [
        ("problem_statement", PLACEHOLDER_ERROR_TYPE)
    ]
    assert _violations(VALID | {"existing_tool": text}) == [
        ("existing_tool", PLACEHOLDER_ERROR_TYPE)
    ]


@pytest.mark.parametrize(
    ("reply", "field"),
    [
        (VALID | {"acceptance_criteria": [CRITERION | {"scenario": "x"}]}, "acceptance_criteria"),
        (
            VALID
            | {"key_questions": [{"question": "Which tool?", "answer": "none", "kind": "fact"}]},
            "key_questions",
        ),
        (
            VALID
            | {
                "key_questions": [
                    {
                        "question": "Which tool?",
                        "answer": "A real answer.",
                        "kind": "decision",
                        "options": [{"option": "probe", "reason": "A real reason."}],
                    }
                ]
            },
            "key_questions",
        ),
        (VALID | {"deferred": [{"title": "feat(x): part", "body": "placeholder"}]}, "deferred"),
        (VALID | {"split_offs": ["x"]}, "split_offs"),
    ],
)
def test_a_placeholder_in_any_free_text_field_fails_the_schema(
    reply: dict[str, Any], field: str
) -> None:
    assert _violations(reply) == [(field, PLACEHOLDER_ERROR_TYPE)]


def test_a_real_reply_passes_and_none_is_a_valid_suspected_block() -> None:
    reply = RefinementProposal.model_validate(VALID | {"suspected_block": "none"})

    assert (reply.problem_statement, reply.suspected_block) == ("The item needs a design.", "none")


# ── The failure ───────────────────────────────────────────────────────────────


def test_a_placeholder_reply_goes_back_once_and_the_second_reply_is_used(
    store: InMemoryRoadmapStore, git_repo: Path, model_fake: ModelFake
) -> None:
    model_fake.answer(json.dumps(VALID | STUB), json.dumps(VALID))

    plan = _plan(store, git_repo, model_fake)

    (refined,) = plan.refined_items
    assert (refined.proposal.problem_statement, plan.failed_items, len(model_fake.sent)) == (
        "The item needs a design.",
        [],
        2,
    )
    assert "placeholder_text" in model_fake.sent[1].messages[-1].content


def test_two_placeholder_replies_write_nothing_and_ask_no_person(
    store: InMemoryRoadmapStore, git_repo: Path, model_fake: ModelFake
) -> None:
    model_fake.answer(json.dumps(VALID | STUB))
    before = store.item(1)

    plan = _plan(store, git_repo, model_fake)
    applied = apply_refine(store, plan)

    (failure,) = plan.failed_items
    assert (failure.item.number, failure.placeholder, failure.item_caused) == (1, True, False)
    assert (plan.refined_items, plan.has_writes, len(model_fake.sent)) == ([], False, 2)
    assert (applied.refined_count, store.job_writes(), store.comments_on(1)) == (0, [], [])
    assert (store.item(1), store.read_issue_body(1)) == (before, "Make a report.")


def test_a_placeholder_with_another_violation_is_a_normal_failure_of_the_item(
    store: InMemoryRoadmapStore, git_repo: Path, model_fake: ModelFake
) -> None:
    model_fake.answer(json.dumps(VALID | STUB | {"acceptance_criteria": ["a string"]}))

    plan = _plan(store, git_repo, model_fake)

    (failure,) = plan.failed_items
    assert (failure.placeholder, failure.item_caused) == (False, True)


def test_a_placeholder_failure_leaves_no_refine_mark_on_a_second_round(
    store: InMemoryRoadmapStore, git_repo: Path, model_fake: ModelFake
) -> None:
    model_fake.answer(json.dumps(VALID | STUB))

    for _ in range(3):
        apply_refine(store, _plan(store, git_repo, model_fake))

    item = store.item(1)
    assert item is not None
    assert {key: item.job_record.get(key) for key in RefineRecordKey} == dict.fromkeys(
        RefineRecordKey
    )
    assert (item.status, store.job_writes()) == ("New", [])


def _failure(item: Any, *, placeholder: bool, caused: bool = False) -> RefineFailure:
    return RefineFailure(
        item=item,
        error="StructuredOutputValidationError" if placeholder else "AIClientError",
        failure_class=FailureClass.PARSER if placeholder else FailureClass.PROVIDER,
        violations=1,
        item_caused=caused,
        placeholder=placeholder,
    )


def test_the_round_fails_for_a_normal_failure_and_names_only_that_item(
    store: InMemoryRoadmapStore,
) -> None:
    store.seed_issue("feat(x): two", fields={ItemField.PRIORITY: "P2-Medium"})
    one, two = store.item(1), store.item(2)
    plan = RefinePlan(
        repo=REPO,
        failed_items=[_failure(one, placeholder=True), _failure(two, placeholder=False)],
    )

    with pytest.raises(RoadmapRefineError) as raised:
        raise_for_failed_items(plan)

    assert list(raised.value.failed_items) == [2]


def test_a_round_with_only_a_placeholder_failure_raises_nothing(
    store: InMemoryRoadmapStore,
) -> None:
    plan = RefinePlan(repo=REPO, failed_items=[_failure(store.item(1), placeholder=True)])

    assert raise_for_failed_items(plan) is None


def test_a_placeholder_failure_three_rounds_in_a_row_does_not_suspend_the_refine_row(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    model_fake: ModelFake,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model_fake.answer(json.dumps(VALID | STUB))
    placeholder = _plan(store, git_repo, model_fake)
    timeout = RefinePlan(repo=REPO, failed_items=[_failure(store.item(1), placeholder=False)])

    def rounds(plan: RefinePlan) -> FailureLedger:
        def planned(*_: Any, writer: RefineWriter, **__: Any) -> RefinePlan:
            for failure in plan.failed_items:
                writer.settle(failure)
            return plan

        monkeypatch.setattr(run, "plan_refine", planned)
        ledger = FailureLedger()
        for _ in range(ledger.limit):
            try:
                _run_refine_adapter(store, repo=REPO, clone_path=git_repo)
            except RoadmapRefineError as exc:
                _count_failure(ledger, REPO, "refine", "input", exc)
            else:
                ledger.succeeded(REPO, "refine")
        return ledger

    assert not rounds(placeholder).suspended(REPO, "refine", "input", NOW)
    assert rounds(timeout).suspended(REPO, "refine", "input", NOW)


def test_the_error_of_a_reply_that_held_only_placeholders_names_the_error_type() -> None:
    from devops_cli.ai.client.structured import _validation_failure
    from devops_cli.ai.schema_reflection import extract_schema_reflection

    with pytest.raises(ValidationError) as raised:
        RefinementProposal.model_validate(STUB)
    report = extract_schema_reflection(raised.value, max_errors=raised.value.error_count())

    error = _validation_failure("model", 2, report)

    assert isinstance(error, StructuredOutputValidationError)
    assert error.error_types == (PLACEHOLDER_ERROR_TYPE,)
