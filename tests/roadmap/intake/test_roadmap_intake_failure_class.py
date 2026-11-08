"""Intake keeps the class, the count and the time of a failed placement in `IntakeRecord`, and a
candidate with a recorded class waits for the time of its class before the next round decides it
again (#4061).

A placement that raises a `GitHubOperationError` is class `ci_infra` and waits 1 hour. The wait
drops the candidate from the queue, so the round makes no triage call and no embedding call for it.
The item record gets no mark: the issue is a candidate, not an item.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_INTAKE_RECORD_FILENAME
from devops_cli.exceptions import RoadmapIntakeError
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.roadmap import failure as failure_module
from devops_cli.roadmap.intake import intake as intake_module
from devops_cli.roadmap.intake.intake import IntakeRecord, plan_intake
from devops_cli.roadmap.run import read_intake_record, run_scoped_update
from devops_cli.roadmap.stores.store import CloseReason
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    REPO,
    REPO_DIR,
    IntakeModel,
    make_candidates,
    run_intake_adapter,
    webhook_delivery,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

MINUTE = timedelta(minutes=1)
HOUR = timedelta(hours=1)
FAILED = 2


@dataclass
class CountingModel(IntakeModel):
    """The scripted intake model that also keeps each text it embeds."""

    embedded: list[str] = field(default_factory=list)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embedded.extend(texts)
        return super().embed(texts)


def _refused() -> GitHubOperationError:
    return GitHubOperationError("HTTP 502: Bad Gateway", operation="roadmap.write")


def _world(tmp_path: Path) -> tuple[InMemoryRoadmapStore, Path, list[str]]:
    """Three candidates, numbers 1 to 3 titled `candidate <n>`, and the repository directory."""
    store, _, titles = make_candidates(3)
    repo_dir = tmp_path / REPO_DIR
    repo_dir.mkdir(parents=True)
    return store, repo_dir, titles


def _round(store: InMemoryRoadmapStore, repo_dir: Path, model: IntakeModel, at: datetime) -> None:
    run_intake_adapter(store=store, repo=REPO, repo_dir=repo_dir, now=at, model=model)


def _failing_round(
    store: InMemoryRoadmapStore, repo_dir: Path, model: IntakeModel, at: datetime
) -> None:
    """A round in which the label write of candidate `FAILED` is refused."""
    store.fail_write(write="label_issue", item=FAILED, error=_refused())
    with pytest.raises(RoadmapIntakeError) as raised:
        _round(store, repo_dir, model, at)
    assert raised.value.failed_items == (FAILED,)


def _record(repo_dir: Path) -> IntakeRecord:
    return read_intake_record(repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME)


def test_the_place_step_is_a_step_name() -> None:
    assert failure_module.StepName.PLACE.value == "place"


def test_a_failed_placement_records_its_class_step_count_and_time_in_the_intake_record(
    tmp_path: Path,
) -> None:
    store, repo_dir, _ = _world(tmp_path)

    _failing_round(store, repo_dir, CountingModel(), NOW)

    entry = _record(repo_dir).failed[FAILED]
    assert (list(_record(repo_dir).failed), entry.step, entry.failure_class, entry.count) == (
        [FAILED],
        failure_module.StepName.PLACE,
        failure_module.FailureClass.CI_INFRA,
        1,
    )
    assert entry.failed_at == NOW


def test_repeated_failure_makes_no_triage_and_no_embedding_call_until_the_wait_ends(
    tmp_path: Path,
) -> None:
    """The second round, 30 minutes after the failure, drops the candidate from its queue: the
    model is not asked and embeds no text of it, the candidate is not placed, and the entry stays.
    A round after the 1 hour wait decides it again and places it, which clears the entry."""
    store, repo_dir, titles = _world(tmp_path)
    model = CountingModel()
    _failing_round(store, repo_dir, model, NOW)
    asked, embedded = len(model.asked), len(model.embedded)

    _round(store, repo_dir, model, NOW + 30 * MINUTE)
    held = (model.asked[asked:], model.embedded[embedded:], store.item(FAILED), _record(repo_dir))
    _round(store, repo_dir, model, NOW + 2 * HOUR)

    assert (held[0], held[1], held[2]) == ([], [], None)
    assert (held[3].failed[FAILED].count, held[3].failed[FAILED].failed_at) == (1, NOW)
    assert (model.asked[asked:], store.item(FAILED) is not None, _record(repo_dir).failed) == (
        [titles[FAILED - 1]],
        True,
        {},
    )


def test_repeated_failure_adds_one_to_the_count_in_the_record(tmp_path: Path) -> None:
    """A candidate that fails again after its wait has count 2 and the time of the new failure."""
    store, repo_dir, titles = _world(tmp_path)
    model = CountingModel()
    _failing_round(store, repo_dir, model, NOW)

    _failing_round(store, repo_dir, model, NOW + 2 * HOUR)

    entry = _record(repo_dir).failed[FAILED]
    assert (entry.count, entry.failed_at, model.asked.count(titles[FAILED - 1])) == (
        2,
        NOW + 2 * HOUR,
        2,
    )


def test_a_candidate_that_waits_is_neither_fresh_nor_a_reason_to_poll(tmp_path: Path) -> None:
    """A held candidate leaves `pending` false: the poll does not run intake for it before its
    wait ends."""
    store, repo_dir, _ = _world(tmp_path)
    model = CountingModel()
    _failing_round(store, repo_dir, model, NOW)

    _round(store, repo_dir, model, NOW + 30 * MINUTE)

    assert _record(repo_dir).pending is False


def test_the_webhook_update_records_a_failure_and_honors_the_wait(tmp_path: Path) -> None:
    """A scoped update of one issue records a failed placement as the poll does, and a later
    delivery for the same issue inside the wait decides nothing."""
    store, _, titles = make_candidates(3)
    model = CountingModel()
    store.fail_write(write="label_issue", item=FAILED, error=_refused())

    with pytest.raises(RoadmapIntakeError, match=f"#{FAILED} \\(GitHubOperationError"):
        run_scoped_update(
            webhook_delivery("opened", FAILED), store, data_dir=tmp_path, now=NOW, model=model
        )
    asked = len(model.asked)
    recorded = read_intake_record(tmp_path / REPO_DIR / CONST_ROADMAP_INTAKE_RECORD_FILENAME)
    run_scoped_update(
        webhook_delivery("edited", FAILED),
        store,
        data_dir=tmp_path,
        now=NOW + 30 * MINUTE,
        model=model,
    )
    run_scoped_update(
        webhook_delivery("edited", FAILED),
        store,
        data_dir=tmp_path,
        now=NOW + 2 * HOUR,
        model=model,
    )

    assert (recorded.failed[FAILED].count, model.asked[asked:], store.item(FAILED) is not None) == (
        1,
        [titles[FAILED - 1]],
        True,
    )


def test_no_item_mark_is_written_for_an_intake_failure(tmp_path: Path) -> None:
    """The failure lives in `IntakeRecord` only: no job writes to the issue that failed, and it
    is no item."""
    store, repo_dir, _ = _world(tmp_path)

    _failing_round(store, repo_dir, CountingModel(), NOW)
    _round(store, repo_dir, CountingModel(), NOW + 30 * MINUTE)

    assert (
        [write for write in store.job_writes() if write.number == FAILED],
        store.item(FAILED),
        list(_record(repo_dir).failed),
    ) == ([], None, [FAILED])


def test_an_item_changed_by_a_person_is_no_failure_and_leaves_no_entry(tmp_path: Path) -> None:
    store, repo_dir, _ = _world(tmp_path)
    changed = RoadmapItemChangedError(f"#{FAILED}'s Status changed since the plan.")
    store.fail_write(write="set_field", item=FAILED, error=changed)

    _round(store, repo_dir, CountingModel(), NOW)

    assert _record(repo_dir).failed == {}


def test_an_entry_of_an_issue_that_is_no_candidate_any_more_is_dropped(tmp_path: Path) -> None:
    """A candidate that a person closed leaves no entry behind in the next round."""
    store, repo_dir, _ = _world(tmp_path)
    model = CountingModel()
    _failing_round(store, repo_dir, model, NOW)
    store.close_by_hand(FAILED, CloseReason.NOT_PLANNED)

    _round(store, repo_dir, model, NOW + 2 * HOUR)

    assert _record(repo_dir).failed == {}


def test_old_record_without_a_failed_field_loads_and_keeps_its_candidates(
    tmp_path: Path,
) -> None:
    """An intake record file from before the field `failed` loads with an empty `failed`, keeps
    its `pending` flag and its waiting candidates, and a round then writes the new field."""
    store, repo_dir, _ = _world(tmp_path)
    path = repo_dir / CONST_ROADMAP_INTAKE_RECORD_FILENAME
    old = {
        "pending": True,
        "waiting": {"7": {"updated_at": None, "decided_at": "2026-10-04T11:00:00Z"}},
    }
    path.write_text(json.dumps(old), encoding="utf-8")

    loaded = read_intake_record(path)
    _round(store, repo_dir, CountingModel(), NOW)

    assert (loaded.pending, list(loaded.waiting), loaded.failed) == (True, [7], {})
    assert "failed" in json.loads(path.read_text(encoding="utf-8"))


def test_plan_intake_leaves_out_a_candidate_whose_wait_has_not_ended() -> None:
    """The plan reports the numbers it held back, and decides the candidate once the wait ends."""
    store, _, _ = make_candidates(3)
    failed = {
        FAILED: intake_module.Failed(
            step=failure_module.StepName.PLACE,
            failure_class=failure_module.FailureClass.CI_INFRA,
            count=1,
            failed_at=NOW,
        )
    }

    def decided(at: datetime) -> tuple[list[int | None], tuple[int, ...]]:
        plan = plan_intake(
            store, repo=REPO, model=IntakeModel(), limit=5, waiting={}, failed=failed, now=at
        )
        return [d.subject.number for d in plan.decisions], plan.held

    assert (decided(NOW + 59 * MINUTE), decided(NOW + HOUR)) == (
        ([1, 3], (FAILED,)),
        ([1, 2, 3], ()),
    )


def test_a_closed_candidate_is_no_held_candidate() -> None:
    store, _, _ = make_candidates(2)
    store.close_by_hand(FAILED, CloseReason.NOT_PLANNED)
    failed = {
        FAILED: intake_module.Failed(
            step=failure_module.StepName.PLACE,
            failure_class=failure_module.FailureClass.CI_INFRA,
            count=1,
            failed_at=NOW,
        )
    }

    plan = plan_intake(
        store, repo=REPO, model=IntakeModel(), limit=5, waiting={}, failed=failed, now=NOW
    )

    assert plan.held == ()
