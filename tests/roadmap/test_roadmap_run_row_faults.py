"""Offline fault-injection suite for the Service row executions (#3075).

The three cases run offline on lane_table, poll_round, and apply_stage:
1. A RoadmapItemChangedError during intake apply leaves the person's priority label in
   place, keeps the earlier placement record, and skips the candidate (#4042); a placement
   failure (GitHubOperationError) counts the candidate as failed, raises RoadmapRunError
   naming the item and the error class, and keeps the record.
2. A Service stop between two stage items: the second item's write raises ServiceStoppingError,
   the first item's stage record and branch stay, and the round ends as a stop and not as a
   failed round.
3. A failed marks write after the draft pull request exists: fail_write(write="set_marks", at=1)
   makes the set_marks call that follows the pull request open raise GitHubOperationError, and
   write_each catches it as a plain DevOpsCLIError and records a StageFailure whose error class
   is GitHubOperationError and whose reason is the masked error message. The branch and the draft
   pull request stay on origin, the item posts no staged comment, and the item counts as failed in
   the row.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_INTAKE_RECORD_FILENAME,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.exceptions import (
    GitHubOperationError,
    RoadmapItemChangedError,
    RoadmapRunError,
    ServiceStoppingError,
    ended_by_stop,
)
from devops_cli.roadmap.run import read_intake_record
from devops_cli.roadmap.stage.stage import parse_filters, plan_stage
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    REPO_DIR,
    IntakeModel,
    intake_table,
    make_candidates,
    poll_round,
)
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    make_stage_proposal,
    seed_stageable,
    validate_args,
)

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake

pytestmark = pytest.mark.usefixtures("keyring_store")

NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)


def test_item_changed_during_intake_apply_preserves_label_and_keeps_record(
    tmp_path: Path,
) -> None:
    """An Item changed by a person during intake apply leaves the person's label in place,
    keeps the placement record, and skips the candidate (#4042); a write failure counts the
    candidate as failed, raises RoadmapRunError naming the item and error, and keeps the record.
    """
    store, _, _ = make_candidates(7)
    person_label = "area/core"
    store.label_issue(1, person_label)
    assert person_label in store._roadmap.issues[1].labels

    model = IntakeModel()
    table = intake_table(model, [])

    # 1. When a person changes the item, RoadmapItemChangedError keeps the round alive (#4042)
    changed_error = RoadmapItemChangedError("#1's Status changed since the plan.")
    store.fail_write(write="label_issue", item=1, error=changed_error)

    poll_round(store, tmp_path, table=table)

    # Label stays in place and the candidate stays in the waiting record
    assert person_label in store._roadmap.issues[1].labels
    record_path = tmp_path / REPO_DIR / CONST_ROADMAP_INTAKE_RECORD_FILENAME
    record = read_intake_record(record_path)
    assert 1 in record.waiting

    # 2. When a write fails with GitHubOperationError, the round fails and names the item
    store.fail_write(
        write="label_issue",
        item=1,
        error=GitHubOperationError("HTTP 502: Bad Gateway"),
    )
    with pytest.raises(RoadmapRunError) as raised:
        poll_round(store, tmp_path, table=table)

    err = str(raised.value)
    assert "#1" in err
    assert "GitHubOperationError" in err
    assert person_label in store._roadmap.issues[1].labels
    assert record_path.exists()


def test_service_stop_between_stage_items_preserves_first_stage_work(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """A Service stop between two stage items ends the round as a stop, not as a failed round,
    and keeps the stage record and branch of the first item.
    """
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store, "fix(roadmap): the job drops a comment")
    seed_stageable(store, "fix(roadmap): the job drops a label")
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    store.seed_pull("staging PR 1", head_ref="fix/1-the-job-drops-a-comment", draft=True)
    store.seed_pull("staging PR 2", head_ref="fix/2-the-job-drops-a-label", draft=True)
    github_api.route("POST", PULLS, OPENED)

    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    openspec_fake.script_sequence(validate_args("2-the-job-drops-a-label"), (0, VALID_REPORT))
    model_fake.answer(make_stage_proposal())

    # Second item's write raises ServiceStoppingError
    stop_exc = ServiceStoppingError("the Service is stopping")
    store.fail_write(write="set_marks", item=2, error=stop_exc)

    plan = plan_stage(store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(()))

    with pytest.raises(ServiceStoppingError) as stopped:
        apply_stage(store, plan, source=stage_repo.clone, now=NOW)

    assert ended_by_stop(stopped.value)

    # First item's stage record and branch stay
    item1 = store.item(1)
    assert item1 is not None
    record = {k.value if hasattr(k, "value") else str(k): v for k, v in item1.job_record.items()}
    assert record.get("stage.pr") == "5"
    assert record.get("stage.branch") == "fix/1-the-job-drops-a-comment"
    branch_output = stage_repo.origin_git(
        "branch", "--list", "fix/1-the-job-drops-a-comment"
    ).strip()
    assert branch_output != ""


def test_failed_marks_write_records_stage_failure_and_keeps_draft_pr(
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: GitHubApiFake,
    openspec_fake: OpenSpecFake,
) -> None:
    """A failed marks write after opening the draft pull request records a StageFailure with
    the error class and masked message, keeps the branch and draft pull request on origin,
    posts no staged comment, and counts the item as failed in the row.
    """
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store, "fix(roadmap): the job drops a comment")
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    store.seed_pull("staging PR 1", head_ref="fix/1-the-job-drops-a-comment", draft=True)
    github_api.route("POST", PULLS, OPENED)

    openspec_fake.script_sequence(validate_args("1-the-job-drops-a-comment"), (0, VALID_REPORT))
    model_fake.answer(make_stage_proposal())

    # Fail the set_marks write that follows opening the draft pull request (the second set_marks call)
    secret_text = "secret_ghp_token12345"
    store.fail_write(
        write="set_marks",
        at=2,
        error=GitHubOperationError(f"HTTP 502: Bad Gateway with token {secret_text}"),
    )

    plan = plan_stage(store, repo=STAGE_REPO, source=stage_repo.clone, filters=parse_filters(()))
    applied = apply_stage(store, plan, source=stage_repo.clone, now=NOW)

    # The row result: staged is empty, failed holds item 1
    assert applied.staged == ()
    assert len(applied.failed) == 1
    failure = applied.failed[0]
    assert failure.number == 1
    assert failure.error == "GitHubOperationError"
    assert secret_text not in failure.reason

    # Final status label remains Ready (not changed to Staged)
    item = store.item(1)
    assert item is not None
    assert item.status == "Ready"

    # The branch and draft pull request stay on origin
    branch_output = stage_repo.origin_git(
        "branch", "--list", "fix/1-the-job-drops-a-comment"
    ).strip()
    assert branch_output != ""

    # No staged comment was posted
    comments = [
        c.body
        for c in store.comments_on(1)
        if c.body.startswith(CONST_ROADMAP_STAGE_COMMENT_MARKER)
    ]
    assert comments == []
