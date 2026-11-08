"""An Item that a person changes between the plan and the write is not a failed placement: the
write refuses before it changes anything, and intake decides the candidate again (#4042).
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_INTAKE_RECORD_FILENAME,
    CONST_ROADMAP_REFINE_DUE_STAMP,
)
from devops_cli.exceptions import RoadmapIntakeError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.roadmap.intake.intake import apply_intake
from devops_cli.roadmap.intake.intake_model import ModelEvidence, ModelProposal
from devops_cli.roadmap.run import read_intake_record
from devops_cli.roadmap.stores.store import Evidence, EvidenceKind
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_intake import FakeModel, Roadmap
from tests.support.roadmap_run import (
    NOW,
    PLANNED,
    REPO,
    REPO_DIR,
    Clock,
    IntakeModel,
    run_intake_adapter,
)

INTAKE_LOGGER = "devops_cli.roadmap.intake.intake"


def _changed(number: int) -> RoadmapItemChangedError:
    return RoadmapItemChangedError(f"#{number}'s Status changed since the plan.")


def test_item_changed_for_one_candidate_places_the_others_and_ends_the_round_with_no_error(
    roadmap: Roadmap, caplog: pytest.LogCaptureFixture
) -> None:
    """A person changes candidate 2 of 3 after the plan: its write raises
    `RoadmapItemChangedError` and nothing is written. The others are placed, the round ends with
    no error, one INFO line names the candidate, and the next plan holds the candidate again."""
    first, changed, last = (roadmap.issue(f"feat: candidate {n}") for n in range(3))
    placed = ("New", "P2-Medium", "Medium", "Low", None)
    roadmap.store.fail_write(write="set_field", item=changed, error=_changed(changed))
    plan = roadmap.plan(FakeModel())

    with caplog.at_level(logging.INFO, logger=INTAKE_LOGGER):
        applied = apply_intake(roadmap.store, plan, repo=REPO)

    lines = [r for r in caplog.records if r.name == INTAKE_LOGGER and f"#{changed}" in r.message]
    again = roadmap.plan(FakeModel())
    assert (
        applied.placed,
        applied.failed,
        roadmap.fields(first),
        roadmap.fields(last),
        roadmap.fields(changed),
        [r.levelno for r in lines],
        [d.subject.number for d in again.decisions],
    ) == (2, (), placed, placed, (None, None, None, None, None), [logging.INFO], [changed])


def test_item_changed_in_a_round_leaves_the_candidate_in_the_intake_record(
    tmp_path: Path,
) -> None:
    """The Service's intake round, with candidate 2 of 3 changed by a person: the round returns
    with no error, and the intake record still holds candidate 2 as a candidate."""
    clock = Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    numbers = [store.seed_issue(f"candidate {n}") for n in range(1, 4)]
    store.fail_write(write="set_field", item=numbers[1], error=_changed(numbers[1]))
    repo_dir = tmp_path / REPO_DIR
    repo_dir.mkdir(parents=True)

    run_intake_adapter(store=store, repo=REPO, repo_dir=repo_dir, now=NOW, model=IntakeModel())

    record = read_intake_record(repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME)
    assert (
        [store.item(number) is not None for number in numbers],
        numbers[1] in record.waiting,
    ) == ([True, False, True], True)


# ── The refine_due stamp (#1540) ──────────────────────────────────────────────


def _p0_roadmap(tmp_path: Path) -> tuple[InMemoryRoadmapStore, int, int, IntakeModel, Path]:
    """A roadmap with a P0 candidate (number 1) and a P2 candidate (number 2), the model that
    decides them, and the repository directory."""
    store = InMemoryRoadmapStore(clock=Clock())
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    p0 = store.seed_issue("P0 critical candidate", body="Failed run 4242.", labels=["type/bug"])
    other = store.seed_issue("P2 candidate")
    proposal = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P0-Critical",
        priority_reason="critical.",
        value="High",
        value_reason="high.",
        effort="Low",
        effort_reason="low.",
        evidence=ModelEvidence(kind="failed_run", value="4242"),
    )
    model = IntakeModel(proposals={"P0 critical candidate": proposal})
    repo_dir = tmp_path / REPO_DIR
    repo_dir.mkdir(parents=True)
    return store, p0, other, model, repo_dir


def test_refine_due_is_stamped_for_a_p0_placed_in_a_round_with_a_real_placement_failure(
    tmp_path: Path,
) -> None:
    """The P0 candidate is placed, and the label write of the other candidate fails for real:
    the round still stamps `refine_due` before it raises, so refine runs in the next poll."""
    store, p0, other, model, repo_dir = _p0_roadmap(tmp_path)
    store.fail_write(write="label_issue", item=other, error=GitHubOperationError("HTTP 502"))

    with pytest.raises(RoadmapIntakeError) as raised:
        run_intake_adapter(store=store, repo=REPO, repo_dir=repo_dir, now=NOW, model=model)

    stamps = json.loads((repo_dir / "schedule.json").read_text(encoding="utf-8"))
    assert (raised.value.failed_items, store.item(p0) is not None, stamps) == (
        (other,),
        True,
        {CONST_ROADMAP_REFINE_DUE_STAMP: NOW.isoformat()},
    )


def test_refine_due_is_not_stamped_when_the_placement_of_the_p0_itself_fails(
    tmp_path: Path,
) -> None:
    """A P0 decision whose own placement failed placed nothing, so the round stamps nothing."""
    store, p0, _, model, repo_dir = _p0_roadmap(tmp_path)
    store.fail_write(write="set_field", item=p0, error=GitHubOperationError("HTTP 502"))

    with pytest.raises(RoadmapIntakeError) as raised:
        run_intake_adapter(store=store, repo=REPO, repo_dir=repo_dir, now=NOW, model=model)

    assert (raised.value.failed_items, (repo_dir / "schedule.json").exists()) == ((p0,), False)


def test_refine_due_is_not_stamped_when_the_p0_item_changed_and_the_round_has_no_error(
    tmp_path: Path,
) -> None:
    """A person changes the P0 candidate after the plan: nothing is placed for it, the round
    ends with no error, and it stamps nothing. The next round decides the candidate again."""
    store, p0, _, model, repo_dir = _p0_roadmap(tmp_path)
    store.fail_write(write="set_field", item=p0, error=_changed(p0))

    outcome = run_intake_adapter(
        store=store, repo=REPO, repo_dir=repo_dir, now=NOW + timedelta(minutes=1), model=model
    )

    assert (outcome.placed_critical_or_p0, (repo_dir / "schedule.json").exists()) == (False, False)
