"""The intake row of the due table: how a capped round decides its candidates over successive
polls, and how a placement makes the refine row due (#981).
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta
from functools import partial
from pathlib import Path

import pytest

from devops_cli.config.constants import (
    CONST_ROADMAP_REFINE_DUE_STAMP,
)
from devops_cli.exceptions import (
    RoadmapRunError,
)
from devops_cli.roadmap.intake.intake_model import (
    ModelEvidence,
    ModelProposal,
)
from devops_cli.roadmap.run import (
    build_stub_table,
    run_due_jobs,
)
from devops_cli.roadmap.stores.store import (
    Evidence,
    EvidenceKind,
)
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.roadmap_run import (
    NOW,
    PLANNED,
    POLL_KEY,
    REPO,
    REPO_DIR,
    Clock,
    IntakeModel,
    intake_table,
    make_candidates,
    poll_round,
    recorded,
    run_intake_adapter,
    stamp_successes,
)

pytestmark = pytest.mark.usefixtures("keyring_store")


def test_a_capped_intake_decides_every_candidate_over_successive_polls_fresh_ones_first(
    tmp_path: Path,
) -> None:
    """Twelve candidates and a limit of five, the five oldest unusable: three polls decide all
    twelve, and the fourth runs no intake. A person's edit to a skipped candidate puts it first
    at intake's next run."""
    store, clock, titles = make_candidates(12)
    model = IntakeModel(unusable=frozenset(titles[:5]))
    ran: list[str] = []
    table = intake_table(model, ran)

    def poll(minutes: int) -> tuple[tuple[str, ...], tuple[str, ...]]:
        ran.clear()
        asked = len(model.asked)
        poll_round(store, tmp_path, now=NOW + timedelta(minutes=minutes), table=table)
        return tuple(ran), tuple(model.asked[asked:])

    polls = [poll(minutes) for minutes in (0, 5, 10, 15)]
    clock.now = NOW + timedelta(minutes=20)
    store.as_actor("alice").write_issue_body(4, "Steps to reproduce: run it twice.")
    edited_first = poll(75)[1][:1]
    assert (polls, edited_first) == (
        [
            (("intake",), tuple(titles[:5])),
            (("intake",), tuple(titles[5:10])),
            (("intake",), (*titles[10:], *titles[:3])),
            ((), ()),
        ],
        ("candidate 4",),
    )


def test_a_failed_placement_is_decided_again_after_the_fresh_candidates_and_its_round_goes_on(
    tmp_path: Path,
) -> None:
    """A round whose first placement fails at its first gh write still places the other four
    and fails the job (#1443). The record is written before any placement, so the next round
    decides the fresh candidates and none of the four again (#1360). The failed one waits for the
    1 hour of its class and is decided again after it (#4061)."""
    store, _, titles = make_candidates(7)
    model = IntakeModel()
    table = intake_table(model, [])
    store.fail_write(write="label_issue")
    with pytest.raises(RoadmapRunError) as raised:
        poll_round(store, tmp_path, table=table)
    assert raised.value.error_code == "DEVOPS_CLI_ERROR"
    placed = tuple(store.item(number) is not None for number in range(1, 6))
    asked = len(model.asked)
    poll_round(store, tmp_path, now=NOW + timedelta(minutes=5), table=table)
    held = tuple(model.asked[asked:])
    asked = len(model.asked)
    poll_round(store, tmp_path, now=NOW + timedelta(minutes=65), table=table)
    assert (store.writes[:1], placed, held, tuple(model.asked[asked:])) == (
        ["label_issue"],
        (False, True, True, True, True),
        tuple(titles[5:]),
        (titles[0],),
    )


def test_intake_placing_p0_item_makes_no_refine_call_and_refine_is_due_through_cross_job_rule(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An intake run that places a P0 item makes no refine call directly; the same round's refine
    row is due through the cross-job rule (#1540)."""
    clock = Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    num = store.seed_issue(
        "P0 critical candidate",
        body="Failed run 4242.",
        labels=["type/bug"],
        author_association="COLLABORATOR",
    )
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
    ran: list[str] = []
    intake = partial(run_intake_adapter, model=model)
    table = build_stub_table(
        {
            "intake": recorded(ran, "intake", intake),
            "refine": recorded(ran, "refine"),
        }
    )
    stamp_successes(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    with caplog.at_level(logging.WARNING, logger="devops_cli.roadmap.intake.intake"):
        jobs = poll_round(store, tmp_path, table=table)

    intake_warnings = [
        r.getMessage() for r in caplog.records if r.name == "devops_cli.roadmap.intake.intake"
    ]
    item = store.item(num)
    assert (
        jobs,
        ran,
        any("refine" in w.lower() for w in intake_warnings),
        item is not None and item.priority,
    ) == (("intake", "refine"), ["intake", "refine"], False, "P0-Critical")


def test_intake_placing_p0_critical_issue_already_labelled_type_bug_makes_refine_due(
    tmp_path: Path,
) -> None:
    """An intake that places a P0-Critical issue already labelled type/bug, so intake adds no
    type label, makes refine due in the same round (#1540)."""
    clock = Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    num = store.seed_issue(
        "Pre-labelled P0 bug",
        body="Failed run 4242.",
        labels=["type/bug"],
        author_association="COLLABORATOR",
    )
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
    model = IntakeModel(proposals={"Pre-labelled P0 bug": proposal})
    ran: list[str] = []
    intake = partial(run_intake_adapter, model=model)
    table = build_stub_table(
        {
            "intake": recorded(ran, "intake", intake),
            "refine": recorded(ran, "refine"),
        }
    )
    stamp_successes(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    jobs = poll_round(store, tmp_path, table=table)
    item = store.item(num)
    assert (
        jobs,
        ran,
        item is not None and item.priority,
    ) == (("intake", "refine"), ["intake", "refine"], "P0-Critical")


def test_intake_placing_p2_medium_issue_labelled_type_bug_does_not_make_refine_due(
    tmp_path: Path,
) -> None:
    """An intake that places a P2-Medium issue labelled type/bug does not make refine due in
    the same round, whether it goes to the backlog or keeps a milestone a person set (#1540)."""
    clock = Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    # 1. Backlog placement
    num_backlog = store.seed_issue("Backlog P2 bug")
    proposal_backlog = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P2-Medium",
        priority_reason="medium.",
        value="Medium",
        value_reason="medium.",
        effort="Low",
        effort_reason="low.",
    )
    model_backlog = IntakeModel(proposals={"Backlog P2 bug": proposal_backlog})
    ran_backlog: list[str] = []
    table_backlog = build_stub_table(
        {
            "intake": recorded(
                ran_backlog, "intake", partial(run_intake_adapter, model=model_backlog)
            ),
            "refine": recorded(ran_backlog, "refine"),
        }
    )
    stamp_successes(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    jobs_backlog = poll_round(store, tmp_path, table=table_backlog)
    item_backlog = store.item(num_backlog)
    assert (
        jobs_backlog,
        ran_backlog,
        item_backlog is not None and item_backlog.priority,
    ) == (("intake",), ["intake"], "P2-Medium")

    # 2. Keeps a milestone a person set
    num_milestone = store.seed_issue("Milestone P2 bug", milestone=PLANNED)
    proposal_milestone = ModelProposal(
        type="type/bug",
        type_reason="defect.",
        priority="P2-Medium",
        priority_reason="medium.",
        value="Medium",
        value_reason="medium.",
        effort="Low",
        effort_reason="low.",
    )
    model_milestone = IntakeModel(proposals={"Milestone P2 bug": proposal_milestone})
    ran_milestone: list[str] = []
    table_milestone = build_stub_table(
        {
            "intake": recorded(
                ran_milestone, "intake", partial(run_intake_adapter, model=model_milestone)
            ),
            "refine": recorded(ran_milestone, "refine"),
        }
    )
    stamp_successes(
        tmp_path,
        metrics=NOW,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
    )
    jobs_milestone = poll_round(store, tmp_path, table=table_milestone)
    item_milestone = store.item(num_milestone)
    assert (
        jobs_milestone,
        ran_milestone,
        item_milestone is not None and (item_milestone.priority, item_milestone.milestone),
    ) == (("intake",), ["intake"], ("P2-Medium", PLANNED))


def test_cross_lane_refine_becomes_due_at_next_model_lane_round_via_stamp(
    tmp_path: Path,
) -> None:
    """Intake placing a P0 item in the triage lane stamps refine_due in schedule.json, making
    refine due in the next model-lane round, and refine succeeding updates its stamp so it is no
    longer due (#1534)."""
    clock = Clock()
    store = InMemoryRoadmapStore(clock=clock)
    store.seed_file(".github/labels.yml", Path(".github/labels.yml").read_text(encoding="utf-8"))
    store.seed_milestone(PLANNED)
    store.seed_evidence(Evidence(kind=EvidenceKind.FAILED_RUN, value="4242"))
    store.seed_issue(
        "P0 critical bug",
        body="Failed run 4242.",
        labels=["type/bug"],
        author_association="COLLABORATOR",
    )
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
    model = IntakeModel(proposals={"P0 critical bug": proposal})
    intake = partial(run_intake_adapter, model=model)
    stamp_successes(
        tmp_path,
        intake=NOW - timedelta(minutes=61),
        refine=NOW - timedelta(minutes=5),
        stage=NOW - timedelta(minutes=5),
        alternatives=NOW - timedelta(minutes=5),
    )

    triage_table = build_stub_table({"intake": intake})
    triage_ran = run_due_jobs(
        REPO,
        store,
        batch={POLL_KEY: 1},
        table=triage_table,
        data_dir=tmp_path,
        now=NOW,
    )
    assert triage_ran == ("intake",)
    schedule = json.loads((tmp_path / REPO_DIR / "schedule.json").read_text(encoding="utf-8"))
    assert CONST_ROADMAP_REFINE_DUE_STAMP in schedule
    assert schedule[CONST_ROADMAP_REFINE_DUE_STAMP] == NOW.isoformat()

    model_ran: list[str] = []
    model_table = build_stub_table(
        {
            "refine": recorded(model_ran, "refine"),
            "stage": recorded(model_ran, "stage"),
            "alternatives": recorded(model_ran, "alternatives"),
        }
    )
    ran_jobs = run_due_jobs(
        REPO,
        store,
        batch={POLL_KEY: 1},
        table=model_table,
        data_dir=tmp_path,
        now=NOW,
    )
    assert ran_jobs == ("refine",)
    schedule_after = json.loads((tmp_path / REPO_DIR / "schedule.json").read_text(encoding="utf-8"))
    assert schedule_after["refine"] == NOW.isoformat()

    model_ran.clear()
    next_now = NOW + timedelta(minutes=1)
    ran_again = run_due_jobs(
        REPO,
        store,
        batch={POLL_KEY: 1},
        table=model_table,
        data_dir=tmp_path,
        now=next_now,
    )
    assert ran_again == ()
    assert model_ran == []
