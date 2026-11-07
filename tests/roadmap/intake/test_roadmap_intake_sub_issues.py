"""A candidate filed from a source issue: its link as a sub-issue, and its parts, which are never
duplicates of their source (#1335).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from devops_cli.config.settings import AIConfig
from devops_cli.roadmap.intake.intake import (
    NewCandidate,
    Outcome,
    intake_candidate,
    plan_intake,
    render_intake,
)
from devops_cli.roadmap.intake.intake_model import (
    GatewayIntakeModel,
)
from tests.support.fakes.model import ModelFake
from tests.support.roadmap_intake import (
    DEFAULT_PROPOSAL,
    FINISHED,
    REGRESSION,
    REPO,
    Embedder,
    FakeModel,
    Roadmap,
    intake_on_github,
    on_github,
)

# ── A part and the issue it is split from (#1985) ─────────────────────────────

# Step B of #1113, which intake judged a duplicate of #1113 on 2026-10-23, and #1113 with
# step C, one of its four sub-issues.
PARENT_TITLE = (
    "fix(valkey): one validated URL names every Valkey endpoint, valkey-py dials an address "
    "that one check vetted, and the unused cache layer goes"
)


PARENT_BODY = (
    "This issue tracks the steps of the plan. One pull request closes each child issue. Step B: "
    "one validated valkey:// or valkeys:// URL names every Valkey endpoint."
)


STEP_C = (
    "fix(valkey): the Valkey client resolves a name once, vets every answer and dials the "
    "vetted address"
)


STEP_B = NewCandidate(
    title="fix(valkey): valkey.url keeps its scheme, so a valkeys url dials tls with host name checks",
    body="Step B of the plan: one validated valkey:// or valkeys:// URL names every Valkey endpoint.",
)


# The worst answer for a part: the model names its parent with a change both ask for.
FOLD_INTO_PARENT = {
    "shared_change": "one validated URL names every Valkey endpoint",
    "duplicate_reason": "This candidate is part of the larger issue, which tracks the steps.",
}


def _link(number: int) -> str:
    """The link GitHub gives issue `number` of the repository."""
    return f"https://github.com/{REPO}/issues/{number}"


def _split(
    roadmap: Roadmap, model_fake: ModelFake, answer: dict[str, Any], *, source: str | None
) -> tuple[Outcome, int | None, int | None, list[list[int]]]:
    """File step B with `source` over the shared model fake, which gives `answer`. Return the
    outcome, the possible original, the issue intake filed and the numbers of each shortlist it
    sent."""
    model_fake.answer(json.dumps(DEFAULT_PROPOSAL | answer))
    model = GatewayIntakeModel(AIConfig(), embedder=Embedder())
    part = replace(STEP_B, source=source)
    outcome = intake_candidate(roadmap.store, part, repo=REPO, model=model, confirm=True)
    sent = [[n["number"] for n in json.loads(call.user)["shortlist"]] for call in model_fake.calls]
    return outcome.decision.outcome, outcome.decision.possible_duplicate, outcome.number, sent


def test_a_candidate_filed_from_source_is_linked_as_a_sub_issue_of_that_issue(
    roadmap: Roadmap, model_fake: ModelFake
) -> None:
    """When a new candidate's source is an issue of the same repository, intake links the filed
    issue as a sub-issue of that source issue (#2035)."""
    parent = roadmap.finished(PARENT_TITLE, body=PARENT_BODY)
    source = _link(parent)
    outcome, _, filed, _ = _split(roadmap, model_fake, {}, source=source)
    assert outcome is Outcome.PLACE
    assert filed is not None
    parent_record = next(i for i in roadmap.store.issues() if i.number == parent)
    filed_record = next(i for i in roadmap.store.issues() if i.number == filed)
    writes = [w.operation for w in roadmap.store.job_writes() if w.number == parent]
    assert (parent_record.sub_issues, filed_record.parent, "add_sub_issue" in writes) == (
        1,
        parent,
        True,
    )


def test_a_candidate_from_another_repository_source_is_not_linked_as_sub_issue(
    roadmap: Roadmap, model_fake: ModelFake
) -> None:
    """When a candidate's source links an issue of another repository, intake links no sub-issue (#2035)."""
    outcome, _, filed, _ = _split(
        roadmap, model_fake, {}, source="https://github.com/other-org/other-repo/issues/99"
    )
    assert outcome is Outcome.PLACE
    assert filed is not None
    filed_record = next(i for i in roadmap.store.issues() if i.number == filed)
    writes = [w.operation for w in roadmap.store.job_writes()]
    assert (filed_record.parent, "add_sub_issue" in writes) == (None, False)


def test_intake_plan_lists_sub_issue_write(roadmap: Roadmap) -> None:
    """The plan of a candidate with source in the same repo lists the sub-issue write (#2035)."""
    parent = roadmap.finished(PARENT_TITLE, body=PARENT_BODY)
    source = _link(parent)
    model = FakeModel(proposals={STEP_B.title: REGRESSION})
    candidate = replace(STEP_B, source=source)
    plan = plan_intake(roadmap.store, repo=REPO, model=model, new=candidate)
    assert f"sub-issue of #{parent}" in plan.decisions[0].writes()
    rendered = render_intake(plan, repo=REPO)
    assert f"sub-issue of #{parent}" in rendered


def test_a_dry_run_lists_the_sub_issue_write_when_source_is_an_issue(
    tmp_path: Path, run_intake: Callable[..., str]
) -> None:
    """A dry run with --source naming an issue of the repository lists the sub-issue write (#2035)."""
    body_file = tmp_path / "body.md"
    body_file.write_text("body text", encoding="utf-8")
    output = run_intake(
        "--title",
        "feat: split task",
        "--body-file",
        str(body_file),
        "--source",
        f"https://github.com/{REPO}/issues/42",
        "--dry-run",
    )
    assert f"POST repos/{REPO}/issues/42/sub_issues" in output


def test_intake_docstring_names_sub_issue_write_rule() -> None:
    """The docstring of intake.py names the sub-issue write as an allowed extra write (#2035)."""
    from devops_cli.roadmap.intake import intake

    doc = intake.__doc__ or ""
    assert "Intake writes to no issue but the candidate" in doc
    assert "sub-issue" in doc


def test_source_parent_number_parses_hashes_and_numbers() -> None:
    """source_parent_number parses hash numbers, bare numbers, and returns None for non-numbers (#2035)."""
    from devops_cli.roadmap.intake.intake import source_parent_number

    assert source_parent_number(REPO, "#42") == 42
    assert source_parent_number(REPO, "42") == 42
    assert source_parent_number(REPO, "not-a-number") is None


@pytest.mark.parametrize("anchor", ["", "#issuecomment-1"], ids=["issue", "comment-on-issue"])
def test_a_part_is_never_a_duplicate_of_the_issue_its_source_names(
    roadmap: Roadmap, model_fake: ModelFake, anchor: str
) -> None:
    """The issue the part's source links, or links a comment of, stays off the shortlist, so
    even a model that names it with a shared change folds nothing: the part is filed, and its
    body ends with the link."""
    parent = roadmap.finished(PARENT_TITLE, body=PARENT_BODY)
    source = _link(parent) + anchor
    answer = FOLD_INTO_PARENT | {"duplicate_of": parent}
    outcome, _, filed, sent = _split(roadmap, model_fake, answer, source=source)
    bodies = [issue.body for issue in roadmap.store.issues() if issue.number == filed]
    assert (outcome, sent, [body.endswith(f"Source: {source}") for body in bodies]) == (
        Outcome.PLACE,
        [[]],
        [True],
    )


def test_a_part_that_repeats_an_item_other_than_its_source_names_it_as_the_possible_original(
    roadmap: Roadmap, model_fake: ModelFake
) -> None:
    """Only the source leaves the shortlist: the part filed before is still its possible
    original, and the part is filed (#2218)."""
    parent = roadmap.finished(PARENT_TITLE, body=PARENT_BODY)
    filed_before = roadmap.finished(STEP_B.title, body=STEP_B.body)
    answer = {
        "shared_change": "valkey.url keeps its scheme",
        "duplicate_of": filed_before,
        "duplicate_reason": "the earlier issue asks for the same step.",
    }
    outcome, original, filed, sent = _split(roadmap, model_fake, answer, source=_link(parent))
    assert (outcome, original, filed is not None, sent) == (
        Outcome.PLACE,
        filed_before,
        True,
        [[filed_before]],
    )


@pytest.mark.parametrize(
    ("sourced", "linked_to_source", "compared"),
    [
        pytest.param(True, True, False, id="sub-issue-of-the-source"),
        pytest.param(True, False, True, id="sub-issue-of-another-issue"),
        pytest.param(False, True, True, id="candidate-with-no-source"),
    ],
)
def test_a_part_is_compared_with_a_sibling_unless_it_is_a_sub_issue_of_the_source(
    roadmap: Roadmap,
    model_fake: ModelFake,
    *,
    sourced: bool,
    linked_to_source: bool,
    compared: bool,
) -> None:
    """The parts of one split are planned to be different changes, so a sub-issue of the
    candidate's source stays off its shortlist, whatever its title. A sub-issue of another issue,
    or any sub-issue when the candidate has no source, is compared as before (#2265)."""
    parent = roadmap.finished(PARENT_TITLE, body=PARENT_BODY, sub_issues=2)
    other = roadmap.finished("feat: an unrelated tracker", sub_issues=1)
    sibling = roadmap.finished(
        STEP_B.title, body=STEP_B.body, parent=parent if linked_to_source else other
    )
    answer = {
        "shared_change": "valkey.url keeps its scheme",
        "duplicate_of": sibling,
        "duplicate_reason": "the sibling asks for the same step.",
    }
    source = _link(parent) if sourced else None
    _, original, _, sent = _split(roadmap, model_fake, answer, source=source)
    assert (original, sent) == ((sibling, [[sibling]]) if compared else (None, [[]]))


def test_an_issue_with_sub_issues_is_never_the_original_of_a_candidate(
    roadmap: Roadmap, model_fake: ModelFake
) -> None:
    """Its sub-issues deliver an issue that has them, one pull request each, so no candidate
    asks for its change: it is compared with none, whatever the candidate's source."""
    parent = roadmap.finished(PARENT_TITLE, body=PARENT_BODY, sub_issues=4)
    step_c = roadmap.finished(STEP_C)
    answer = FOLD_INTO_PARENT | {"duplicate_of": parent}
    outcome, _, filed, sent = _split(roadmap, model_fake, answer, source=None)
    assert (outcome, filed is not None, sent) == (Outcome.PLACE, True, [[step_c]])


def test_a_sub_issue_decided_after_its_parent_in_one_run_is_not_closed_as_its_duplicate(
    roadmap: Roadmap,
) -> None:
    """A parent the run places does not join the items the later candidates are compared
    with, so its newer sub-issue is placed, not closed."""
    parent = roadmap.issue(PARENT_TITLE, body=PARENT_BODY, sub_issues=1)
    step = roadmap.issue(STEP_B.title, body=STEP_B.body)
    model = FakeModel(duplicates={STEP_B.title: PARENT_TITLE})
    roadmap.run(model)
    assert (
        [request.shortlist for request in model.requests],
        roadmap.store.closures(step),
        [roadmap.fields(number)[0] for number in (parent, step)],
    ) == ([(), ()], [], ["New", "New"])


def test_an_item_whose_issue_github_lists_with_sub_issues_is_on_no_shortlist() -> None:
    """GitHub's issue listing gives each issue the count of its sub-issues
    (`sub_issues_summary`), and intake reads it there, with no other request (#1985)."""
    github, store = on_github()
    github.seed_issue(1, PARENT_TITLE, labels=("type/bug", *FINISHED[1:]), sub_issues=4)
    github.seed_issue(2, STEP_C, labels=("type/bug", *FINISHED[1:]))
    model = FakeModel(duplicates={STEP_B.title: PARENT_TITLE})
    plan, _ = intake_on_github(store, model, new=STEP_B)
    assert (
        [[neighbour.number for neighbour in request.shortlist] for request in model.requests],
        [decision.outcome for decision in plan.decisions],
    ) == ([[2]], [Outcome.PLACE])


def test_an_item_whose_issue_github_lists_as_a_sub_issue_of_the_source_is_on_no_shortlist() -> None:
    """GitHub's issue listing gives each sub-issue the URL of its parent (`parent_issue_url`),
    and intake reads it there, with no other request. A parent in another repository, which
    may have the source's number, names another issue (#2265)."""
    github, store = on_github()
    finished = ("type/bug", *FINISHED[1:])
    github.seed_issue(1, PARENT_TITLE, labels=finished, sub_issues=2)
    github.seed_issue(2, STEP_C, labels=finished, parent=1)
    github.seed_issue(3, STEP_B.title, labels=finished, parent=1, parent_repo="example/other")
    model = FakeModel()
    part = replace(STEP_B, source=_link(1))
    plan, _ = intake_on_github(store, model, new=part)
    assert (
        [[neighbour.number for neighbour in request.shortlist] for request in model.requests],
        [decision.outcome for decision in plan.decisions],
    ) == ([[3]], [Outcome.PLACE])
