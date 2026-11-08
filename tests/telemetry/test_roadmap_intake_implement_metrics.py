"""The outcome of each intake candidate and the seconds of the implement steps (#4067).

Intake. `apply_intake` adds 1 to `devops_cli_roadmap_intake_candidates_total` for each candidate,
under `repo` and `result`: `placed`, `duplicate`, `skipped` or `failed`. The row sends 0 for the
four results of its repository before the first candidate.

Implement. The job sends one sample of `devops_cli_roadmap_step_seconds` with the row `implement`
for each call of the scoped checks, of the publish step and of the watch of the pull request
checks, with the steps `checks`, `publish` and `watch`. The label scheme is the one of the stage
row (#4066).

The intake rounds run over `Roadmap`, the in-memory store, and the implement runs over `job_world`,
where git runs for real and the project's commands and GitHub are faked at their edges. A command
moves the fake clock by a set number of seconds, so a sample holds a value that the test knows. The
collector is the fake of the OTLP fixture. The instruments are read inside the tests that need
them: the fail-to-pass replay loads this module against a base tree that does not declare them.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.exceptions import RoadmapIntakeError
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.exceptions.roadmap import RoadmapItemChangedError
from devops_cli.roadmap.failure import StepName
from devops_cli.roadmap.intake.intake import apply_intake, raise_for_failed_placements
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import command_text, git_for_real
from tests.support.model_script import say, tool_calls
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import (
    FAIL,
    PASS,
    SHOUT,
    JobWorld,
    two_groups,
)
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
from tests.support.roadmap_stage import STAGE_REPO

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

INTAKE_CANDIDATES = "devops_cli_roadmap_intake_candidates_total"
STEP_SECONDS = "devops_cli_roadmap_step_seconds"
INTAKE_RESULTS = {"placed", "duplicate", "skipped", "failed"}
IMPLEMENT_STEPS = {"checks", "publish", "watch"}
CHECK_SECONDS = 10.0
PUSH_SECONDS = 2.0

STATIC = "uv run devops ci --check --only constructs,docs,openspec"
PRE_PUSH = "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD"
CONFIG = ".pre-commit-config.yaml"
HOOKS = "repos:\n  - repo: local\n    hooks: []\n"
TEST_MODULE = "tests/test_shout.py"

Sample = tuple[dict[str, Any], int, float]


# ── Intake ────────────────────────────────────────────────────────────────────


def _outcomes(otlp: FakeCollector) -> dict[str, float]:
    """The sum of the counter for each `result`, after a check that every point holds the labels
    `repo` and `result` and no other, and that the repository is the one of the round."""
    points = otlp.points(INTAKE_CANDIDATES)
    assert {tuple(sorted(attrs)) for attrs, _ in points} <= {("repo", "result")}
    assert {attrs["repo"] for attrs, _ in points} <= {REPO}
    found: dict[str, float] = {}
    for attrs, value in points:
        found[attrs["result"]] = found.get(attrs["result"], 0.0) + value
    return found


def _four_candidates(roadmap: Roadmap) -> tuple[FakeModel, int]:
    """One candidate for each result. `placed` is placed. `duplicate` is placed too, with the
    model naming `placed` as its possible original. `skipped` has a proposal off the lists. The
    write of `failed` fails. The model and the number of the candidate whose write fails."""
    roadmap.issue("Cache embeddings")
    roadmap.issue("Keep embeddings cached")
    roadmap.issue("Odd proposal")
    failing = roadmap.issue("Write refused")
    model = FakeModel(
        duplicates={"Keep embeddings cached": "Cache embeddings"},
        proposals={"Odd proposal": {"value": "Enormous"}},
    )
    return model, failing


def test_intake_outcome_each_candidate_counts_once_under_its_result(
    roadmap: Roadmap, otlp: FakeCollector
) -> None:
    """Four candidates give the four results, and the counter holds 1 for each, under the
    repository of the round."""
    model, failing = _four_candidates(roadmap)
    roadmap.store.fail_write(write="set_field", item=failing)
    plan = roadmap.plan(model)

    applied = apply_intake(roadmap.store, plan, repo=REPO)

    assert (len(applied.failed), _outcomes(otlp)) == (
        1,
        {"placed": 1.0, "duplicate": 1.0, "skipped": 1.0, "failed": 1.0},
    )


def test_intake_outcome_a_possible_duplicate_is_placed_and_counts_once_as_duplicate(
    roadmap: Roadmap, otlp: FakeCollector
) -> None:
    """The verdict of the model only flags the candidate (the owner rule of 2026-10-25): intake
    still places it, and the candidate counts under `duplicate` and not under `placed`."""
    original = roadmap.finished("Cache embeddings")
    copy = roadmap.issue("Keep embeddings cached")
    plan = roadmap.plan(FakeModel(duplicates={"Keep embeddings cached": "Cache embeddings"}))

    apply_intake(roadmap.store, plan, repo=REPO)

    (decision,) = plan.decisions
    assert (decision.possible_duplicate, roadmap.fields(copy)[0], original != copy) == (
        original,
        "New",
        True,
    )
    assert _outcomes(otlp) == {"placed": 0.0, "duplicate": 1.0, "skipped": 0.0, "failed": 0.0}


def test_intake_outcome_an_item_a_person_changed_counts_as_skipped_and_not_as_failed(
    roadmap: Roadmap, otlp: FakeCollector
) -> None:
    """The write refuses before it changes anything, and the next plan decides the candidate
    again: it is skipped and not failed (#4042)."""
    first = roadmap.issue("feat: first")
    changed = roadmap.issue("feat: changed")
    roadmap.store.fail_write(
        write="set_field",
        item=changed,
        error=RoadmapItemChangedError(f"#{changed}'s Status changed since the plan."),
    )
    plan = roadmap.plan(FakeModel())

    applied = apply_intake(roadmap.store, plan, repo=REPO)

    assert (applied.placed, applied.failed, roadmap.fields(first)[0]) == (1, (), "New")
    assert _outcomes(otlp) == {"placed": 1.0, "duplicate": 0.0, "skipped": 1.0, "failed": 0.0}


def test_intake_outcome_a_rate_limit_ends_the_round_and_counts_the_candidates_that_were_written(
    roadmap: Roadmap, otlp: FakeCollector
) -> None:
    """Every later write would be refused too (#983), so the error goes on and the candidates
    after it count nothing."""
    for n in range(3):
        roadmap.issue(f"feat: candidate {n}")
    plan = roadmap.plan(FakeModel())
    refused = plan.decisions[1].subject.number
    roadmap.store.fail_write(
        write="set_field", item=refused, error=GitHubRateLimitError("No requests are left.")
    )

    with pytest.raises(GitHubRateLimitError, match="No requests are left"):
        apply_intake(roadmap.store, plan, repo=REPO)

    assert _outcomes(otlp) == {"placed": 1.0, "duplicate": 0.0, "skipped": 0.0, "failed": 0.0}


def test_intake_outcome_the_failed_count_matches_the_failed_placements_of_the_error(
    roadmap: Roadmap, otlp: FakeCollector
) -> None:
    """The counter and the error that names the failed candidates agree."""
    roadmap.issue("feat: fine")
    failing = roadmap.issue("feat: refused")
    roadmap.store.fail_write(write="set_field", item=failing, error=GitHubOperationError("422"))
    plan = roadmap.plan(FakeModel())

    applied = apply_intake(roadmap.store, plan, repo=REPO)
    with pytest.raises(RoadmapIntakeError) as raised:
        raise_for_failed_placements(applied)

    assert raised.value.failed_items == [failing]
    assert _outcomes(otlp)["failed"] == float(len(applied.failed))


def _round(store: InMemoryRoadmapStore, tmp_path: Path) -> None:
    """Run the intake row of the Service over `store`."""
    repo_dir = tmp_path / REPO_DIR
    repo_dir.mkdir(parents=True)
    run_intake_adapter(store=store, repo=REPO, repo_dir=repo_dir, now=NOW, model=IntakeModel())


def _store(*candidates: str) -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(clock=Clock())
    store.seed_file(".github/labels.yml", (REPO_ROOT / ".github" / "labels.yml").read_text("utf-8"))
    store.seed_milestone(PLANNED)
    for title in candidates:
        store.seed_issue(title)
    return store


def test_intake_outcome_a_round_with_no_candidate_sends_zero_for_the_four_results(
    tmp_path: Path, otlp: FakeCollector
) -> None:
    """The series of a repository exist before its first candidate, so a rate or an increase
    query finds them. A round that decides nothing sends the four zeros."""
    _round(_store(), tmp_path)

    assert _outcomes(otlp) == {"placed": 0.0, "duplicate": 0.0, "skipped": 0.0, "failed": 0.0}


def test_intake_outcome_a_round_that_places_one_candidate_holds_zero_for_the_other_results(
    tmp_path: Path, otlp: FakeCollector
) -> None:
    _round(_store("feat: one candidate"), tmp_path)

    assert _outcomes(otlp) == {"placed": 1.0, "duplicate": 0.0, "skipped": 0.0, "failed": 0.0}


def test_intake_outcome_the_instrument_is_a_counter_with_its_series_count_and_documented() -> None:
    from devops_cli.telemetry.instruments import INSTRUMENTS, InstrumentKind

    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    documented = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    assert INTAKE_CANDIDATES in declared, "the instrument is not declared"
    instrument = declared[INTAKE_CANDIDATES]
    assert (instrument.kind, instrument.unit, INTAKE_CANDIDATES in documented) == (
        InstrumentKind.COUNTER,
        "1",
        True,
    )
    for word in ("repo", "result", *sorted(INTAKE_RESULTS)):
        assert word in instrument.description
    assert "4 series" in instrument.description
    assert "4 series" in documented


# ── Implement ─────────────────────────────────────────────────────────────────


@pytest.fixture
def hooked_world(job_world: JobWorld) -> JobWorld:
    """The job world, with the hook configuration and a test module on `main` of `origin`, so that
    the scoped checks of the job have commands to run."""
    repo = job_world.repo
    (repo.clone / CONFIG).write_text(HOOKS, encoding="utf-8")
    (repo.clone / TEST_MODULE).parent.mkdir(exist_ok=True)
    (repo.clone / TEST_MODULE).write_text("from devops_cli.shout import shout\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Add the hooks and a test")
    repo.git("push", "-q", "origin", "main")
    return job_world


def _taking(
    world: JobWorld,
    matches: Callable[[ProcessCall], bool],
    seconds: float,
    effect: Callable[[ProcessCall], subprocess.CompletedProcess[str]] | None = None,
) -> None:
    """Each command that `matches` does its `effect` (it exits 0 by default) and then takes
    `seconds` on the fake clock."""

    def run(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        done = effect(call) if effect else subprocess.CompletedProcess(call.argv, 0, stdout="")
        world.clock.shift(seconds)
        return done

    world.programs.answer(matches, ProcessAnswer(side_effect=run))


def _is_push(call: ProcessCall) -> bool:
    return call.argv[0] == "git" and "push" in call.argv


def _fails(world: JobWorld, command: str) -> None:
    """`command` exits 1 with a report, each time it runs."""
    world.programs.answer(
        lambda call: command_text(call).startswith(command),
        ProcessAnswer(returncode=1, stdout="ruff-check....Failed\n"),
    )


def _fix(round_number: int) -> tuple[Any, Any]:
    """A fix that changes the code in a way that no earlier fix did."""
    changed = SHOUT + "".join(f"\n\nVALUE_{k} = {k}\n" for k in range(round_number))
    return (
        tool_calls(("write_file", {"path": "src/devops_cli/shout.py", "content": changed})),
        say(f"Fixed round {round_number}."),
    )


def _steps(otlp: FakeCollector) -> list[Sample]:
    """Each point of the step seconds histogram, as (attributes, count, sum), in a stable order."""
    found: list[Sample] = []
    for metric in otlp.metrics:
        if metric["name"] != STEP_SECONDS:
            continue
        for point in metric["exponentialHistogram"]["dataPoints"]:
            attrs = {a["key"]: next(iter(a["value"].values())) for a in point["attributes"]}
            found.append((attrs, int(point["count"]), point["sum"]))
    return sorted(found, key=lambda sample: sorted(sample[0].items()))


def _implement(otlp: FakeCollector) -> dict[tuple[str, str], tuple[int, float]]:
    """The count and the sum of each (step, result) pair of the row `implement`, after a check
    that every sample holds the four labels and no other, for the repository of the job."""
    samples = [sample for sample in _steps(otlp) if sample[0].get("row") == "implement"]
    assert {tuple(sorted(attrs)) for attrs, _, _ in samples} <= {("repo", "result", "row", "step")}
    assert {attrs["repo"] for attrs, _, _ in samples} <= {STAGE_REPO}
    return {(attrs["step"], attrs["result"]): (count, total) for attrs, count, total in samples}


def test_implement_step_a_run_emits_one_sample_for_the_checks_the_publish_and_the_watch(
    hooked_world: JobWorld, otlp: FakeCollector
) -> None:
    """A Staged item with a draft pull request: the scoped checks run once, the branch is pushed
    once, and the watch of the checks of the pull request runs once."""
    applied = hooked_world.run(two_groups())

    steps = _implement(otlp)
    assert (applied.ready, {step: count for (step, _), (count, _) in steps.items()}) == (
        (1,),
        {"checks": 1, "publish": 1, "watch": 1},
    )
    assert {result for _, result in steps} == {"ok"}


def test_implement_step_a_planned_item_publishes_its_branch_in_the_publish_sample(
    planned_world: JobWorld, otlp: FakeCollector
) -> None:
    """A Planned item has no branch yet: its first push publishes it and opens the draft pull
    request. That is the publish step too."""
    applied = planned_world.run(two_groups())

    steps = _implement(otlp)
    assert (applied.ready, {step: count for (step, _), (count, _) in steps.items()}) == (
        (1,),
        {"checks": 1, "publish": 1, "watch": 1},
    )


def test_implement_step_publish_excludes_the_seconds_of_the_scoped_checks(
    hooked_world: JobWorld, otlp: FakeCollector
) -> None:
    """The scoped checks take 10 s and the push takes 2 s on the fake clock. `_push` runs the
    checks first, so a timer around `_push` would put the 10 s in both samples."""
    _taking(hooked_world, lambda call: command_text(call).startswith(STATIC), CHECK_SECONDS)
    _taking(hooked_world, _is_push, PUSH_SECONDS, git_for_real)

    hooked_world.run(two_groups())

    steps = _implement(otlp)
    assert steps[("checks", "ok")][1] >= CHECK_SECONDS
    assert PUSH_SECONDS <= steps[("publish", "ok")][1] < CHECK_SECONDS


def test_implement_step_a_scoped_check_that_no_fix_repairs_sends_one_checks_sample_with_error(
    hooked_world: JobWorld, otlp: FakeCollector
) -> None:
    """One sample covers one call of the scoped checks with its fix rounds, and the stop of the
    call is an error. The job pushes nothing, so no publish sample and no watch sample follow."""
    _fails(hooked_world, PRE_PUSH)

    applied = hooked_world.run(two_groups(*_fix(1), *_fix(2), *_fix(3)))

    steps = _implement(otlp)
    assert (applied.stopped, {step: count for step, (count, _) in steps.items()}) == (
        (1,),
        {("checks", "error"): 1},
    )


def test_implement_step_a_failed_check_of_the_pull_request_is_a_watch_sample_with_error(
    hooked_world: JobWorld, otlp: FakeCollector
) -> None:
    """The first head fails a check and the repair gives a head that passes. The first watch
    returns a failed result with no exception, and it is an error all the same. The repair pushes
    again, so the job makes a second call of the scoped checks and of the publish step."""
    hooked_world.pull.runs = [[FAIL], [PASS]]

    applied = hooked_world.run(two_groups(*_fix(1)))

    steps = _implement(otlp)
    assert (applied.ready, {step: count for step, (count, _) in steps.items()}) == (
        (1,),
        {
            ("checks", "ok"): 2,
            ("publish", "ok"): 2,
            ("watch", "error"): 1,
            ("watch", "ok"): 1,
        },
    )


def test_implement_step_the_stage_samples_and_the_implement_samples_share_the_labels(
    hooked_world: JobWorld, otlp: FakeCollector
) -> None:
    """A run of the implement job sends no sample under another row, and the step values are
    the three new ones."""
    hooked_world.run(two_groups())

    samples = _steps(otlp)
    assert {attrs["row"] for attrs, _, _ in samples} == {"implement"}
    assert {attrs["step"] for attrs, _, _ in samples} == IMPLEMENT_STEPS


def test_implement_step_the_instrument_text_states_six_series_for_the_implement_row() -> None:
    """3 steps and 2 results make 6 series for one repository. The buckets add none. The stage
    row keeps its 10 series, so one repository holds 16."""
    from devops_cli.telemetry.instruments import INSTRUMENTS

    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    documented = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    description = declared[STEP_SECONDS].description
    assert "6 series" in description
    assert "10 series" in description
    assert "implement" in description
    assert "6 series" in documented


# ── The step names ────────────────────────────────────────────────────────────


def test_step_names_checks_publish_and_watch_are_members_of_step_name() -> None:
    assert (StepName.CHECKS.value, StepName.PUBLISH.value, StepName.WATCH.value) == (
        "checks",
        "publish",
        "watch",
    )


def test_step_names_the_step_values_of_a_run_are_members_of_step_name(
    hooked_world: JobWorld, otlp: FakeCollector
) -> None:
    hooked_world.run(two_groups())

    sent = {attrs["step"] for attrs, _, _ in _steps(otlp)}
    members = {step.value for step in StepName}
    assert (sent <= members, IMPLEMENT_STEPS <= members, sent >= IMPLEMENT_STEPS) == (
        True,
        True,
        True,
    )


def test_step_names_the_new_steps_are_one_word_and_come_after_the_steps_that_exist() -> None:
    assert [step.value for step in StepName][-3:] == ["checks", "publish", "watch"]


def test_step_names_the_tail_of_step_name_does_not_move_a_stored_step() -> None:
    """The ledger of the jobs stores the value of a step. The members that exist keep their
    values, and the new members add to them."""
    assert [step.value for step in StepName][:7] == [
        "plan",
        "apply",
        "investigate",
        "place",
        "select",
        "gate",
        "review",
    ]
