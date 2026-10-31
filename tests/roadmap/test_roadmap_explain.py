"""`devops roadmap explain`: why each job takes an item or leaves it out (#2911). Git runs for real
on a clone with an `origin`, and GitHub is faked."""

from __future__ import annotations

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.explain import Explanation, JobVerdict, explain_item, render_explanation
from devops_cli.roadmap.implement import parse_implement_filters
from devops_cli.roadmap.stage import parse_filters
from devops_cli.roadmap.store import GitHubState, ImplementRecordKey, ItemField, StageRecordKey
from tests.support.roadmap_implement import TITLE, JobWorld
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

LOW = ("type/bug", "effort/low")
TEXTS = MESSAGES.roadmap


def _seed(
    world: JobWorld,
    *,
    labels: tuple[str, ...] = LOW,
    status: str = "Ready",
    priority: str = "P1-High",
    state: GitHubState = GitHubState.OPEN,
    title: str = "fix(roadmap): another job drops a label",
) -> int:
    return world.store.seed_issue(
        title,
        body="The job drops a label.",
        labels=labels,
        fields={ItemField.STATUS: status, ItemField.PRIORITY: priority},
        author_association="OWNER",
        state=state,
    )


def _explain(
    world: JobWorld,
    number: int,
    *,
    stage: tuple[str, ...] = (),
    implement: tuple[str, ...] = (),
    stage_limit: int = 3,
    implement_limit: int = 1,
) -> Explanation:
    return explain_item(
        world.store,
        repo=STAGE_REPO,
        source=world.repo.clone,
        number=number,
        stage_filters=parse_filters(stage),
        implement_filters=parse_implement_filters(implement),
        stage_limit=stage_limit,
        implement_limit=implement_limit,
    )


def test_an_item_of_medium_effort_names_the_filter_family_and_both_values(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world, labels=("type/bug", "effort/medium"), status="Planned")

    explained = _explain(job_world, number)

    assert explained.implement == JobVerdict(
        False, "The filter takes effort low. The item has effort medium."
    )
    assert explained.stage == JobVerdict(
        False, "The filter takes status ready. The item has status planned."
    )


def test_a_claimed_item_names_its_owner_for_both_jobs(job_world: JobWorld) -> None:
    number = _seed(job_world, labels=(*LOW, "owner/human"))

    explained = _explain(job_world, number)

    assert (explained.stage, explained.implement) == (
        JobVerdict(False, "It is claimed by human."),
        JobVerdict(False, "It is claimed by human."),
    )


def test_a_stopped_item_names_its_stop_for_the_implement_job(job_world: JobWorld) -> None:
    held = job_world.store.item(job_world.number)
    assert held is not None
    job_world.store.set_marks(held, {ImplementRecordKey.STOPPED: "group 2"})

    explained = _explain(job_world, job_world.number)

    assert explained.implement == JobVerdict(
        False, TEXTS.implement_left_stopped.format(stopped="group 2")
    )


def test_an_unplanned_item_is_taken_by_stage_and_left_out_by_implement(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world)

    explained = _explain(job_world, number)

    assert explained.stage == JobVerdict(True)
    assert explained.implement == JobVerdict(
        False, TEXTS.implement_left_not_staged.format(branch="main")
    )


def test_a_recorded_group_over_the_budget_is_the_reason_of_the_stage_job(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world)
    held = job_world.store.item(number)
    assert held is not None
    job_world.store.set_marks(
        held,
        {
            StageRecordKey.NEEDS_SPLIT: "The first group (9000 tokens)",
            StageRecordKey.FILE_CAP: str(CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS),
        },
    )

    explained = _explain(job_world, number)

    assert explained.stage == JobVerdict(
        False,
        TEXTS.stage_left_recorded_split.format(
            detail="The first group (9000 tokens)", number=number
        ),
    )


def test_a_closed_issue_and_a_missing_issue_give_the_shared_reasons(job_world: JobWorld) -> None:
    closed = _seed(job_world, state=GitHubState.CLOSED)

    reasons = [
        (e.stage.reason, e.implement.reason)
        for e in (_explain(job_world, closed), _explain(job_world, 999))
    ]

    assert reasons == [
        (TEXTS.item_left_closed, TEXTS.item_left_closed),
        (TEXTS.item_left_not_item, TEXTS.item_left_not_item),
    ]


def test_an_item_behind_a_full_limit_names_the_limit(job_world: JobWorld) -> None:
    first = _seed(job_world, priority="P0-Critical")
    second = _seed(job_world, priority="P2-Medium", title="fix(roadmap): a third job drops it")

    taken = _explain(job_world, first, stage_limit=1)
    behind = _explain(job_world, second, stage_limit=1)

    assert (taken.stage, behind.stage) == (
        JobVerdict(True),
        JobVerdict(False, TEXTS.item_left_limit.format(limit=1)),
    )


def test_the_staged_item_is_taken_by_the_implement_job(job_world: JobWorld) -> None:
    explained = _explain(job_world, job_world.number)

    assert explained.implement == JobVerdict(True)


def test_explain_calls_no_model_and_writes_nothing(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("explain called a model")

    monkeypatch.setattr("devops_cli.roadmap.stage.get_llm_client", refuse)
    number = _seed(job_world)
    before = (job_world.store.job_writes, job_world.store.comments_on(number))

    _explain(job_world, number)
    _explain(job_world, job_world.number)

    assert (job_world.store.job_writes, job_world.store.comments_on(number)) == before


def test_the_report_gives_yes_or_no_for_each_job_and_the_reason_of_a_no() -> None:
    explained = Explanation(
        STAGE_REPO,
        7,
        TITLE,
        JobVerdict(False, "It is claimed by human."),
        JobVerdict(True),
    )

    assert render_explanation(explained).splitlines() == [
        f"# {STAGE_REPO} #7: {TITLE}",
        "",
        "Stage job: no. It is claimed by human.",
        "Implement job: yes.",
    ]
