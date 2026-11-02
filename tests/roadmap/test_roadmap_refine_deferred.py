"""Tests for the deferred parts of refine (#2423): a part of an item that cannot be built as
written, or that waits on a person, moves to a new issue through intake, and the rest of the item
reaches Ready.

The roadmap is the in-memory store. The proposal step and intake's two model calls are answered
by test doubles, and git runs on a temporary repository.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.roadmap.intake_model import ModelProposal, ProposalRequest, UnusableProposalError
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.refine import (
    AcceptanceCriterion,
    DeferredPart,
    NextStep,
    QuestionAnswer,
    RefinementProposal,
    apply_refine,
    plan_refine,
)
from devops_cli.roadmap.store import IssueRecord, ItemField, RefineRecordKey

pytestmark = pytest.mark.usefixtures("keyring_store")

REPO = "example/roadmap"
LABELS_YML = Path(".github/labels.yml").read_text(encoding="utf-8")
_CRITERION = AcceptanceCriterion(
    name="A design",
    requirement="The item SHALL have a design.",
    scenario="A person reads the item",
    when="a person reads the item",
    then="the design is in the item",
)
_STORAGE = DeferredPart(
    title="feat(roadmap): decide the storage",
    body="The storage needs a decision of the owner. Criterion: the storage is named.",
)
_EXPORT = DeferredPart(
    title="feat(roadmap): export the report",
    body="The export waits on an upstream release. Ping @someone when it ships.",
)
_PROPOSAL = RefinementProposal(
    problem_statement="The item needs a design.",
    acceptance_criteria=[_CRITERION],
    existing_tool="No open tool covers the need.",
    deferred=[_STORAGE, _EXPORT],
)
_PROPOSAL_FIELDS: dict[str, Any] = {
    "type": "type/feature",
    "type_reason": "it adds a capability.",
    "priority": "P2-Medium",
    "priority_reason": "useful, not urgent.",
    "value": "Medium",
    "value_reason": "it helps maintainers.",
    "effort": "Low",
    "effort_reason": "one module.",
}


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


class _Store(InMemoryRoadmapStore):
    """The in-memory roadmap, keeping the order of the issues it creates and the bodies it
    writes, and refusing the creation of an issue whose number is in `refuse_creation`."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.order: list[str] = []
        self.refuse_creation: set[int] = set()
        self.created = 0

    def create_issue(self, title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        self.created += 1
        if self.created in self.refuse_creation:
            raise GitHubOperationError("GitHub answered 502.", operation="roadmap.create_issue")
        self.order.append(f"create {title}")
        return super().create_issue(title, body, labels=labels)

    def write_issue_body(self, number: int, body: str) -> None:
        self.order.append(f"body #{number}")
        super().write_issue_body(number, body)


@pytest.fixture
def store() -> _Store:
    """A private roadmap with `.github/labels.yml` and one New P1 backlog item, number 1."""
    roadmap = _Store(repo=REPO, is_private=True)
    roadmap.seed_file(".github/labels.yml", LABELS_YML)
    roadmap.seed_issue(
        "feat(roadmap): a report",
        body="Make a report.",
        fields={ItemField.STATUS: "New", ItemField.PRIORITY: "P1-High"},
    )
    return roadmap


class _Proposer:
    """The proposal step's client: it answers each request with `proposal`, and keeps each
    request document."""

    def __init__(self, proposal: RefinementProposal) -> None:
        self.proposal = proposal
        self.prompts: list[str] = []

    def chat_structured(self, system: str, prompt: str, schema: type[Any]) -> Any:
        self.prompts.append(prompt)
        return self.proposal


class _Intake:
    """Intake's two model calls: one vector for each text, and the same proposal for each
    candidate, or no usable proposal for a title in `unusable`."""

    def __init__(self, unusable: Sequence[str] = ()) -> None:
        self.unusable = set(unusable)
        self.titles: list[str] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    def propose(self, request: ProposalRequest) -> ModelProposal:
        self.titles.append(request.title)
        if request.title in self.unusable:
            raise UnusableProposalError("no usable proposal")
        return ModelProposal.model_validate(_PROPOSAL_FIELDS)


def _plan(
    store: InMemoryRoadmapStore,
    git_repo: Path,
    proposal: RefinementProposal = _PROPOSAL,
    intake: _Intake | None = None,
) -> Any:
    return plan_refine(
        store,
        repo=REPO,
        source=git_repo,
        item_number=1,
        model=_Proposer(proposal),
        intake_model=intake or _Intake(),
    )


def _record(store: InMemoryRoadmapStore, number: int, key: RefineRecordKey) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.job_record.get(key)


def _status(store: InMemoryRoadmapStore, number: int) -> str | None:
    item = store.item(number)
    assert item is not None
    return item.status


# ── The reply ─────────────────────────────────────────────────────────────────


def test_deferred_a_reply_with_two_parts_validates_in_order() -> None:
    reply = RefinementProposal.model_validate(
        {
            "problem_statement": "p",
            "existing_tool": "t",
            "deferred": [_STORAGE.model_dump(), _EXPORT.model_dump()],
        }
    )

    assert (
        [part.title for part in reply.deferred],
        RefinementProposal(problem_statement="p", existing_tool="t").deferred,
    ) == ([_STORAGE.title, _EXPORT.title], [])


@pytest.mark.parametrize(
    ("parts", "error_type"),
    [
        pytest.param([_STORAGE.model_dump()] * 4, "too_long", id="four-parts"),
        pytest.param([{"title": "", "body": "b"}], "string_too_short", id="empty-title"),
        pytest.param([{"title": "t", "body": ""}], "string_too_short", id="empty-body"),
        pytest.param([{"title": "t", "body": "b", "extra": 1}], "extra_forbidden", id="other-key"),
    ],
)
def test_deferred_a_reply_with_a_bad_part_fails_validation(
    parts: list[dict[str, Any]], error_type: str
) -> None:
    with pytest.raises(ValidationError) as raised:
        RefinementProposal.model_validate(
            {"problem_statement": "p", "existing_tool": "t", "deferred": parts}
        )

    assert [error["type"] for error in raised.value.errors()] == [error_type]


# ── The plan ──────────────────────────────────────────────────────────────────


def test_deferred_a_complete_proposal_plans_one_new_issue_for_each_part(
    store: _Store, git_repo: Path
) -> None:
    intake = _Intake()

    plan = _plan(store, git_repo, intake=intake)

    (refined,) = plan.refined_items
    subjects = [deferral.plan.decisions[0].subject for deferral in refined.deferred]
    assert (
        refined.is_ready,
        refined.next_step,
        [subject.title for subject in subjects],
        [subject.body.splitlines()[0] for subject in subjects],
        "`@someone`" in subjects[1].body,
        intake.titles,
        store.order,
    ) == (
        True,
        NextStep.READY,
        [_STORAGE.title, _EXPORT.title],
        ["Split from #1.", "Split from #1."],
        True,
        [_STORAGE.title, _EXPORT.title],
        [],
    )


def test_deferred_an_item_with_an_open_question_plans_no_new_issue(
    store: _Store, git_repo: Path
) -> None:
    open_question = QuestionAnswer(question="Which store?", answer="Ask the owner.", kind="person")
    proposal = _PROPOSAL.model_copy(update={"key_questions": [open_question]})
    intake = _Intake()

    plan = _plan(store, git_repo, proposal, intake)

    (refined,) = plan.refined_items
    assert (refined.is_ready, refined.next_step, refined.deferred, intake.titles) == (
        False,
        NextStep.PERSON,
        (),
        [],
    )


def test_deferred_a_part_that_intake_cannot_place_keeps_the_item_waiting_on_a_person(
    store: _Store, git_repo: Path
) -> None:
    plan = _plan(store, git_repo, intake=_Intake(unusable=[_EXPORT.title]))
    apply_refine(store, plan)

    (refined,) = plan.refined_items
    assert (
        refined.is_ready,
        refined.next_step,
        refined.deferred,
        any(_EXPORT.title in detail for detail in refined.step_details),
        store.order,
        _status(store, 1),
    ) == (False, NextStep.PERSON, (), True, ["body #1"], "New")


def test_deferred_a_part_whose_text_looks_like_a_secret_keeps_the_item_waiting(
    store: _Store, git_repo: Path
) -> None:
    secret = DeferredPart(
        title="feat(roadmap): rotate the key",
        body="The key ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8 must rotate.",
    )
    proposal = _PROPOSAL.model_copy(update={"deferred": [secret]})

    plan = _plan(store, git_repo, proposal)

    (refined,) = plan.refined_items
    assert (refined.is_ready, refined.next_step, refined.deferred) == (False, NextStep.PERSON, ())
    assert any(secret.title in detail for detail in refined.step_details)


def test_deferred_a_proposal_that_is_too_big_still_waits_for_a_split(
    store: _Store, git_repo: Path
) -> None:
    proposal = _PROPOSAL.model_copy(update={"fits_one_pr": False, "split_offs": ["a", "b"]})
    intake = _Intake()

    plan = _plan(store, git_repo, proposal, intake)

    (refined,) = plan.refined_items
    assert (refined.next_step, refined.is_ready, intake.titles) == (NextStep.SPLIT, False, [])


def test_deferred_a_proposal_with_no_part_makes_no_intake_call(
    store: _Store, git_repo: Path
) -> None:
    intake = _Intake()

    plan = _plan(store, git_repo, _PROPOSAL.model_copy(update={"deferred": []}), intake)

    (refined,) = plan.refined_items
    assert (refined.is_ready, refined.deferred, intake.titles) == (True, (), [])


def test_deferred_a_plan_that_is_not_applied_files_no_issue(store: _Store, git_repo: Path) -> None:
    issues_before = len(store.issues())

    plan = _plan(store, git_repo)

    assert (len(plan.refined_items[0].deferred), len(store.issues()), store.order) == (
        2,
        issues_before,
        [],
    )


# ── The writes ────────────────────────────────────────────────────────────────


def test_deferred_apply_files_the_parts_first_then_sets_the_item_ready_and_links_them(
    store: _Store, git_repo: Path
) -> None:
    plan = _plan(store, git_repo)

    applied = apply_refine(store, plan)

    new = [issue for issue in store.issues() if issue.number != 1]
    numbers = [issue.number for issue in new]
    refine_comments = [c.body for c in store.comments_on(1)]
    item = store.item(1)
    assert item is not None
    assert (
        applied.readied_count,
        _status(store, 1),
        [issue.title for issue in new],
        [issue.body.splitlines()[0] for issue in new],
        store.order,
        _record(store, 1, RefineRecordKey.DEFERRED),
        len(refine_comments),
        f"Moved to new items: #{numbers[0]}, #{numbers[1]}." in refine_comments[0],
        item.sub_issues,
        [issue.parent for issue in new],
    ) == (
        1,
        "Ready",
        [_STORAGE.title, _EXPORT.title],
        ["Split from #1.", "Split from #1."],
        [f"create {_STORAGE.title}", f"create {_EXPORT.title}", "body #1"],
        f"{numbers[0]},{numbers[1]}",
        1,
        True,
        0,
        [None, None],
    )


def test_deferred_a_failed_second_filing_records_the_first_and_leaves_the_item(
    store: _Store, git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store.refuse_creation = {2}
    plan = _plan(store, git_repo)

    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.refine"):
        applied = apply_refine(store, plan)

    (first,) = [issue for issue in store.issues() if issue.number != 1]
    assert (
        applied.readied_count,
        _record(store, 1, RefineRecordKey.DEFERRED),
        store.order,
        store.read_issue_body(1),
        _status(store, 1),
        store.comments_on(1),
        any("deferred parts of #1" in r.getMessage() for r in caplog.records),
    ) == (0, str(first.number), [f"create {_STORAGE.title}"], "Make a report.", "New", [], True)


def test_deferred_a_later_round_files_only_the_parts_that_no_round_filed(
    store: _Store, git_repo: Path
) -> None:
    store.refuse_creation = {2}
    apply_refine(store, _plan(store, git_repo))
    (first,) = [issue for issue in store.issues() if issue.number != 1]
    store.refuse_creation = set()
    proposer_intake = _Intake()
    proposer = _Proposer(_PROPOSAL)

    plan = plan_refine(
        store,
        repo=REPO,
        source=git_repo,
        item_number=1,
        model=proposer,
        intake_model=proposer_intake,
    )
    apply_refine(store, plan)

    second = [issue for issue in store.issues() if issue.number not in {1, first.number}]
    assert (
        '"deferred_issues": [\n  {\n   "number": ' + str(first.number) in proposer.prompts[0],
        proposer_intake.titles,
        [issue.title for issue in second],
        _record(store, 1, RefineRecordKey.DEFERRED),
        _status(store, 1),
    ) == (
        True,
        [_EXPORT.title],
        [_EXPORT.title],
        f"{first.number},{second[0].number}",
        "Ready",
    )
