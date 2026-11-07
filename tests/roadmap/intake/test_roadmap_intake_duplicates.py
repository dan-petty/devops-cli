"""How intake treats a candidate that may duplicate an item: it files the candidate and names the
possible original (#1335).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.duplicate_eval import DUPLICATE_CASES
from devops_cli.roadmap.intake.intake import (
    IntakePlan,
    NewCandidate,
    Outcome,
    apply_intake,
    intake_candidate,
    plan_intake,
    render_intake,
)
from devops_cli.roadmap.intake.intake_model import (
    GatewayIntakeModel,
    intake_system_prompt,
)
from devops_cli.roadmap.stores.store import (
    CloseReason,
    GitHubState,
    ItemField,
)
from tests.support.fakes.model import ModelFake
from tests.support.roadmap_intake import (
    DEFAULT_PROPOSAL,
    DONE,
    LATER,
    REPO,
    Embedder,
    FakeModel,
    Roadmap,
    echoing,
    labels_of,
    possible_duplicate_line,
)


def test_a_possible_duplicate_of_a_not_planned_issue_is_placed_and_stays_open(
    roadmap: Roadmap,
) -> None:
    """A model's duplicate verdict closes nothing: intake places the issue, and its reason
    comment names the possible original (#2218)."""
    rejected = roadmap.issue(
        "Bare-metal installers", state=GitHubState.CLOSED, state_reason="not_planned"
    )
    copy = roadmap.issue("Install on bare metal")
    roadmap.run(FakeModel(duplicates={"Install on bare metal": "Bare-metal installers"}))
    (comment,) = roadmap.comments(copy)
    assert (
        roadmap.store.closures(copy),
        roadmap.fields(copy)[0],
        possible_duplicate_line(rejected, "Bare-metal installers") in comment.splitlines(),
    ) == ([], "New", True)


def test_two_candidates_that_duplicate_each_other_make_two_items(roadmap: Roadmap) -> None:
    """Of two candidates in one run that the model judges duplicates, the second is placed too,
    and its reason comment names the first as the possible original (#2218)."""
    first = roadmap.issue("Cache embeddings")
    second = roadmap.issue("Keep embeddings cached")
    roadmap.run(FakeModel(duplicates={"Keep embeddings cached": "Cache embeddings"}))
    (comment,) = roadmap.comments(second)
    assert (
        roadmap.fields(first)[0],
        roadmap.fields(second)[0],
        roadmap.store.closures(second),
        possible_duplicate_line(first, "Cache embeddings") in comment.splitlines(),
    ) == ("New", "New", [], True)


def test_a_duplicate_close_a_person_reopened_is_placed_without_a_duplicate_check(
    roadmap: Roadmap,
) -> None:
    roadmap.finished("Original")
    reopened = roadmap.issue("Not a copy")
    roadmap.person.close_by_hand(reopened, CloseReason.DUPLICATE)
    roadmap.person.reopen_issue(reopened)
    model = FakeModel(duplicates={"Not a copy": "Original"})
    roadmap.run(model)
    assert (
        [request.shortlist for request in model.requests],
        model.embedded,
        roadmap.fields(reopened)[0],
    ) == ([()], [], "New")


@pytest.mark.parametrize(
    ("planned", "older"),
    [
        pytest.param({"milestone": LATER}, False, id="person-placed-milestone"),
        pytest.param({"labels": ("status/blocked",)}, False, id="person-status"),
        pytest.param({}, True, id="older-than-its-original"),
    ],
)
def test_a_possible_duplicate_a_person_planned_or_an_older_one_is_placed_and_stays_open(
    roadmap: Roadmap, planned: dict[str, Any], older: bool
) -> None:
    """A candidate a person planned with a milestone or a Status, or one older than the item
    the model names as its original, is placed and stays open like any other: no verdict closes
    an issue (#2218)."""
    candidate = roadmap.issue("Parent task", **planned) if older else 0
    original = roadmap.finished("Split work")
    candidate = candidate or roadmap.issue("Parent task", **planned)
    roadmap.run(FakeModel(duplicates={"Parent task": "Split work"}))
    (comment,) = roadmap.comments(candidate)
    assert (
        roadmap.store.closures(candidate),
        roadmap.store.item(candidate) is not None,
        possible_duplicate_line(original, "Split work") in comment.splitlines(),
    ) == ([], True, True)


# ── The same change, not a shared theme (#1755) ───────────────────────────────

# The evaluation set's cases that hold a recorded reply: candidates intake folded for a shared
# theme, with the model's answers of that run, and duplicates a person closed, with answers
# written from the person's comment. `devops roadmap eval intake` runs every case live.
JUDGEMENTS: list[dict[str, Any]] = [
    case
    for case in json.loads(DUPLICATE_CASES.read_text(encoding="utf-8"))["cases"]
    if case.get("answer") is not None
]


def _judged(
    roadmap: Roadmap, model_fake: ModelFake, case: dict[str, Any]
) -> tuple[int, IntakePlan, int | None]:
    """Run one case of the evaluation set through intake over the shared model fake: seed its
    item as a finished one, answer with the case's answer for the seeded number, and file the
    candidate. Return the item's number, the plan and the issue intake filed."""
    item = case["item"]
    number = roadmap.finished(item["title"], body=item["body"])
    answer = {k: number if v == item["number"] else v for k, v in case["answer"].items()}
    model_fake.answer(json.dumps(DEFAULT_PROPOSAL | answer))
    model = GatewayIntakeModel(AIConfig(), embedder=Embedder())
    candidate = NewCandidate(title=case["candidate"]["title"], body=case["candidate"]["body"])
    outcome = intake_candidate(roadmap.store, candidate, repo=REPO, model=model, confirm=True)
    return number, outcome.plan, outcome.number


@pytest.mark.parametrize(
    "case", [c for c in JUDGEMENTS if not c["duplicate"]], ids=lambda case: case["name"]
)
def test_a_candidate_that_shares_only_a_theme_with_an_item_is_filed_and_names_it_as_related(
    roadmap: Roadmap, model_fake: ModelFake, case: dict[str, Any]
) -> None:
    """The model's answers of the 2026-10-20 runs name an original and no change both ask
    for: each candidate is filed, and the report and its reason comment name the item."""
    number, plan, filed = _judged(roadmap, model_fake, case)
    (decision,) = plan.decisions
    said = case["answer"]["duplicate_reason"]
    related = f"#{number}, which asks for a different change." + (f" `{said}`" if said else "")
    assert filed is not None
    (comment,) = roadmap.comments(filed)
    assert (
        decision.outcome,
        decision.related,
        f"  - related: {related}" in render_intake(plan, repo=REPO).splitlines(),
        f"- Related: {related}" in comment.splitlines(),
        roadmap.store.closures(filed),
    ) == (Outcome.PLACE, number, True, True, [])


@pytest.mark.parametrize(
    "case", [c for c in JUDGEMENTS if c["duplicate"]], ids=lambda case: case["name"]
)
def test_a_candidate_that_asks_for_the_same_change_is_filed_and_names_the_possible_original(
    roadmap: Roadmap, model_fake: ModelFake, case: dict[str, Any]
) -> None:
    """A duplicate a person closed is filed and placed all the same: the report and the reason
    comment name the possible original and the change that the model says both ask for, and a
    person closes the duplicate (#2218)."""
    number, plan, filed = _judged(roadmap, model_fake, case)
    (decision,) = plan.decisions
    answer = case["answer"]
    reason = (
        f"The model names `{answer['shared_change']}` as the change that both ask for. "
        f"`{answer['duplicate_reason']}`"
    )
    assert filed is not None
    (comment,) = roadmap.comments(filed)
    assert (
        decision.outcome,
        decision.possible_duplicate,
        f"  - possible duplicate: #{number}. {reason}"
        in render_intake(plan, repo=REPO).splitlines(),
        f"- Possible duplicate: #{number}, which may ask for the same change. {reason} A person "
        "closes one of the two if that is so." in comment.splitlines(),
        roadmap.store.closures(filed),
    ) == (Outcome.PLACE, number, True, True, [])


def test_a_related_item_the_model_names_is_reported_and_linked_from_the_reason_comment(
    roadmap: Roadmap,
) -> None:
    umbrella = roadmap.finished("perf(ci): the gate finishes in 2 minutes")
    number = roadmap.issue("perf(tests): the invariant tests share one parse")
    answer = {"related_to": umbrella, "related_reason": "it is the umbrella item."}
    model = FakeModel(proposals={"perf(tests): the invariant tests share one parse": answer})
    plan = roadmap.plan(model)
    apply_intake(roadmap.store, plan)
    related = f"#{umbrella}, which asks for a different change. `it is the umbrella item.`"
    (comment,) = roadmap.comments(number)
    assert (
        plan.decisions[0].outcome,
        f"  - related: {related}" in render_intake(plan, repo=REPO).splitlines(),
        f"- Related: {related}" in comment.splitlines(),
    ) == (Outcome.PLACE, True, True)


def test_a_related_item_off_the_shortlist_is_rejected_with_a_note(roadmap: Roadmap) -> None:
    roadmap.issue("feat: export the board as CSV")
    answer = {"related_to": 740, "related_reason": "both export data."}
    plan = roadmap.plan(FakeModel(proposals={"feat: export the board as CSV": answer}))
    (decision,) = plan.decisions
    assert (decision.outcome, decision.related, decision.notes) == (
        Outcome.PLACE,
        None,
        (
            "the model named #740 as related, which is not one of the nearest items, so it "
            "was rejected.",
        ),
    )


def test_the_intake_prompt_defines_a_duplicate_as_the_same_change(
    snapshot: SnapshotAssertion,
) -> None:
    assert intake_system_prompt() == snapshot


def test_a_new_candidate_and_a_possible_duplicate_are_each_filed(
    opened: Roadmap, fake_model: FakeModel, tmp_path: Path, run_intake: Callable[..., str]
) -> None:
    """A candidate that the model judges a duplicate is filed and placed like a new idea, and
    the report names its possible original (#2218)."""
    original = opened.finished("feat(github): single-entry item intake")
    body = tmp_path / "body.md"
    body.write_text("One entry point turns candidates into items.", encoding="utf-8")
    fake_model.duplicates["feat: item intake again"] = "feat(github): single-entry item intake"
    possible = run_intake(
        "--title", "feat: item intake again", "--body-file", str(body), "--confirm"
    )
    filed = run_intake("--title", "feat: a new idea", "--body-file", str(body), "--confirm")
    numbers = {i.title: i.number for i in opened.store.issues()}
    again, new = numbers["feat: item intake again"], numbers["feat: a new idea"]
    assert (
        f"possible duplicate: #{original}." in possible,
        f"Filed #{again}" in possible,
        f"Filed #{new}" in filed,
        len(opened.store.issues()),
        [opened.fields(number)[0] for number in (again, new)],
        labels_of(opened, new),
    ) == (True, True, True, 3, ["New", "New"], ("source/agent", "type/feature"))


def test_a_duplicate_of_written_as_text_is_read_against_the_shortlist(roadmap: Roadmap) -> None:
    original = roadmap.finished("Cache embeddings")
    copy = roadmap.issue("Keep embeddings cached")
    answer = {"duplicate_of": f"#{original}", "shared_change": "an embedding cache"}
    model = FakeModel(proposals={"Keep embeddings cached": answer})
    model.propose = echoing(model.propose, answer)  # type: ignore[method-assign, assignment]
    (decision,) = roadmap.plan(model).decisions
    assert (decision.outcome, decision.possible_duplicate, decision.subject.number) == (
        Outcome.PLACE,
        original,
        copy,
    )


def test_candidate_matching_only_done_item_is_filed_with_reference_in_body(
    roadmap: Roadmap,
) -> None:
    """A candidate matching only a closed completed item, which is done, is filed as a new
    issue whose body references the done item (#1671)."""
    done = roadmap.issue(
        "feat: tempo trace storage",
        body="Store traces in tempo.",
        state=GitHubState.CLOSED,
        state_reason=CloseReason.COMPLETED,
        milestone=DONE,
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    model = FakeModel(
        duplicates={"fix(k8s): tempo runs under otel namespace": "feat: tempo trace storage"}
    )
    candidate = NewCandidate(
        title="fix(k8s): tempo runs under otel namespace",
        body="Tempo fails to start under restricted pod security.",
    )
    plan = plan_intake(roadmap.store, repo=REPO, model=model, new=candidate)
    (decision,) = plan.decisions
    assert decision.outcome is Outcome.PLACE
    applied = apply_intake(roadmap.store, plan)
    (filed_number,) = applied.filed
    filed_issue = next(i for i in roadmap.store.issues() if i.number == filed_number)
    assert (f"regression of #{done}" in filed_issue.body, "shipped in" in filed_issue.body) == (
        True,
        False,
    )
    assert "Tempo fails to start under restricted pod security." in filed_issue.body


def test_candidate_matching_open_item_is_filed_as_its_possible_duplicate(roadmap: Roadmap) -> None:
    """A candidate that the model matches to an open item is filed, and names that item as its
    possible original (#1671, #2218)."""
    open_item = roadmap.issue(
        "feat: open feature",
        body="Feature in progress.",
        state=GitHubState.OPEN,
        fields={ItemField.PRIORITY: "P2-Medium"},
    )
    model = FakeModel(duplicates={"feat: open feature copy": "feat: open feature"})
    candidate = NewCandidate(
        title="feat: open feature copy",
        body="Duplicate feature.",
    )
    plan = plan_intake(roadmap.store, repo=REPO, model=model, new=candidate)
    (decision,) = plan.decisions
    applied = apply_intake(roadmap.store, plan)
    assert (decision.outcome, decision.possible_duplicate, len(applied.filed)) == (
        Outcome.PLACE,
        open_item,
        1,
    )


def test_candidate_matching_item_closed_as_not_planned_is_filed_as_its_possible_duplicate(
    roadmap: Roadmap,
) -> None:
    """A candidate that the model matches to an item closed as not planned is filed, and names
    that item as its possible original (#1671, #2218)."""
    not_planned = roadmap.issue(
        "feat: rejected proposal",
        body="Rejected idea.",
        state=GitHubState.CLOSED,
        state_reason=CloseReason.NOT_PLANNED,
    )
    model = FakeModel(duplicates={"feat: rejected proposal again": "feat: rejected proposal"})
    candidate = NewCandidate(
        title="feat: rejected proposal again",
        body="Same idea again.",
    )
    plan = plan_intake(roadmap.store, repo=REPO, model=model, new=candidate)
    (decision,) = plan.decisions
    applied = apply_intake(roadmap.store, plan)
    assert (decision.outcome, decision.possible_duplicate, len(applied.filed)) == (
        Outcome.PLACE,
        not_planned,
        1,
    )
