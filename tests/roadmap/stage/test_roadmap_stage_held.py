"""`devops roadmap stage`: the stage job replaces its own draft plan that fails the plan check
(#3387).

The rule reads the facts of the one draft pull request of a held item as data (`DraftRead`), so it
runs with no network and no checkout: the read of those facts is `held_draft` in the same module.
The job re-stages a draft plan that fails `check_proposal` one time, and holds the item for every
other draft.

The module under test is new, so each test imports it in its own body: a module-level import would
stop this module at collection on the base commit, before any assertion runs, and prove nothing.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from devops_cli.roadmap.body_hash import body_hashes
from devops_cli.roadmap.plan_check import PlanProblem
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_item

PULL = 12
BODY = "The job drops the last comment of a thread."
PROBLEM = PlanProblem(
    "openspec/changes/1-the-job-drops-a-comment/tasks.md",
    "paths",
    "The plan names a path that the tree does not hold.",
)
OUTSIDE = "src/devops_cli/roadmap/stage/stage.py"


def _read(**update: Any) -> Any:
    """The read of a draft pull request of an item whose plan check found one problem, with every
    other fact at the value that lets the job replace the draft."""
    from devops_cli.roadmap.stage.stage_held import DraftRead

    facts: dict[str, Any] = {
        "pull": PULL,
        "draft": True,
        "at_recorded_commit": True,
        "app_authored": True,
        "unresolved_threads": 0,
        "problems": (PROBLEM,),
        "outside_paths": (),
        "restaged": False,
    }
    return DraftRead(**{**facts, **update})


def _recorded(pull: int = PULL, text_hash: str | None = None) -> str:
    """The value of `stage.restage` for a re-stage of pull request `pull` of `BODY`."""
    from devops_cli.roadmap.stage.stage_held import Restage

    item = make_item(number=7, body=BODY)
    return Restage(pull=pull, text_hash=text_hash or body_hashes(item.body)[0]).record


def test_a_draft_plan_that_fails_check_proposal_is_replaced() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert may_replace(_read())


def test_a_draft_plan_that_passes_check_proposal_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(problems=()))


def test_a_draft_with_an_unresolved_review_thread_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(unresolved_threads=1))


def test_a_branch_with_a_path_outside_the_change_folder_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(outside_paths=(OUTSIDE,)))


def test_a_draft_at_another_commit_than_the_recorded_one_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(at_recorded_commit=False))


def test_a_draft_with_a_commit_of_a_person_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(app_authored=False))


def test_a_pull_request_that_is_no_draft_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(draft=False))


def test_a_draft_that_the_job_re_staged_once_stays_held() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(_read(restaged=True))


def test_a_read_of_no_draft_replaces_nothing() -> None:
    from devops_cli.roadmap.stage.stage_held import may_replace

    assert not may_replace(None)


def test_a_re_stage_records_the_pull_and_the_hash_of_the_text() -> None:
    from devops_cli.roadmap.stage.stage_held import Restage, recorded_restage, restage_record

    item = make_item(number=7, body=BODY)

    recorded = restage_record(item, PULL)
    held = recorded_restage(
        make_item(
            number=7,
            body=BODY,
            job_record={StageRecordKey.RESTAGE: recorded},
        )
    )

    assert held == Restage(pull=PULL, text_hash=body_hashes(BODY)[0])
    assert held is not None
    assert held.record == recorded


def test_a_record_that_is_no_re_stage_is_read_as_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from devops_cli.roadmap.stage.stage_held import recorded_restage

    item = make_item(number=7, job_record={StageRecordKey.RESTAGE: "not a re-stage"})

    with caplog.at_level(logging.WARNING):
        held = recorded_restage(item)

    assert held is None
    assert "is not a re-stage" in caplog.text


def test_an_item_with_no_re_stage_record_holds_none() -> None:
    from devops_cli.roadmap.stage.stage_held import recorded_restage

    assert recorded_restage(make_item(number=7)) is None


def test_a_re_stage_of_the_same_text_holds_the_draft() -> None:
    from devops_cli.roadmap.stage.stage_held import restaged_now

    item = make_item(number=7, body=BODY, job_record={StageRecordKey.RESTAGE: _recorded()})

    assert restaged_now(item)


def test_a_re_stage_of_another_text_holds_no_draft() -> None:
    """A body edit is a new text, and its plan gets the one re-stage that the record bounds."""
    from devops_cli.roadmap.stage.stage_held import restaged_now

    item = make_item(
        number=7,
        body="The job drops the last two comments of a thread.",
        job_record={StageRecordKey.RESTAGE: _recorded()},
    )

    assert not restaged_now(item)
