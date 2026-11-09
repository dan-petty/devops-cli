"""The implement job keeps the phases that passed and the spend of a Job that was killed (#4070).

Git runs for real on a clone with an `origin`. The model is scripted, so the steps are real. GitHub's
REST API and `gh` are faked at their edges. A Job that is killed raises a `BaseException` from the
model: the pod is gone, so the job writes no stop and no comment.

The keys of the record are written as text here, so that a module without the keys still collects
and each test fails on its own assertion.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from enum import StrEnum
from pathlib import Path
from typing import Any

import pytest

from devops_cli.roadmap.implement.implement_pull import WatchKind, watch_pull
from devops_cli.roadmap.stores.store import ImplementRecordKey, ItemField, decode_job_record
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    FAIL,
    PASS,
    PULL,
    RUNNING,
    JobWorld,
    a_fix,
    group_one_calls,
    group_two_calls,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_REPO

pytestmark = pytest.mark.usefixtures("keyring_store")

MARKER = "<!-- devops roadmap implement -->"
RUN = "<!-- devops roadmap implement run: {job} -->"
JOB = "implement-example-roadmap-1-aaaaa"
NEXT_JOB = "implement-example-roadmap-1-bbbbb"
CHECKED = "implement.checked_sha"
PUBLISHED = "implement.published_sha"
SPEND = "implement.spend"
PRE_PUSH = "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD"
# Each scripted request counts 50 input tokens, so a group of two requests spends 100.
GROUP_TOKENS = 100
REQUEST_TOKENS = 50
OLD_SPEND = json.dumps(
    {
        "requests": 2,
        "input_tokens": GROUP_TOKENS,
        "output_tokens": 0,
        "steps": [{"step": "group 1", "first_request_tokens": REQUEST_TOKENS}],
        "tiers": {},
    }
)


class PodKilled(BaseException):
    """The pod of the Job is gone. No handler of the job sees it."""


@pytest.fixture
def job_world(job_world: JobWorld) -> JobWorld:
    """The job world, with the configuration of the hooks on `main` of `origin`, so that the scoped
    checks run the pre-push hook."""
    repo = job_world.repo
    (repo.clone / ".pre-commit-config.yaml").write_text(
        "repos:\n  - repo: local\n    hooks: []\n", encoding="utf-8"
    )
    (repo.clone / "tests").mkdir(exist_ok=True)
    (repo.clone / "tests" / "test_shout.py").write_text(
        "from devops_cli.shout import shout\n", encoding="utf-8"
    )
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Add the hooks and a test")
    repo.git("push", "-q", "origin", "main")
    return job_world


def _item(world: JobWorld) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(1)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


class Mark(StrEnum):
    """Marks of the record that a test writes as text, so that it needs no key of the job."""

    CHECKED = CHECKED
    PUBLISHED = PUBLISHED


def _mark(world: JobWorld, marks: Mapping[Any, str | None]) -> None:
    held = world.store.item(1)
    assert held is not None
    world.store.set_marks(held, marks)


def _continue(world: JobWorld, job: str = NEXT_JOB, *, retry: bool = False) -> None:
    """What happens after a Job ended. The Service records the next Job, clears the stop, and puts
    the item back to Ready. A person who retries comments `implement: retry` and the stop stays in
    the record until the next Job clears it."""
    marks: dict[Any, str | None] = {ImplementRecordKey.JOB: job}
    if not retry:
        marks[ImplementRecordKey.STOPPED] = None
        marks[ImplementRecordKey.FAILURE] = None
    _mark(world, marks)
    if retry:
        world.store.seed_comment(1, "implement: retry", author_association="OWNER")
    held = world.store.item(1)
    assert held is not None
    world.store.set_field(held, ItemField.STATUS, "Ready")


def _comment_calls(world: JobWorld) -> list[str]:
    """The methods of the requests that read, post or change a comment of the pull request."""
    return [
        entry.split(" ", 1)[0]
        for entry in world.api.requested
        if f"/issues/{PULL}/comments" in entry or "/issues/comments/" in entry
    ]


def _posted(world: JobWorld) -> list[str]:
    """The text of each comment that the job posted on the pull request."""
    return [str(sent["body"]) for sent in world.sent("POST", f"issues/{PULL}/comments")]


def _changed(world: JobWorld, comment: int = 1) -> list[str]:
    """The text of each change of comment `comment` of the pull request."""
    return [str(sent["body"]) for sent in world.sent("PATCH", f"issues/comments/{comment}")]


def _count(world: JobWorld, prefix: str) -> int:
    return sum(command_text(call).startswith(prefix) for call in world.programs.calls)


def _tip(world: JobWorld) -> str:
    return world.repo.origin_git("rev-parse", BRANCH)


def _kill_in_group_two(world: JobWorld) -> None:
    """Group 1 passes. The pod dies at the first request of group 2."""

    def die() -> None:
        raise PodKilled

    script = ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."), effects={3: die})
    with pytest.raises(PodKilled) as killed:
        world.run(script)
    assert killed.type is PodKilled


def _group_two() -> ModelScript:
    return ModelScript(tool_calls(*group_two_calls()), say("Group 2 is done."))


def _spend(world: JobWorld) -> dict[str, object]:
    text = _item(world)[1].get(SPEND)
    assert text, "the record holds no spend"
    spent: dict[str, object] = json.loads(text)
    return spent


# ── checked_sha ───────────────────────────────────────────────────────────────────────────


def test_checked_sha_is_the_head_that_passed_the_scoped_checks(job_world: JobWorld) -> None:
    job_world.pull.runs = [[RUNNING]]

    applied = job_world.run(two_groups())

    assert applied.stopped == (1,)
    assert _item(job_world)[1].get(CHECKED) == _tip(job_world)


def test_checked_sha_a_second_job_at_the_checked_head_runs_no_scoped_check(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[RUNNING]]
    job_world.run(two_groups())
    first = _count(job_world, PRE_PUSH)
    job_world.pull.runs = [[PASS]]
    _continue(job_world)

    applied = job_world.run(ModelScript())

    assert (first, applied.ready) == (1, (1,))
    assert _count(job_world, PRE_PUSH) == first


def test_checked_sha_of_another_head_runs_the_scoped_checks_again(job_world: JobWorld) -> None:
    job_world.pull.runs = [[RUNNING]]
    job_world.run(two_groups())
    first = _count(job_world, PRE_PUSH)
    _mark(job_world, {Mark.CHECKED: "0" * 40})
    job_world.pull.runs = [[PASS]]
    _continue(job_world)

    applied = job_world.run(ModelScript())

    assert applied.ready == (1,)
    assert _count(job_world, PRE_PUSH) == first + 1


def test_checked_sha_a_fix_after_a_failed_check_checks_the_new_head(job_world: JobWorld) -> None:
    job_world.pull.runs = [[FAIL], [PASS]]

    applied = job_world.run(two_groups(*a_fix()))

    assert applied.ready == (1,)
    assert _count(job_world, PRE_PUSH) == 2
    assert _item(job_world)[1].get(CHECKED) is None


# ── published_sha ─────────────────────────────────────────────────────────────────────────


def test_published_sha_is_the_head_that_the_job_pushed(job_world: JobWorld) -> None:
    job_world.pull.runs = [[RUNNING]]

    job_world.run(two_groups())

    assert _item(job_world)[1].get(PUBLISHED) == _tip(job_world)


def test_published_sha_a_second_job_at_the_published_head_pushes_nothing(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[RUNNING]]
    job_world.run(two_groups())
    tip = _tip(job_world)
    pushes = [call for call in job_world.programs.calls if "push" in call.argv]
    job_world.pull.runs = [[PASS]]
    _continue(job_world)

    applied = job_world.run(ModelScript())

    assert applied.ready == (1,)
    assert [call for call in job_world.programs.calls if "push" in call.argv] == pushes
    assert _tip(job_world) == tip
    assert _item(job_world)[1].get(PUBLISHED) is None


def test_published_sha_of_a_planned_item_is_the_head_of_its_draft(planned_world: JobWorld) -> None:
    planned_world.pull.runs = [[RUNNING]]

    planned_world.run(two_groups())

    assert _item(planned_world)[1].get(PUBLISHED) == _tip(planned_world)


def test_a_ready_item_keeps_neither_phase_mark(job_world: JobWorld) -> None:
    applied = job_world.run(two_groups())

    record = _item(job_world)[1]
    assert (applied.ready, record.get(CHECKED), record.get(PUBLISHED)) == ((1,), None, None)


def test_the_phase_marks_cost_one_write_each(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    written = [
        write.key
        for write in job_world.store.job_writes()
        if write.key in (CHECKED, PUBLISHED) and write.value is not None
    ]
    assert written == [CHECKED, PUBLISHED]


# ── pr_comment_marker ─────────────────────────────────────────────────────────────────────


def test_pr_comment_marker_the_comment_names_the_run(job_world: JobWorld) -> None:
    _mark(job_world, {ImplementRecordKey.JOB: JOB})

    job_world.run(two_groups())

    (comment,) = _posted(job_world)
    assert comment.splitlines()[:2] == [MARKER, RUN.format(job=JOB)]


def test_pr_comment_marker_a_run_with_no_job_record_has_the_marker_of_a_manual_run(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    (comment,) = _posted(job_world)
    assert comment.splitlines()[:2] == [MARKER, RUN.format(job="manual")]


def test_pr_comment_marker_a_repair_round_updates_the_comment_of_the_run(
    job_world: JobWorld,
) -> None:
    _mark(job_world, {ImplementRecordKey.JOB: JOB})
    job_world.pull.runs = [[FAIL], [PASS]]

    applied = job_world.run(two_groups(*a_fix()))

    (posted,) = _posted(job_world)
    (changed,) = _changed(job_world)
    assert applied.ready == (1,)
    assert posted.splitlines()[:2] == changed.splitlines()[:2] == [MARKER, RUN.format(job=JOB)]
    assert "| group 1 | done |" in changed
    assert "| fix | done |" in changed


@pytest.mark.parametrize("same_run", [True, False], ids=["same run", "next run"])
def test_pr_comment_marker_a_rerun_with_no_new_outcome_posts_no_empty_comment(
    job_world: JobWorld, same_run: bool
) -> None:
    _mark(job_world, {ImplementRecordKey.JOB: JOB})
    job_world.pull.runs = [[RUNNING]]
    job_world.run(two_groups())
    (first,) = _posted(job_world)
    job_world.pull.comments({"id": 77, "body": first, "user": {"login": "example-app[bot]"}})
    job_world.pull.runs = [[PASS]]
    _continue(job_world, JOB if same_run else NEXT_JOB)

    applied = job_world.run(ModelScript())

    assert applied.ready == (1,)
    assert _posted(job_world) == [first]
    assert all("| group 1 | done |" in body for body in _changed(job_world, 77))
    assert not any(
        body.rstrip().endswith("\n-") for body in [*_posted(job_world), *_changed(job_world, 77)]
    )


def test_pr_comment_marker_a_next_run_posts_its_own_comment_for_its_own_outcomes(
    job_world: JobWorld,
) -> None:
    """Group 1 passes in the first Job, which is killed. The second Job runs group 2 and posts
    one comment with the marker of its own run, which holds the row of group 2 only."""
    _mark(job_world, {ImplementRecordKey.JOB: JOB})
    _kill_in_group_two(job_world)
    _continue(job_world)

    applied = job_world.run(_group_two())

    (comment,) = _posted(job_world)
    assert applied.ready == (1,)
    assert comment.splitlines()[:2] == [MARKER, RUN.format(job=NEXT_JOB)]
    assert ("| group 2 | done |" in comment, "| group 1 |" in comment) == (True, False)


# ── spend_survives_kill ───────────────────────────────────────────────────────────────────


def test_spend_survives_kill_the_mark_of_a_passed_group_holds_the_spend(
    job_world: JobWorld,
) -> None:
    _kill_in_group_two(job_world)

    spend = _spend(job_world)

    assert (spend["requests"], spend["input_tokens"]) == (2, GROUP_TOKENS)


def test_spend_survives_kill_a_continuation_stops_at_the_item_budget_as_a_sum(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """The budget is 150. Group 1 spent 100 in the killed Job. A Job that starts from zero would
    spend 100 on group 2 and finish. A Job that starts from the recorded 100 has spent 150 after
    its first request, so it makes no second request."""
    config(roadmap={"implement": {"item_token_budget": 150}})
    _kill_in_group_two(job_world)
    _continue(job_world)
    script = _group_two()

    applied = job_world.run(script)

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.failure")) == (
        (1,),
        "Blocked",
        "limit_reached",
    )
    assert len(script.seen) == 1


def test_spend_survives_kill_a_stop_writes_the_sum_of_the_jobs(job_world: JobWorld) -> None:
    _kill_in_group_two(job_world)
    _continue(job_world)

    applied = job_world.run(ModelScript(say("I could not do group 2.")))

    spend = _spend(job_world)
    assert applied.stopped == (1,)
    assert (spend["requests"], spend["input_tokens"]) == (3, GROUP_TOKENS + REQUEST_TOKENS)


def test_spend_survives_kill_ready_writes_the_sum_of_the_jobs(job_world: JobWorld) -> None:
    _kill_in_group_two(job_world)
    _continue(job_world)

    applied = job_world.run(_group_two())

    spend = _spend(job_world)
    steps = spend["steps"]
    assert isinstance(steps, list)
    assert applied.ready == (1,)
    assert (spend["requests"], spend["input_tokens"]) == (4, 2 * GROUP_TOKENS)
    assert [step["step"] for step in steps] == ["group 1", "group 2"]
    assert "4 model requests" in job_world.issue_comments()[0]


def test_spend_survives_kill_a_retry_of_a_person_starts_from_zero(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """A stop on the budget is retried by a person, so the retry must not stop at once again."""
    config(roadmap={"implement": {"item_token_budget": 200}})
    job_world.run(ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."), say("No.")))
    assert _spend(job_world)["input_tokens"] == GROUP_TOKENS + REQUEST_TOKENS
    _continue(job_world, retry=True)

    applied = job_world.run(_group_two())

    assert applied.ready == (1,)
    assert (_spend(job_world)["requests"], _spend(job_world)["input_tokens"]) == (2, GROUP_TOKENS)


def test_spend_survives_kill_a_retry_of_a_person_clears_the_counted_spend(
    job_world: JobWorld,
) -> None:
    """The retry starts the spend from zero, so the count of the spend starts from zero too, or the
    first report after the retry would count too little (#4200)."""
    _kill_in_group_two(job_world)
    _mark(job_world, {ImplementRecordKey.SPEND_COUNTED: str(GROUP_TOKENS + REQUEST_TOKENS)})
    _continue(job_world, retry=True)

    job_world.run(_group_two())

    assert _item(job_world)[1].get("implement.spend_counted") is None


def test_spend_survives_kill_a_record_of_an_older_version_gives_its_spend(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    """The record holds the spend as an earlier version wrote it, and none of the phase marks."""
    config(roadmap={"implement": {"item_token_budget": 150}})
    _mark(job_world, {ImplementRecordKey.SPEND: OLD_SPEND})
    assert {CHECKED, PUBLISHED}.isdisjoint(_item(job_world)[1])
    script = two_groups()

    applied = job_world.run(script)

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.failure")) == (
        (1,),
        "Blocked",
        "limit_reached",
    )
    assert len(script.seen) == 1


def test_a_return_to_new_clears_the_spend(job_world: JobWorld) -> None:
    premise = (
        "```plan-request\n"
        '{"kind": "premise", "group": 2, "defect": "the premise is false", '
        '"evidence": "upstream removed the API"}\n'
        "```"
    )

    applied = job_world.run(
        ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."), say(premise))
    )

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get(SPEND)) == ((), "New", None)


def test_a_return_to_new_clears_the_counted_spend(job_world: JobWorld) -> None:
    _mark(job_world, {ImplementRecordKey.SPEND_COUNTED: "100"})
    premise = (
        "```plan-request\n"
        '{"kind": "premise", "group": 2, "defect": "the premise is false", '
        '"evidence": "upstream removed the API"}\n'
        "```"
    )

    job_world.run(
        ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."), say(premise))
    )

    assert _item(job_world)[1].get("implement.spend_counted") is None


# ── watch_progress_line ───────────────────────────────────────────────────────────────────


def test_watch_progress_line_the_watch_writes_a_line_at_each_interval(
    job_world: JobWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    """A check runs for the first three waits of 30 seconds, and ends at the fourth poll."""
    job_world.pull.runs = [[RUNNING]]
    waits: list[float] = []

    def settle() -> None:
        waits.append(1)
        if len(waits) == 3:
            job_world.pull.runs = [[PASS]]

    job_world.clock.after_each_sleep(settle)

    watch = watch_pull(STAGE_REPO, PULL, _tip(job_world))

    shown = capsys.readouterr()
    lines = [
        line for line in (shown.out + shown.err).splitlines() if f"pull request #{PULL}" in line
    ]
    assert watch.kind is WatchKind.READY
    assert lines == [
        f"The checks of pull request #{PULL} still run after 30 s.",
        f"The checks of pull request #{PULL} still run after 60 s.",
    ]


def test_watch_progress_line_a_watch_that_ends_at_the_first_poll_writes_none(
    job_world: JobWorld, capsys: pytest.CaptureFixture[str]
) -> None:
    watch = watch_pull(STAGE_REPO, PULL, _tip(job_world))

    shown = capsys.readouterr()
    assert watch.kind is WatchKind.READY
    assert f"pull request #{PULL}" not in shown.out + shown.err


# ── request_count ─────────────────────────────────────────────────────────────────────────


def test_request_count_the_comment_costs_one_read_and_one_write(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    assert _comment_calls(job_world) == ["GET", "POST"]


def test_request_count_a_repair_round_reads_the_comments_once_and_changes_the_comment(
    job_world: JobWorld,
) -> None:
    job_world.pull.runs = [[FAIL], [PASS]]

    job_world.run(two_groups(*a_fix()))

    assert _comment_calls(job_world) == ["GET", "POST", "PATCH"]


def test_request_count_the_marker_and_the_two_phase_marks_cost_at_most_five_requests(
    job_world: JobWorld,
) -> None:
    """One read of the comments, and for each phase mark a read of the item and a write."""
    job_world.run(two_groups())

    reads = _comment_calls(job_world).count("GET")
    marks = [
        write
        for write in job_world.store.job_writes()
        if write.key in (CHECKED, PUBLISHED) and write.value is not None
    ]
    assert reads + 2 * len(marks) <= 5
    assert (reads, len(marks)) == (1, 2)


# ── The record ────────────────────────────────────────────────────────────────────────────


def test_a_record_of_an_older_version_decodes_with_no_phase_mark() -> None:
    held = {"implement.group": "2", "implement.sha": "a" * 40, SPEND: OLD_SPEND}

    assert decode_job_record(held) == held


def test_the_phase_marks_are_kept_by_a_read_of_the_record() -> None:
    held = {CHECKED: "a" * 40, PUBLISHED: "b" * 40}

    assert decode_job_record(held) == held
