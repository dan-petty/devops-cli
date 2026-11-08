"""The seconds of each step of a stage round and the gates that refuse a plan (#4066).

A stage round sends one sample of `devops_cli_roadmap_step_seconds` for each call of a step, under
`repo`, `row`, `step` and `result`. The row is `stage`; #4067 sends the implement row with the same
four labels. The counter `devops_cli_roadmap_stage_gate_refusals_total` adds 1 for each gate that
found a problem in a reply, under `repo` and `gate`.

The rounds run over `plan_stage` and the writer of the job. The planner and the verifier are the
model fake, and each of their answers moves the fake clock by a set number of seconds, so a sample
holds a value that the test knows. The collector is the fake of the OTLP fixture, and a histogram
point is read as (attributes, count, sum).

The names of the instruments are strings and the instruments are imported in the tests that need
them: the fail-to-pass replay loads this module against a base tree that has neither.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest

from devops_cli.ai.client.models import AIClientError
from devops_cli.core import clock as clock_seam
from devops_cli.roadmap.failure import FailureClass, StepName
from devops_cli.roadmap.stage.stage import (
    StagePlan,
    parse_filters,
    plan_item,
    plan_stage,
    select_stageable,
)
from devops_cli.roadmap.stage.stage_change import ProposalGate
from devops_cli.roadmap.stage.stage_toolbox import ToolboxClient, ToolboxModel
from devops_cli.roadmap.stage.stage_verify import Verification
from devops_cli.roadmap.stores.store import StageRecordKey
from tests.support.builders import make_stage_proposal
from tests.support.fakes.github import github_json
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_stage import (
    STAGE_REPO,
    VALID_REPORT,
    StageRepo,
    apply_stage,
    seed_stageable,
    validate_args,
)
from tests.support.scripted_model import Script

if TYPE_CHECKING:
    from devops_cli.roadmap.planned import PlannedChanges
    from devops_cli.roadmap.stage.stage import StageClient
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.model import ModelFake
    from tests.support.fakes.openspec import OpenSpecFake
    from tests.support.fakes.otlp import FakeCollector

pytestmark = pytest.mark.usefixtures("keyring_store")

STEP_SECONDS = "devops_cli_roadmap_step_seconds"
GATE_REFUSALS = "devops_cli_roadmap_stage_gate_refusals_total"
BRANCH = "fix/1-the-job-drops-a-comment"
PULLS = f"/repos/{STAGE_REPO}/pulls"
OPENED = github_json({"number": 5, "html_url": "https://example.com/pull/5"}, status=201)
PLAN_SECONDS = 3.0
REVIEW_SECONDS = 2.0
STAGE_STEPS = {"select", "plan", "gate", "review", "apply"}
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)

Sample = tuple[dict[str, Any], int, float]


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    seed_stageable(store)
    store.seed_file(
        ".github/labels.yml",
        '- name: "type/docs"\n  color: "0075ca"\n- name: "scope/openspec"\n  color: "0e8a16"\n',
    )
    for i in range(2, 5):
        store.seed_issue(f"placeholder {i}")
    store.seed_pull("staging PR", head_ref=BRANCH, draft=True)
    return store


@pytest.fixture(autouse=True)
def valid_openspec(openspec_fake: OpenSpecFake) -> OpenSpecFake:
    """OpenSpec, found, and valid about the change of #1 for every run of a test."""
    openspec_fake.script_sequence(
        validate_args("1-the-job-drops-a-comment"), *[(0, VALID_REPORT)] * 6
    )
    return openspec_fake


@pytest.fixture(autouse=True)
def opened_pull(github_api: Any) -> None:
    """The draft pull request that the writer opens."""
    cast("GitHubApiFake", github_api).route("POST", PULLS, OPENED)


class StepClock:
    """The monotonic reading of the clock seam, moved only by the test.

    The wall clock stays as it is, so the pacing of a GitHub request and the quota of the fake API
    see no passing time, and a step holds exactly the seconds that the test gave it."""

    def __init__(self) -> None:
        self._now = 0.0

    def monotonic(self) -> float:
        return self._now

    def shift(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> StepClock:
    fake = StepClock()
    monkeypatch.setattr(clock_seam, "monotonic", fake.monotonic)
    return fake


def _taking(clock: StepClock, seconds: float, answer: Any) -> Any:
    """An answer of the model fake that takes `seconds` on the fake clock and then gives `answer`."""

    def give(_prompt: str) -> Any:
        clock.shift(seconds)
        return answer

    return give


def _plan(
    store: InMemoryRoadmapStore, repo: StageRepo, *, verifier: ModelFake | None = None
) -> StagePlan:
    return plan_stage(
        store,
        repo=STAGE_REPO,
        source=repo.clone,
        filters=parse_filters(()),
        model=cast("StageClient | None", None),
        verifier=ToolboxModel(verifier) if verifier is not None else None,
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


def _by_step(otlp: FakeCollector) -> dict[tuple[str, str], tuple[int, float]]:
    """The count and the sum of each (step, result) pair, after a check that every sample holds
    the four labels and no other."""
    samples = _steps(otlp)
    assert {tuple(sorted(attrs)) for attrs, _, _ in samples} <= {("repo", "result", "row", "step")}
    assert {(attrs["repo"], attrs["row"]) for attrs, _, _ in samples} <= {(STAGE_REPO, "stage")}
    return {(attrs["step"], attrs["result"]): (count, total) for attrs, count, total in samples}


def _refusals(otlp: FakeCollector) -> list[tuple[dict[str, Any], float]]:
    return sorted(otlp.points(GATE_REFUSALS), key=lambda point: sorted(point[0].items()))


def _refused_once(**update: Any) -> Any:
    """A plan that one gate refuses, the gate `paths`: its group changes files that do not exist."""
    group = make_stage_proposal().groups[0]
    changes = [*group.changes, "tests/test_missing.py", "tests/test_missing_too.py"]
    return make_stage_proposal(groups=[group.model_copy(update={"changes": changes, **update})])


# ── The step seconds ──────────────────────────────────────────────────────────


def test_step_label_a_stage_round_emits_a_sample_for_select_plan_gate_review_and_apply(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    clock: StepClock,
    otlp: FakeCollector,
) -> None:
    """One round that plans, reviews and writes one item sends a sample for each of the five steps
    under the row `stage` and the result `ok`. The planner call took 3 s and the review 2 s on the
    fake clock."""
    from tests.support.fakes.model import ModelFake as Fake

    verifier = Fake()
    model_fake.answer(_taking(clock, PLAN_SECONDS, make_stage_proposal()))
    verifier.answer(_taking(clock, REVIEW_SECONDS, Verification()))

    apply_stage(store, _plan(store, stage_repo, verifier=verifier), source=stage_repo.clone)

    assert _by_step(otlp) == {
        ("select", "ok"): (1, 0.0),
        ("plan", "ok"): (1, PLAN_SECONDS),
        ("gate", "ok"): (1, 0.0),
        ("review", "ok"): (1, REVIEW_SECONDS),
        ("apply", "ok"): (1, 0.0),
    }


def test_step_label_a_round_with_no_verifier_sends_no_review_sample(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    otlp: FakeCollector,
) -> None:
    """The review step times the model review. A job that makes no review call sends no sample."""
    model_fake.answer(make_stage_proposal())

    apply_stage(store, _plan(store, stage_repo), source=stage_repo.clone)

    assert {step for step, _ in _by_step(otlp)} == STAGE_STEPS - {"review"}


def test_step_label_a_refused_reply_adds_one_gate_sample_for_each_call_of_the_gates(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    otlp: FakeCollector,
) -> None:
    """The gates run once for the first reply and once for the reply that answers the problem, so
    the item adds two gate samples and two plan samples. A refusal is no error: both gate samples
    have the result `ok`."""
    model_fake.answer(_refused_once(), make_stage_proposal())

    _plan(store, stage_repo)

    steps = _by_step(otlp)
    assert (steps[("gate", "ok")][0], steps[("plan", "ok")][0], ("gate", "error") in steps) == (
        2,
        2,
        False,
    )


def test_step_label_a_step_that_raises_sends_its_sample_with_the_result_error(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    clock: StepClock,
    otlp: FakeCollector,
) -> None:
    """The planner call fails after 3 s. Its sample has the result `error` and the seconds up to
    the error, and no step after it sends a sample."""
    model_fake.answer(_taking(clock, PLAN_SECONDS, AIClientError("the model is down")))

    plan = _plan(store, stage_repo)

    steps = _by_step(otlp)
    assert (len(plan.failed), ("plan", "error") in steps, {step for step, _ in steps}) == (
        1,
        True,
        {"select", "plan"},
    )
    assert steps[("plan", "error")][1] == PLAN_SECONDS
    assert ("plan", "ok") not in steps


def test_step_label_a_write_that_fails_sends_the_apply_sample_with_the_result_error(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: Any,
    otlp: FakeCollector,
) -> None:
    """The writer records a failed write and goes on, so the error shows in the label."""
    cast("GitHubApiFake", github_api).route(
        "POST", PULLS, github_json({"message": "Validation Failed"}, status=422)
    )
    model_fake.answer(make_stage_proposal())

    applied = apply_stage(store, _plan(store, stage_repo), source=stage_repo.clone)

    steps = _by_step(otlp)
    assert (len(applied.failed), steps[("apply", "error")][0], ("apply", "ok") in steps) == (
        1,
        1,
        False,
    )


def test_step_label_a_golden_set_replay_sends_no_step_sample_and_no_refusal(
    store: InMemoryRoadmapStore, stage_repo: StageRepo, otlp: FakeCollector
) -> None:
    """`plan_item` replays one item with no repository, as the evaluation does. It adds no series,
    so a replay does not add a `repo` value."""
    item = store.item(1)
    assert item is not None
    sha = stage_repo.git("rev-parse", "HEAD")
    script = Script(_refused_once(), make_stage_proposal())
    client = ToolboxClient(script.model(), cast("StageClient", object()), stage_repo.clone, sha)

    plan_item(item, client=client, checkout=stage_repo.clone, sha=sha)

    assert (_steps(otlp), _refusals(otlp)) == ([], [])


# ── The step names ────────────────────────────────────────────────────────────


def test_step_names_the_step_values_are_members_of_step_name_and_no_other_value_appears(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    github_api: Any,
    otlp: FakeCollector,
) -> None:
    """A round that stages one item and a round that fails one send step values, and each value is
    the value of a member of `StepName`. The stage steps are in the enum."""
    from tests.support.fakes.model import ModelFake as Fake

    verifier = Fake()
    verifier.answer(Verification())
    model_fake.answer(make_stage_proposal())
    apply_stage(store, _plan(store, stage_repo, verifier=verifier), source=stage_repo.clone)
    model_fake.reset()
    model_fake.answer(AIClientError("the model is down"))
    store.seed_issue("fix(roadmap): a second item", labels=("type/bug",))
    _plan(store, stage_repo)

    sent = {attrs["step"] for attrs, _, _ in _steps(otlp)}
    members = {step.value for step in StepName}
    assert (sent <= members, STAGE_STEPS <= members, sent >= STAGE_STEPS) == (True, True, True)


def test_step_names_the_new_steps_are_one_word_and_come_after_the_steps_that_exist() -> None:
    assert [step.value for step in StepName][-3:] == ["select", "gate", "review"]


# ── The gate refusals ─────────────────────────────────────────────────────────


def test_gate_refusal_a_refused_plan_adds_one_to_its_gate_and_to_no_other(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    otlp: FakeCollector,
) -> None:
    """The first reply changes two files that do not exist: the gate `paths` finds two problems and
    counts one. The reply that answers the problem passes every gate."""
    model_fake.answer(_refused_once(), make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert (len(plan.ready), _refusals(otlp)) == (
        1,
        [({"repo": STAGE_REPO, "gate": ProposalGate.PATHS.value}, 1.0)],
    )


def test_gate_refusal_a_plan_that_passes_every_gate_adds_no_refusal(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    otlp: FakeCollector,
) -> None:
    model_fake.answer(make_stage_proposal())

    plan = _plan(store, stage_repo)

    assert (len(plan.ready), _refusals(otlp)) == (1, [])


def test_gate_refusal_a_plan_that_a_gate_refuses_twice_counts_the_gate_twice(
    store: InMemoryRoadmapStore,
    stage_repo: StageRepo,
    model_fake: ModelFake,
    otlp: FakeCollector,
) -> None:
    """The count is the count of refused replies, not of refused items: the item fails after its
    second refusal, and the series holds 2."""
    model_fake.answer(_refused_once())

    plan = _plan(store, stage_repo)

    assert (len(plan.failed), _refusals(otlp)) == (
        1,
        [({"repo": STAGE_REPO, "gate": ProposalGate.PATHS.value}, 2.0)],
    )


# ── The instruments and the documents ─────────────────────────────────────────


def test_step_label_the_step_seconds_instrument_is_a_histogram_of_seconds_and_documented() -> None:
    from devops_cli.telemetry.instruments import INSTRUMENTS, InstrumentKind

    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    documented = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    assert STEP_SECONDS in declared, "the instrument is not declared"
    instrument = declared[STEP_SECONDS]
    assert (instrument.kind, instrument.unit, STEP_SECONDS in documented) == (
        InstrumentKind.HISTOGRAM,
        "s",
        True,
    )
    for label in ("repo", "row", "step", "result"):
        assert label in instrument.description
    assert re.search(r"\b10 series\b", instrument.description)


def test_gate_refusal_the_counter_is_declared_with_its_series_count_and_documented() -> None:
    """The description states the series count: one repository and one series for each gate."""
    from devops_cli.telemetry.instruments import INSTRUMENTS, InstrumentKind

    declared = {instrument.name: instrument for instrument in INSTRUMENTS}
    documented = (REPO_ROOT / "docs" / "TELEMETRY.md").read_text(encoding="utf-8")

    assert GATE_REFUSALS in declared, "the instrument is not declared"
    instrument = declared[GATE_REFUSALS]
    assert (instrument.kind, instrument.unit, GATE_REFUSALS in documented) == (
        InstrumentKind.COUNTER,
        "1",
        True,
    )
    assert re.search(rf"\b{len(ProposalGate)} series\b", instrument.description)


def test_step_label_the_series_of_the_stage_row_are_five_steps_and_two_results() -> None:
    """The stage row sends 5 steps and 2 results, so one repository adds at most 10 series. The
    series count of the instrument text is this product."""
    stage_steps = {"select", "plan", "gate", "review", "apply"}
    results = {"ok", "error"}

    assert (stage_steps <= {step.value for step in StepName}, len(stage_steps) * len(results)) == (
        True,
        10,
    )


# ── The rollout ───────────────────────────────────────────────────────────────


def test_an_old_failure_record_with_the_step_plan_loads_and_holds_the_item_as_before(
    store: InMemoryRoadmapStore,
) -> None:
    """The change adds no field to the record of the job: the step it writes is a string that the
    ledger on the volume already holds. A record of the earlier form is read, its step is a member
    of `StepName`, and the item waits for the time of its class."""
    item = store.item(1)
    assert item is not None
    store.set_marks(
        item,
        {
            StageRecordKey.FAILED_AT: NOW.isoformat(),
            StageRecordKey.FAILED_ERROR: "AIClientError",
            StageRecordKey.FAILED_STEP: "plan",
            StageRecordKey.FAILED_CLASS: FailureClass.PROVIDER.value,
        },
    )
    held = store.item(1)
    assert held is not None

    selection = select_stageable(
        store,
        filters=parse_filters(()),
        holder_of=lambda _issue, _branch: None,
        planned=cast("PlannedChanges", _no_plans()),
        item_number=None,
        limit=5,
        planned_limit=20,
        now=NOW + timedelta(minutes=1),
    )

    assert (
        StepName(held.job_record[StageRecordKey.FAILED_STEP]) is StepName.PLAN,
        [target.item.number for target in selection.selected],
    ) == (True, [])


def _no_plans() -> object:
    from devops_cli.roadmap.planned import PlannedChanges

    return PlannedChanges("main", {}, {})
