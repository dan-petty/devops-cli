"""The deadline of a runner Job follows its progress (#3063).

The Kubernetes API is faked at its edge (`FakeCluster`), the wall clock by the `clock` fixture, and
the CronJob template is the committed manifest `k8s/devops/cronjob-runner.yaml`. The log of the
pod is what the fake answers, so a test changes the log to make progress and leaves it to make
none.
"""

from __future__ import annotations

import copy
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import yaml
from kubernetes.client.rest import ApiException

from devops_cli.config.env import setting_variables
from devops_cli.k8s.cluster_job import repository_label
from devops_cli.k8s.cluster_job_api import ClusterJobs
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement_deadline import manage_deadlines
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.run import STATUS_LANE_ROWS
from devops_cli.roadmap.store import ImplementRecordKey
from devops_cli.telemetry.tracer import get_tracer, reset_tracer
from tests.support.fakes.clock import ClockFake
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.kubernetes import FakeCluster, pod
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import route_pull_status, seed_staged
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store", "app_slug")

IMPLEMENT_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "implement")
JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")
LABELS = {"implement-repo": repository_label(STAGE_REPO)}
START = datetime(2026, 11, 2, 10, 0, tzinfo=UTC)
NAME = "devops-cli-runner-20261102-100000-ab12"
PROGRESS = "roadmap.devops-cli/progress"
PROGRESS_AT = "roadmap.devops-cli/progress-at"
STALLED = "roadmap.devops-cli/stalled"
STALL, EXTENSION, CEILING = 4200, 5400, 14400
TICK = 450  # a round of the row, in seconds: 7 minutes and a tick of the Service, rounded


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
    cluster.core.answers["list_namespaced_pod"] = [pod(f"{NAME}-x1", namespace="devops")]
    cluster.core.answers["read_namespaced_pod_log"] = ""
    return cluster


@pytest.fixture
def now(clock: ClockFake) -> ClockFake:
    """The wall clock at `START`, the start of the Job."""
    clock.move_to(START)
    return clock


@pytest.fixture
def spans(monkeypatch: pytest.MonkeyPatch, config: Callable[..., Any]) -> Iterator[list[Any]]:
    """Every OTLP payload that the tracer sends."""
    config(telemetry={"enabled": True})
    reset_tracer()
    payloads: list[Any] = []
    monkeypatch.setattr(get_tracer(), "_send_payload", lambda path, p: payloads.append(p))
    yield payloads
    reset_tracer()


def _deadline_spans(payloads: list[Any]) -> list[dict[str, Any]]:
    found = [
        span
        for payload in payloads
        for resource in payload.get("resourceSpans", [])
        for scope in resource.get("scopeSpans", [])
        for span in scope.get("spans", [])
        if span.get("name") == "implement.deadline"
    ]
    return [
        {
            attr["key"]: next(iter(attr["value"].values()))
            for attr in span.get("attributes", [])
            if attr["key"].split(".")[0] in {"job", "deadline", "reason"}
        }
        for span in found
    ]


def _seed(
    kube: FakeCluster,
    *,
    deadline: int = EXTENSION,
    annotations: dict[str, str] | None = None,
    started: datetime | None = START,
    name: str = NAME,
) -> None:
    """A running Job of the repository, as the Job controller and the Service left it."""
    job: dict[str, Any] = {
        "metadata": {
            "name": name,
            "namespace": "devops",
            "labels": dict(LABELS),
            "annotations": {PROGRESS_AT: str(int(START.timestamp()))}
            if annotations is None
            else annotations,
        },
        "spec": {"activeDeadlineSeconds": deadline},
        "status": {"startTime": started.strftime("%Y-%m-%dT%H:%M:%SZ")} if started else {},
    }
    kube.custom_objects.objects[JOBS] = [job]


def _job(kube: FakeCluster) -> dict[str, Any]:
    (job,) = kube.custom_objects.objects[JOBS]
    return job


def _deadline(kube: FakeCluster) -> int:
    deadline: int = _job(kube)["spec"]["activeDeadlineSeconds"]
    return deadline


def _patches(kube: FakeCluster) -> list[dict[str, Any]]:
    return [
        call[1]["body"]
        for call in kube.custom_objects.calls
        if call[0] == "patch_namespaced_custom_object"
    ]


def _manage() -> None:
    api = ClusterJobs()
    manage_deadlines(api, api.list_jobs(LABELS))


def _log(kube: FakeCluster, text: str) -> None:
    kube.core.answers["read_namespaced_pod_log"] = text


# ── The extension ───────────────────────────────────────────────────────────────────────────


def test_a_changed_log_sets_the_deadline_to_the_time_since_the_start_plus_the_extension(
    kube: FakeCluster, now: ClockFake
) -> None:
    _seed(kube)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(1800)

    _manage()

    assert (_deadline(kube), _job(kube)["metadata"]["annotations"][PROGRESS_AT]) == (
        1800 + EXTENSION,
        str(int((START + timedelta(seconds=1800)).timestamp())),
    )


def test_the_log_is_read_for_the_lines_of_the_constant_and_its_digest_is_kept(
    kube: FakeCluster, now: ClockFake
) -> None:
    _seed(kube)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(60)

    _manage()

    (call,) = [c for c in kube.core.calls if c[0] == "read_namespaced_pod_log"]
    first = _job(kube)["metadata"]["annotations"][PROGRESS]
    _log(kube, "Tool call: read_file, ok.\nTool call: edit_file, ok.\n")
    now.shift(60)
    _manage()
    assert (
        call[1]["tail_lines"],
        len(first),
        first != _job(kube)["metadata"]["annotations"][PROGRESS],
    ) == (
        20,
        64,
        True,
    )


def test_a_progress_event_never_lowers_the_deadline(kube: FakeCluster, now: ClockFake) -> None:
    _seed(kube, deadline=9000)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(600)

    _manage()

    assert (_deadline(kube), _job(kube)["metadata"]["annotations"][PROGRESS] != "") == (9000, True)


def test_the_deadline_stops_at_the_ceiling(kube: FakeCluster, now: ClockFake) -> None:
    _seed(kube, deadline=CEILING - 100)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(CEILING - 600)

    _manage()

    assert _deadline(kube) == CEILING


def test_a_job_at_the_ceiling_keeps_its_deadline_on_progress(
    kube: FakeCluster, now: ClockFake, spans: list[Any]
) -> None:
    _seed(kube, deadline=CEILING)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(CEILING - 600)

    _manage()

    assert (_deadline(kube), _deadline_spans(spans)) == (CEILING, [])


def test_a_job_without_the_annotation_of_the_service_keeps_its_deadline(
    kube: FakeCluster, now: ClockFake
) -> None:
    _seed(kube, deadline=7200, annotations={})
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(7000)

    _manage()

    assert (_deadline(kube), _patches(kube)) == (7200, [])


def test_a_job_whose_pod_has_not_started_is_left_alone(kube: FakeCluster, now: ClockFake) -> None:
    _seed(kube, started=None)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(600)

    _manage()

    assert _patches(kube) == []


def test_a_job_that_ended_is_left_alone(kube: FakeCluster, now: ClockFake) -> None:
    _seed(kube)
    _job(kube)["status"]["conditions"] = [{"type": "Failed", "status": "True"}]
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(600)

    _manage()

    assert _patches(kube) == []


def test_a_log_that_the_api_refuses_is_no_progress_and_raises_nothing(
    kube: FakeCluster, now: ClockFake
) -> None:
    _seed(kube)
    _log(kube, "")
    kube.core.answers["read_namespaced_pod_log"] = ApiException(status=400, reason="Bad Request")
    now.shift(600)

    _manage()

    assert (_patches(kube), _deadline(kube)) == ([], EXTENSION)


# ── The stall ───────────────────────────────────────────────────────────────────────────────


def test_a_log_that_stays_the_same_for_the_stall_time_ends_the_job_by_its_deadline(
    kube: FakeCluster, now: ClockFake
) -> None:
    _seed(kube, annotations={PROGRESS_AT: str(int(START.timestamp())), PROGRESS: ""})
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(60)
    _manage()
    saw = _job(kube)["metadata"]["annotations"][PROGRESS_AT]
    now.shift(STALL)

    _manage()

    annotations = _job(kube)["metadata"]["annotations"]
    assert (
        _deadline(kube),
        annotations[STALLED],
        saw != str(int(START.timestamp())),
    ) == (60 + STALL, str(STALL), True)


def test_a_silence_below_the_stall_time_changes_no_deadline(
    kube: FakeCluster, now: ClockFake
) -> None:
    _seed(kube)
    now.shift(STALL - 1)

    _manage()

    assert (_patches(kube), _deadline(kube)) == ([], EXTENSION)


def test_an_empty_log_is_no_progress(kube: FakeCluster, now: ClockFake) -> None:
    _seed(kube)
    _log(kube, "")
    now.shift(600)

    _manage()

    assert _patches(kube) == []


def test_a_stalled_job_is_marked_one_time(kube: FakeCluster, now: ClockFake) -> None:
    _seed(kube)
    now.shift(STALL)
    _manage()
    now.shift(TICK)

    _manage()

    assert len(_patches(kube)) == 1


# ── A replay ────────────────────────────────────────────────────────────────────────────────


def _replay(kube: FakeCluster, now: ClockFake, *, progress: bool, hours: int) -> tuple[int, int]:
    """Run a round every `TICK` seconds, as the Job controller would end the Job at its deadline.
    Return the deadline at which the Job ended (0 when it did not) and the most seconds that its
    deadline was ahead of the clock."""
    _seed(kube)
    steps = hours * 3600 // TICK
    ahead = 0
    for step in range(1, steps + 1):
        now.shift(TICK)
        if progress:
            _log(kube, f"Tool call: read_file, ok. {step}\n")
        elapsed = step * TICK
        if elapsed >= _deadline(kube):
            return _deadline(kube), ahead
        _manage()
        ahead = max(ahead, _deadline(kube) - elapsed)
    return 0, ahead


def test_a_replay_of_three_hours_that_makes_progress_finishes_without_a_deadline(
    kube: FakeCluster, now: ClockFake
) -> None:
    ended, ahead = _replay(kube, now, progress=True, hours=3)

    assert (ended, _deadline(kube) <= CEILING, ahead >= EXTENSION - TICK) == (0, True, True)


def test_a_replay_that_makes_progress_ends_at_the_ceiling(
    kube: FakeCluster, now: ClockFake
) -> None:
    ended, _ = _replay(kube, now, progress=True, hours=5)

    assert (ended, _deadline(kube)) == (CEILING, CEILING)


def test_a_replay_that_makes_none_ends_at_the_stall_time(kube: FakeCluster, now: ClockFake) -> None:
    ended, _ = _replay(kube, now, progress=False, hours=3)

    stalled = int(_job(kube)["metadata"]["annotations"][STALLED])
    assert (STALL <= ended <= STALL + TICK, STALL <= stalled <= STALL + TICK) == (True, True)


# ── The trace ───────────────────────────────────────────────────────────────────────────────


def test_an_extension_is_a_span_with_the_old_and_the_new_deadline_and_the_reason(
    kube: FakeCluster, now: ClockFake, spans: list[Any]
) -> None:
    _seed(kube)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(1800)

    _manage()
    get_tracer().flush()

    assert _deadline_spans(spans) == [
        {
            "job": NAME,
            "deadline.previous_seconds": str(EXTENSION),
            "deadline.seconds": str(1800 + EXTENSION),
            "reason": "progress",
        }
    ]


def test_a_deadline_cut_to_the_ceiling_says_so(
    kube: FakeCluster, now: ClockFake, spans: list[Any]
) -> None:
    _seed(kube, deadline=CEILING - 100)
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(CEILING - 600)

    _manage()
    get_tracer().flush()

    (span,) = _deadline_spans(spans)
    assert (span["deadline.seconds"], span["reason"]) == (str(CEILING), "progress, ceiling")


def test_a_stall_is_a_span_with_the_reason_stall(
    kube: FakeCluster, now: ClockFake, spans: list[Any]
) -> None:
    _seed(kube)
    now.shift(STALL)

    _manage()
    get_tracer().flush()

    (span,) = _deadline_spans(spans)
    assert (span["deadline.seconds"], span["reason"]) == (str(STALL), "stall")


def test_a_round_with_no_change_of_the_deadline_makes_no_span(
    kube: FakeCluster, now: ClockFake, spans: list[Any]
) -> None:
    _seed(kube)
    now.shift(60)

    _manage()
    get_tracer().flush()

    assert _deadline_spans(spans) == []


# ── The round ───────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    route_pull_status(github_api)
    return github_api


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> None:
    IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _created(kube: FakeCluster) -> dict[str, Any]:
    (job,) = kube.custom_objects.objects[JOBS]
    return job


def test_a_round_creates_the_job_with_the_extension_as_its_deadline_and_the_annotation(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    now: ClockFake,
) -> None:
    seed_staged(store)

    _round(store, staged_repo)

    job = _created(kube)
    (container,) = job["spec"]["template"]["spec"]["containers"]
    (annotation,) = job["metadata"]["annotations"].items()
    assert (
        job["spec"]["activeDeadlineSeconds"],
        annotation[0],
        int(START.timestamp()) <= int(annotation[1]) <= int(datetime.now(UTC).timestamp()),
        container["resources"]["limits"]["memory"],
    ) == (EXTENSION, PROGRESS_AT, True, "8Gi")


def test_a_later_round_extends_the_deadline_of_the_job_it_created(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    now: ClockFake,
) -> None:
    seed_staged(store)
    _round(store, staged_repo)
    started = datetime.now(UTC).replace(microsecond=0)
    _created(kube)["status"] = {"startTime": started.strftime("%Y-%m-%dT%H:%M:%SZ")}
    _log(kube, "Tool call: read_file, ok.\n")
    now.shift(900)

    _round(store, staged_repo)

    seen = int(_created(kube)["metadata"]["annotations"][PROGRESS_AT])
    assert 0 <= _deadline(kube) - EXTENSION - (seen - int(started.timestamp())) <= 1


@pytest.mark.usefixtures("no_continuation")
def test_the_report_of_a_stalled_job_names_the_silence(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    now: ClockFake,
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    _created(kube)["status"] = {"startTime": "2026-11-02T10:00:00Z"}
    now.shift(STALL)
    _round(store, staged_repo)
    _created(kube)["status"]["conditions"] = [{"type": "Failed", "status": "True"}]

    _round(store, staged_repo)

    (comment,) = [
        c.body for c in store.comments_on(number) if "roadmap implement" in c.body.splitlines()[0]
    ]
    held = store.item(number)
    assert held is not None
    assert (
        MESSAGES.roadmap.implement_job_report_stalled.format(seconds=STALL).strip() in comment,
        held.job_record.get(ImplementRecordKey.FAILURE),
    ) == (True, "timeout")


@pytest.mark.usefixtures("no_continuation")
def test_the_report_of_a_job_that_did_not_stall_does_not_mention_a_stall(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    now: ClockFake,
) -> None:
    number = seed_staged(store)
    _round(store, staged_repo)
    _created(kube)["status"] = {"conditions": [{"type": "Failed", "status": "True"}]}

    _round(store, staged_repo)

    (comment,) = [
        c.body for c in store.comments_on(number) if "roadmap implement" in c.body.splitlines()[0]
    ]
    assert "stall" not in comment.lower()


def test_the_variables_of_the_settings_are_the_ones_of_the_deployment() -> None:
    assert (
        setting_variables()["roadmap.implement.deadline_extension_seconds"]
        == "DEVOPS_CLI_ROADMAP_IMPLEMENT_DEADLINE_EXTENSION_SECONDS"
    )
