"""`devops roadmap explain`: why each job takes an item or leaves it out (#2911). Git runs for real
on a clone with an `origin`, and GitHub is faked."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.config import settings
from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_FILE_MAX_TOKENS,
    CONST_ROADMAP_REFINE_COMMENT_MARKER,
    CONST_ROADMAP_STAGE_COMMENT_MARKER,
)
from devops_cli.exceptions.roadmap import RoadmapImplementError
from devops_cli.git import worktree_add
from devops_cli.lang import MESSAGES
from devops_cli.roadmap import planned
from devops_cli.roadmap.body_hash import body_hashes, hash_text
from devops_cli.roadmap.explain import (
    Explanation,
    JobVerdict,
    explain_item,
    read_trace,
    render_explanation,
    render_trace,
)
from devops_cli.roadmap.implement.implement import parse_implement_filters
from devops_cli.roadmap.implement.implement_trace import ImplementTrace
from devops_cli.roadmap.stage.stage import parse_filters
from devops_cli.roadmap.stage.stage_rejected import RejectedPlan
from devops_cli.roadmap.stores.store import (
    GitHubState,
    ImplementRecordKey,
    ItemField,
    RefineRecordKey,
    StageRecordKey,
)
from tests.support.roadmap_implement import (
    TITLE,
    JobWorld,
    long_run_trace,
    push_staged_branch,
    route_pull_status,
    seed_staged,
)
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
    planned_limit: int | None = None,
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
        planned_limit=planned_limit,
    )


def test_an_item_of_high_effort_names_the_filter_family_and_the_values_it_takes(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world, labels=("type/bug", "effort/high"), status="Planned")

    explained = _explain(job_world, number)

    assert explained.implement == JobVerdict(
        False, "The filter takes effort low or medium. The item has effort high."
    )
    assert explained.stage == JobVerdict(
        False, "The filter takes status ready. The item has status planned."
    )


def test_explain_names_the_effort_set_and_whether_the_fallback_applies(
    job_world: JobWorld,
) -> None:
    job_world.store.add_label(job_world.number, "owner/agent")
    medium = seed_staged(job_world.store, labels=("type/bug", "effort/medium"), pull=6)
    push_staged_branch(job_world.repo, number=medium)
    route_pull_status(job_world.api, pull=6)

    explained = _explain(job_world, medium)
    line = TEXTS.explain_effort_line.format(
        efforts="low,medium", state=TEXTS.explain_effort_applies
    )

    assert (explained.implement, explained.implement_effort) == (JobVerdict(True), line)
    lines = render_explanation(explained).splitlines()
    assert lines[-2] == line
    assert lines[-1] == (f"Issue #{medium} has no recorded implement run, so it has no totals.")


def test_a_medium_effort_item_waits_for_the_low_effort_item_that_the_run_takes(
    job_world: JobWorld,
) -> None:
    medium = seed_staged(job_world.store, labels=("type/bug", "effort/medium"), pull=6)
    push_staged_branch(job_world.repo, number=medium)
    route_pull_status(job_world.api, pull=6)

    explained = _explain(job_world, medium)

    assert (explained.implement, explained.implement_effort) == (
        JobVerdict(False, TEXTS.implement_job_effort_later.format(effort="low")),
        TEXTS.explain_effort_line.format(
            efforts="low,medium", state=TEXTS.explain_effort_not_applies
        ),
    )


def test_the_fallback_does_not_apply_to_a_medium_effort_item_when_no_pass_takes_an_item(
    job_world: JobWorld,
) -> None:
    job_world.store.add_label(job_world.number, "owner/agent")
    medium = _seed(job_world, labels=("type/bug", "effort/medium"))

    explained = _explain(job_world, medium)

    assert explained.implement_effort == TEXTS.explain_effort_line.format(
        efforts="low,medium", state=TEXTS.explain_effort_not_applies
    )


def test_the_effort_line_says_the_set_does_not_apply_when_the_filter_names_effort(
    job_world: JobWorld,
) -> None:
    explained = _explain(job_world, job_world.number, implement=("effort=low",))

    assert explained.implement_effort == TEXTS.explain_effort_explicit


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


def test_a_rejected_plan_is_the_reason_of_the_stage_job_and_names_the_pull_request(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world)
    held = job_world.store.item(number)
    assert held is not None
    rejected = RejectedPlan(
        pull=7,
        text_hash=body_hashes(held.body)[0],
        closed_at=datetime(2026, 11, 2, 20, 22, 45, tzinfo=UTC),
    )
    job_world.store.set_marks(held, {StageRecordKey.REJECTED: rejected.record})

    explained = _explain(job_world, number)

    assert explained.stage == JobVerdict(False, TEXTS.stage_left_rejected.format(pull=7))
    assert "#7" in explained.stage.reason


def test_a_repository_without_openspec_is_the_reason_of_the_stage_job(
    job_world: JobWorld,
) -> None:
    """The stage job holds each item of a repository whose default branch has no
    `openspec/config.yaml`, and explain prints that reason (#4629)."""
    job_world.repo.untrack("openspec/config.yaml")
    number = _seed(job_world)

    explained = _explain(job_world, number)

    assert explained.stage == JobVerdict(
        False, TEXTS.stage_left_no_openspec.format(path="openspec/config.yaml", branch="main")
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


def test_the_planned_limit_names_the_setting_and_the_count_for_the_stage_job(
    job_world: JobWorld,
) -> None:
    _seed(job_world, status="Planned", title="fix(roadmap): a first plan waits")
    _seed(job_world, status="Planned", title="fix(roadmap): a second plan waits")
    number = _seed(job_world, priority="P2-Medium")

    held = _explain(job_world, number, planned_limit=2)
    free = _explain(job_world, number, planned_limit=3)

    assert held.stage == JobVerdict(
        False,
        TEXTS.stage_left_planned_limit.format(
            count=2, limit=2, priorities="P0-Critical or P1-High"
        ),
    )
    assert "roadmap.stage.planned_limit" in held.stage.reason
    assert "The count of Planned items is 2" in held.stage.reason
    assert "P0-Critical or P1-High" in held.stage.reason
    assert free.stage == JobVerdict(True)


def test_a_p1_item_passes_the_planned_limit_for_the_stage_job(job_world: JobWorld) -> None:
    _seed(job_world, status="Planned", title="fix(roadmap): a first plan waits")
    number = _seed(job_world, priority="P1-High")

    assert _explain(job_world, number, planned_limit=1).stage == JobVerdict(True)


def test_the_planned_limit_is_the_setting_when_the_option_is_absent(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEVOPS_CLI_ROADMAP_STAGE_PLANNED_LIMIT", "1")
    settings.reset_settings_cache()
    _seed(job_world, status="Planned", title="fix(roadmap): a first plan waits")
    number = _seed(job_world, priority="P2-Medium")

    explained = _explain(job_world, number)

    assert explained.stage.reason == TEXTS.stage_left_planned_limit.format(
        count=1, limit=1, priorities="P0-Critical or P1-High"
    )


def test_the_staged_item_is_taken_by_the_implement_job(job_world: JobWorld) -> None:
    explained = _explain(job_world, job_world.number)

    assert explained.implement == JobVerdict(True)


def test_explain_calls_no_model_and_writes_nothing(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: object, **__: object) -> None:
        raise AssertionError("explain called a model")

    monkeypatch.setattr("devops_cli.roadmap.stage.stage.get_llm_client", refuse)
    number = _seed(job_world)
    before = (job_world.store.job_writes, job_world.store.comments_on(number))

    _explain(job_world, number)
    _explain(job_world, job_world.number)

    assert (job_world.store.job_writes, job_world.store.comments_on(number)) == before


def test_explain_reads_the_branches_and_the_plans_once_for_both_jobs(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dry run lists each git read once, so a real run reads each once (#2911)."""
    reads: list[str] = []
    run, git = worktree_add._run, planned.git

    def counting_run(argv: list[str]) -> str:
        reads.extend(arg for arg in argv if arg == "ls-remote")
        return run(argv)

    def counting_git(source: Path, *args: str, operation: str) -> str:
        reads.extend(arg for arg in args[:1] if arg in {"fetch", "ls-tree"})
        return git(source, *args, operation=operation)

    monkeypatch.setattr(worktree_add, "_run", counting_run)
    monkeypatch.setattr(planned, "git", counting_git)

    _explain(job_world, _seed(job_world))

    assert sorted(reads) == ["fetch", "ls-remote", "ls-tree"]


def test_the_report_gives_yes_or_no_for_each_job_and_the_reason_of_a_no() -> None:
    explained = Explanation(
        STAGE_REPO,
        7,
        TITLE,
        JobVerdict(False, "The item waits on a person. Reply."),
        JobVerdict(False, "It is claimed by human."),
        JobVerdict(True),
    )

    assert render_explanation(explained).splitlines() == [
        f"# {STAGE_REPO} #7: {TITLE}",
        "",
        "Refine job: no. The item waits on a person. Reply.",
        "Stage job: no. It is claimed by human.",
        "Implement job: yes.",
        "Issue #7 has no recorded implement run, so it has no totals.",
    ]


# ── The cause of a refine wait (#3483) ───────────────────────────────────────────────────


def _refine_wait(world: JobWorld, number: int, step: str, text: str) -> None:
    """Record a refine round that left the item waiting on `step`, with `text` in its comment."""
    held = world.store.item(number)
    assert held is not None
    world.store.set_marks(
        held,
        {RefineRecordKey.BODY_HASH: hash_text(held.body), RefineRecordKey.NEXT_STEP: step},
    )
    world.store.seed_comment(number, f"{CONST_ROADMAP_REFINE_COMMENT_MARKER}\n{text}")


def test_an_item_that_waits_on_a_person_names_the_wait_and_what_ends_it(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world, status="New")
    _refine_wait(job_world, number, "person", "- Which store holds the record?")

    explained = _explain(job_world, number)

    assert explained.refine == JobVerdict(
        False,
        "The item waits on a person. " + TEXTS.refine_left_person_hint,
    )


def test_an_item_that_the_stage_job_returned_twice_names_the_cause(job_world: JobWorld) -> None:
    number = _seed(job_world, status="New")
    held = job_world.store.item(number)
    assert held is not None
    hashed = hash_text(held.body)
    job_world.store.set_marks(
        held,
        {
            RefineRecordKey.BODY_HASH: hashed,
            RefineRecordKey.NEXT_STEP: "ready",
            RefineRecordKey.RETURNED_BODY_HASH: hashed,
        },
    )
    job_world.store.seed_comment(number, f"{CONST_ROADMAP_REFINE_COMMENT_MARKER}\nReady.")
    job_world.store.seed_comment(number, f"{CONST_ROADMAP_STAGE_COMMENT_MARKER}\nReturned.")

    explained = _explain(job_world, number)

    assert explained.refine == JobVerdict(
        False, "The item waits on a person. " + TEXTS.refine_stage_returned_twice
    )


def test_a_new_item_with_no_round_is_taken_and_a_ready_item_is_not(job_world: JobWorld) -> None:
    new = _seed(job_world, status="New")
    ready = _seed(job_world, status="Ready")
    refined = job_world.store.item(ready)
    assert refined is not None
    job_world.store.set_marks(
        refined, {RefineRecordKey.SECTION_HASH: "section", RefineRecordKey.BODY_HASH: "body"}
    )

    assert (_explain(job_world, new).refine, _explain(job_world, ready).refine) == (
        JobVerdict(True),
        JobVerdict(False, TEXTS.refine_left_ready),
    )


# ── The trace of the last run (#3032) ─────────────────────────────────────────────────────


def _record_trace(world: JobWorld, number: int, text: str) -> None:
    item = world.store.item(number)
    assert item is not None
    world.store.set_marks(item, {ImplementRecordKey.TRACE: text})


def test_the_trace_of_an_item_gives_one_line_for_each_event_in_order(job_world: JobWorld) -> None:
    number = _seed(job_world)
    trace = ImplementTrace(step="group 1")
    trace.model_call("model-a", 100, 20, 1.5)
    trace.tool_call("shell", "ruff", "abc123abc123", "refused")
    trace.check("ruff check .", 1)
    _record_trace(job_world, number, trace.encode())
    before = (job_world.store.job_writes, job_world.store.comments_on(number))

    report = render_trace(read_trace(job_world.store, number), number=number)

    lines = report.splitlines()
    assert len(lines) == 3
    assert lines[0] == "group 1: model model-a, 100/20 tokens, 1.5 s"
    assert lines[1] == "group 1: tool shell (program ruff) [argument abc123abc123], refused"
    assert lines[2] == "group 1: check ruff check ., exit status 1"
    assert (job_world.store.job_writes, job_world.store.comments_on(number)) == before


def test_a_shell_call_with_an_exit_status_shows_it_in_the_line(job_world: JobWorld) -> None:
    """#4393: the line of a tool call shows the digest of its argument, so a reader sees that the
    model made the same call twice, and the exit status of a shell call."""
    number = _seed(job_world)
    trace = ImplementTrace(step="group 1")
    trace.tool_call("shell", "git", "abc123abc123", "ok", status=128)
    trace.tool_call("shell", "git", "abc123abc123", "ok", status=0)
    _record_trace(job_world, number, trace.encode())

    report = render_trace(read_trace(job_world.store, number), number=number)

    assert report.splitlines() == [
        "group 1: tool shell (program git) [argument abc123abc123], ok (exit status 128)",
        "group 1: tool shell (program git) [argument abc123abc123], ok (exit status 0)",
    ]


def test_a_tool_call_with_no_digest_shows_no_argument(job_world: JobWorld) -> None:
    number = _seed(job_world)
    _record_trace(
        job_world,
        number,
        '{"events":[{"kind":"tool","step":"g","tool":"edit_file","outcome":"ok"}],"dropped":0}',
    )

    report = render_trace(read_trace(job_world.store, number), number=number)

    assert report.splitlines() == ["g: tool edit_file, ok"]


def test_the_trace_says_how_many_earlier_events_the_bound_dropped(job_world: JobWorld) -> None:
    number = _seed(job_world)
    _record_trace(job_world, number, '{"events":[],"dropped":12}')

    report = render_trace(read_trace(job_world.store, number), number=number)

    assert report == "12 earlier event(s) are not kept."


def test_an_item_with_no_trace_says_so(job_world: JobWorld) -> None:
    number = _seed(job_world)

    trace = read_trace(job_world.store, number)

    assert trace is None
    assert render_trace(trace, number=number) == f"Issue #{number} has no trace of a run."


def test_a_trace_that_is_not_json_raises_an_error_that_names_the_key(job_world: JobWorld) -> None:
    number = _seed(job_world)
    _record_trace(job_world, number, "not json")

    with pytest.raises(RoadmapImplementError, match=r"implement\.trace"):
        read_trace(job_world.store, number)


def test_a_trace_read_reads_the_one_issue_once(
    job_world: JobWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    number = _seed(job_world)
    reads: list[int] = []
    item = job_world.store.item
    monkeypatch.setattr(job_world.store, "item", lambda n: (reads.append(n), item(n))[1])

    read_trace(job_world.store, number)

    assert reads == [number]


# ── The totals of the last run (#3217) ────────────────────────────────────────────────────


def _totals_trace() -> ImplementTrace:
    """The trace of a run with one model event and two attempts: a failed one that a repair
    round follows, and a passed one that ends the step."""
    trace = ImplementTrace(step="group 1")
    trace.model_call("model-a", 1200, 300, 90.0)
    trace.attempt(1, "standard", "check_failed", "ruff check . exited 1", repair=True)
    trace.attempt(2, "standard", "", "", repair=False)
    return trace


def test_the_totals_of_the_last_run_sum_the_tokens_the_seconds_and_the_outcomes(
    job_world: JobWorld,
) -> None:
    number = _seed(job_world)
    _record_trace(job_world, number, _totals_trace().encode())

    explained = _explain(job_world, number)

    totals = getattr(explained, "totals", None)
    assert totals is not None, "the explanation gives no totals of the last run"
    assert (
        totals.tokens_total,
        totals.seconds_total,
        totals.repair_rounds,
        totals.outcomes,
        totals.dropped,
    ) == (1500, 90.0, 1, {"failed": 1, "passed": 1}, 0)


def test_the_report_names_the_totals_of_the_last_run(job_world: JobWorld) -> None:
    number = _seed(job_world)
    _record_trace(job_world, number, _totals_trace().encode())

    report = render_explanation(_explain(job_world, number))

    assert report.splitlines()[-1] == (
        "Last implement run: 1500 tokens, 90.0 s, 1 repair round(s), 1 failed and 1 passed "
        "outcome(s)."
    )
    assert "1 repair round" in report


def test_the_report_names_the_events_that_the_bound_dropped_beside_the_totals(
    job_world: JobWorld,
) -> None:
    """#4457: the trace holds the sums of its dropped events, so the totals include them."""
    number = _seed(job_world)
    _record_trace(job_world, number, '{"events":[],"dropped":12,"dropped_tokens":100}')

    report = render_explanation(_explain(job_world, number))

    assert report.splitlines()[-1] == (
        "12 earlier event(s) are not kept in the trace, and the totals include them."
    )


def test_the_report_of_a_trace_with_no_dropped_sums_says_that_the_totals_leave_them_out(
    job_world: JobWorld,
) -> None:
    """#4457: a trace from before the sums holds only the count of its dropped events, so the
    totals leave them out."""
    number = _seed(job_world)
    _record_trace(job_world, number, '{"events":[],"dropped":12}')

    report = render_explanation(_explain(job_world, number))

    assert report.splitlines()[-1] == (
        "12 earlier event(s) are not kept in the trace, and the totals leave them out."
    )


def test_the_totals_of_a_long_run_count_the_events_that_the_bound_dropped(
    job_world: JobWorld,
) -> None:
    """#4457: the bound drops every model event of a long run, and the totals still give the
    tokens and the seconds of the full run."""
    number = _seed(job_world)
    trace = long_run_trace()
    _record_trace(job_world, number, trace.encode())

    totals = _explain(job_world, number).totals

    assert totals is not None
    assert totals.dropped > 0
    assert (
        totals.tokens_total,
        totals.seconds_total,
        totals.repair_rounds,
        totals.outcomes,
    ) == (2_030_000, 400.0, 0, {"failed": 1})


def test_an_item_with_no_recorded_run_says_so_and_gives_no_totals(job_world: JobWorld) -> None:
    number = _seed(job_world)

    explained = _explain(job_world, number)

    assert getattr(explained, "totals", None) is None
    assert render_explanation(explained).splitlines()[-1] == (
        f"Issue #{number} has no recorded implement run, so it has no totals."
    )


def test_a_trace_that_is_not_json_stops_the_report_and_names_the_key(job_world: JobWorld) -> None:
    number = _seed(job_world)
    _record_trace(job_world, number, "not json")

    with pytest.raises(RoadmapImplementError, match=r"implement\.trace"):
        _explain(job_world, number)
