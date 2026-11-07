"""Candidates that agents file: no quota holds them back, and every agent issue is placed (#1959)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from devops_cli.roadmap.intake.intake import (
    NewCandidate,
    Outcome,
    apply_intake,
    intake_candidate,
    render_intake,
)
from tests.support.roadmap_intake import (
    REPO,
    FakeModel,
    Roadmap,
    labels_of,
    possible_duplicate_line,
)


def _new(title: str, **options: Any) -> NewCandidate:
    return NewCandidate(title=title, body=f"{title} body", **options)


def test_an_agent_candidate_is_filed_however_many_issues_agents_opened_recently(
    roadmap: Roadmap,
) -> None:
    """No filing quota holds an agent's candidate back (#1959). With 162 open items and 12 of
    them opened by agents today, a new candidate that duplicates nothing is filed and placed,
    and the report names no quota."""
    for index in range(150):
        roadmap.finished(f"chore: open item {index}")
    for index in range(12):
        roadmap.finished(f"feat: agent opening {index}", labels=("source/agent",))
    outcome = intake_candidate(
        roadmap.store,
        _new("feat: one more"),
        repo=REPO,
        model=FakeModel(),
        confirm=True,
    )
    number = outcome.number
    filed = (labels_of(roadmap, number), roadmap.fields(number)[:2]) if number else None
    report = render_intake(outcome.plan, repo=REPO).lower()
    assert (outcome.decision.outcome, filed, "quota" in report, "allowance" in report) == (
        Outcome.PLACE,
        (("source/agent", "type/feature"), ("New", "P2-Medium")),
        False,
        False,
    )


# ── Agent candidates and their duplicates ─────────────────────────────────────


def test_a_possible_duplicate_agent_candidate_is_filed_and_the_report_names_its_original(
    roadmap: Roadmap,
) -> None:
    """An agent's candidate that the model judges a duplicate is filed and labeled
    `status/new` with its Priority, and the report and the reason comment name the possible
    original (#2218)."""
    original = roadmap.finished("feat: cache embeddings")
    model = FakeModel(duplicates={"feat: cached embeddings": "feat: cache embeddings"})
    outcome = intake_candidate(
        roadmap.store, _new("feat: cached embeddings"), repo=REPO, model=model, confirm=True
    )
    report = render_intake(outcome.plan, repo=REPO).splitlines()
    filed = outcome.number or 0
    (comment,) = roadmap.comments(filed)
    labels = next(issue.labels for issue in roadmap.store.issues() if issue.number == filed)
    assert (
        outcome.decision.outcome,
        outcome.decision.possible_duplicate,
        len(roadmap.store.issues()),
        f"  - possible duplicate: #{original}. The model names `feat: cache embeddings` as the "
        "change that both ask for." in report,
        possible_duplicate_line(original, "feat: cache embeddings") in comment.splitlines(),
        {"status/new", "priority/p2-medium"} <= set(labels),
    ) == (Outcome.PLACE, original, 2, True, True, True)


def test_every_agent_issue_filed_outside_intake_is_placed(roadmap: Roadmap) -> None:
    """Agent issues filed outside intake are all placed, a P1 bug among them, and none gets a
    label beyond its type."""
    issues = [
        roadmap.issue(title, labels=("source/agent",))
        for title in ("feat: early", "feat: outside", "fix: outside")
    ]
    model = FakeModel(proposals={"fix: outside": {"type": "type/bug", "priority": "P1-High"}})
    plan = roadmap.plan(model)
    apply_intake(roadmap.store, plan)
    assert (
        [(d.subject.number, d.outcome) for d in plan.decisions],
        [roadmap.fields(number)[:2] for number in issues],
        [labels_of(roadmap, number) for number in issues],
    ) == (
        [(number, Outcome.PLACE) for number in issues],
        [("New", "P2-Medium"), ("New", "P2-Medium"), ("New", "P1-High")],
        [
            ("source/agent", "type/feature"),
            ("source/agent", "type/feature"),
            ("source/agent", "type/bug"),
        ],
    )


def test_a_retried_new_candidate_finds_the_issue_its_stopped_run_filed(roadmap: Roadmap) -> None:
    """A run that filed the issue and stopped before Priority left it open with no Priority,
    with the title and body that intake files. The retry labels that issue `status/new` instead
    of filing a second one (#2218)."""
    candidate = _new("feat: retry me")
    filed = roadmap.issue(
        candidate.title, candidate.filed_body(), labels=("source/agent",), author="NONE"
    )
    outcome = intake_candidate(roadmap.store, candidate, repo=REPO, model=FakeModel(), confirm=True)
    assert (
        outcome.decision.outcome,
        outcome.decision.subject.number,
        outcome.number,
        len(roadmap.store.issues()),
        roadmap.fields(filed)[0],
    ) == (Outcome.PLACE, filed, filed, 1, "New")


def test_a_person_files_through_the_command_without_the_agent_label(
    opened: Roadmap, fake_model: FakeModel, tmp_path: Path, run_intake: Callable[..., str]
) -> None:
    body = tmp_path / "body.md"
    body.write_text("text", encoding="utf-8")
    run_intake(
        "--title", "feat: mine", "--body-file", str(body), "--filed-by", "person", "--confirm"
    )
    (new,) = [i.number for i in opened.store.issues() if i.title == "feat: mine"]
    assert labels_of(opened, new) == ("type/feature",)
