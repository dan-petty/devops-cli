"""The implement job writes how its run ended, and hands the stop of an earlier Job on (#4071).

Three parts. The runner writes `implement.result` as the last mark of a run (`typed_result`). The
Service reads it, and a Job that left no result keeps the old path with its log (`no_result`). The
first step of a run gets the check log and the conflict files of the earlier stop, and the next
Job clears both in its first record write (`handoff`).

Git runs for real on a clone with an `origin`. The model is scripted. GitHub's REST API and `gh`
are faked at their edges, and so is the Kubernetes API. A Job that is killed raises a
`BaseException` from the model: the pod is gone, so the job writes no stop.

The key `implement.result` is written as text here, so that a module without the key still
collects and each test fails on its own assertion.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any

import pytest
import yaml
from pydantic_ai.messages import UserPromptPart

from devops_cli.ai.task_loader import load_task_prompt
from devops_cli.config.constants import CONST_SERVICE_METRIC_IMPLEMENT_FAILURES
from devops_cli.roadmap.implement.implement_run import apply_implement
from devops_cli.roadmap.implement.implement_shell_policy import fill_prompt
from devops_cli.roadmap.run import STATUS_LANE_ROWS, JobOutcome
from devops_cli.roadmap.stores.store import (
    ImplementRecordKey,
    ItemField,
    decode_job_record,
    encode_job_record,
    split_record,
)
from devops_cli.telemetry.metrics import GLOBAL_METRICS
from tests.support.fakes.github import GitHubApiFake
from tests.support.fakes.kubernetes import FakeCluster, pod
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.paths import REPO_ROOT
from tests.support.roadmap_implement import (
    RUNNING,
    JobWorld,
    group_one_calls,
    route_pull_status,
    seed_staged,
    two_groups,
)
from tests.support.roadmap_stage import STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

RESULT = "implement.result"
MARKER = "<!-- devops roadmap implement -->"
HEADING = "# The stop of the earlier Job"
LOG = "FAILED tests/test_shout.py::test_loud - assert 'quiet' == 'LOUD'"
FILES = ["docs/conflicted-one.md", "docs/conflicted-two.md"]
JOB = "implement-example-roadmap-1-aaaaa"
NEXT_JOB = "implement-example-roadmap-1-bbbbb"
IMPLEMENT_ROW = next(row for row in STATUS_LANE_ROWS if row.name == "implement")
JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")
OUT_OF_MEMORY = "Traceback (most recent call last):\nMemoryError: Cannot allocate memory\n"


class Mark(StrEnum):
    """Marks of the record that a test writes as text, so that it needs no key of the job."""

    RESULT = RESULT


class PodKilled(BaseException):
    """The pod of the Job is gone. No handler of the job sees it."""


def _item(world: JobWorld) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(1)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


def _mark(world: JobWorld, marks: Mapping[Any, str | None]) -> None:
    held = world.store.item(1)
    assert held is not None
    world.store.set_marks(held, marks)


def _raw_record(store: InMemoryRoadmapStore) -> dict[str, Any]:
    """The record block of the item as GitHub holds it, with the keys that this version of the
    code does not know. The record that `Item` returns drops those."""
    return split_record(store.raw_body(1))[1]


def _last_mark(world: JobWorld) -> str | None:
    """The key of the last mark that the job wrote to the record of the item."""
    marks = [w for w in world.store.job_writes() if w.operation == "set_mark" and w.number == 1]
    return marks[-1].key if marks else None


def _prompt(script: ModelScript, request: int) -> str:
    """The user message of request number `request` (from 1) that the model saw."""
    return "\n".join(
        str(part.content)
        for message in script.seen[request - 1]
        for part in getattr(message, "parts", ())
        if isinstance(part, UserPromptPart)
    )


def _stopped_with_a_log(world: JobWorld, *, retry: bool) -> None:
    """An item that a stop left with the end of a failed check log and the unmerged files of a
    conflict. A person who retries comments after the stop comment, and the stop stays in the
    record until the next Job clears it. Else the Service cleared the stop: its rule removes the
    stop and the class and leaves the Job to take the item."""
    marks: dict[Any, str | None] = {
        ImplementRecordKey.CHECK_LOG: LOG,
        ImplementRecordKey.CONFLICT: json.dumps(FILES),
    }
    if retry:
        marks |= {
            ImplementRecordKey.STOPPED: "fix",
            ImplementRecordKey.FAILURE: "test",
            ImplementRecordKey.CHECK: "pre-push",
        }
    _mark(world, marks)
    if retry:
        world.store.comment(1, f"{MARKER}\nStopped at fix.")
        world.store.seed_comment(1, "implement: retry", author_association="OWNER")


def _killed_in_group_two(world: JobWorld) -> ModelScript:
    """Run until the pod dies at the first request of group 2. Group 1 has passed."""

    def die() -> None:
        raise PodKilled

    script = ModelScript(tool_calls(*group_one_calls()), say("Group 1 is done."), effects={3: die})
    with pytest.raises(PodKilled) as killed:
        world.run(script)
    assert killed.type is PodKilled
    return script


# ── typed_result: the runner writes how its run ended ─────────────────────────────────────


def test_typed_result_a_ready_run_writes_ready_as_its_last_mark(job_world: JobWorld) -> None:
    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.ready, status, record.get(RESULT), _last_mark(job_world)) == (
        (1,),
        "In Review",
        "ready",
        RESULT,
    )


def test_typed_result_a_stopped_run_writes_stopped_after_the_stop(job_world: JobWorld) -> None:
    job_world.pull.runs = [[RUNNING]]

    applied = job_world.run(two_groups())

    status, record = _item(job_world)
    assert (applied.stopped, status, record.get("implement.stopped")) == ((1,), "Blocked", "checks")
    assert (record.get(RESULT), _last_mark(job_world)) == ("stopped", RESULT)


def test_typed_result_a_run_that_a_claim_ended_writes_yielded(job_world: JobWorld) -> None:
    script = two_groups()
    script.effects[2] = lambda: job_world.store.as_actor("alice").add_label(1, "owner/human")

    applied = job_world.run(script)

    status, record = _item(job_world)
    assert (applied.yielded, status, record.get("implement.stopped")) == ((1,), "In Progress", None)
    assert (record.get(RESULT), _last_mark(job_world)) == ("yielded", RESULT)


def test_typed_result_a_claim_before_the_first_group_writes_yielded(job_world: JobWorld) -> None:
    plan = job_world.plan()
    job_world.store.as_actor("alice").add_label(1, "owner/agent")
    script = two_groups()

    applied = apply_implement(
        job_world.store, plan, source=job_world.repo.clone, model=script.model(), window=200_000
    )

    _, record = _item(job_world)
    assert (applied.yielded, script.seen, record.get(RESULT)) == ((1,), [], "yielded")


class TestTypedResultOfAReturn:
    """A false premise of a behavior group returns the item to New."""

    TITLES_PATH = "src/devops_cli/titles.py"
    TASKS = (
        "# Tasks\n\n## 1. The first group\n\n"
        "Reads: `CONTEXT.md`. Changes: `tests/test_shout.py` (new), `src/devops_cli/shout.py` (new).\n\n"
        "- [ ] 1.1 Add the failing test `tests/test_shout.py` for `src/devops_cli/shout.py`\n"
        "  - Verification: `$ uv run devops ci test tests/test_shout.py` fails on the base\n"
        "- [ ] 1.2 Add the guard `_delivery_title` to `src/devops_cli/shout.py`\n"
        "  - Verification: `$ uv run devops ci test tests/test_shout.py`\n\n"
        "## 2. The second group\n\n"
        "Reads: `CONTEXT.md`. Changes: `CONTEXT.md`.\n\n"
        "- [ ] 2.1 Document the function in `CONTEXT.md`\n"
        "  - Verification: `$ uv run devops docs check`\n\n"
        "## Criteria\n\n- Group 1: The job keeps every comment.\n"
    )

    @pytest.fixture
    def staged_files(self) -> dict[str, str]:
        body = '"""The titles."""\n\n\ndef _delivery_title(text: str) -> str:\n    return text.strip()\n'
        return {"tests/conftest.py": '"""The tests."""\n', self.TITLES_PATH: body}

    @pytest.fixture
    def staged_tasks(self) -> str:
        return self.TASKS

    def test_typed_result_a_return_to_new_writes_returned_as_its_last_mark(
        self, job_world: JobWorld
    ) -> None:
        applied = job_world.run(two_groups())

        status, record = _item(job_world)
        assert (applied.returned, status) == ((1,), "New")
        assert (record.get(RESULT), _last_mark(job_world)) == ("returned", RESULT)


def test_typed_result_a_new_run_clears_the_result_of_the_run_before(job_world: JobWorld) -> None:
    _mark(job_world, {Mark.RESULT: "ready"})

    _killed_in_group_two(job_world)

    status, record = _item(job_world)
    assert (status, record.get("implement.group")) == ("In Progress", "1")
    assert _raw_record(job_world.store).get(RESULT) is None


# ── typed_result: the record of an older version ──────────────────────────────────────────


def test_typed_result_the_key_is_kept_by_a_read_of_the_record() -> None:
    held = {RESULT: "yielded", "implement.group": "1"}

    assert decode_job_record(held) == held


def test_typed_result_a_record_of_an_older_version_loads_with_no_result() -> None:
    held = {
        "implement.group": "2",
        "implement.sha": "a" * 40,
        "implement.check_log": LOG,
        "implement.conflict": json.dumps(FILES),
    }

    assert decode_job_record(held) == held


def test_typed_result_a_key_of_a_newer_version_is_kept_by_a_write() -> None:
    written = json.loads(
        encode_job_record({"implement.future": "x"}, {Mark.RESULT: "ready"})
        .removeprefix("<!-- devops-roadmap-record ")
        .removesuffix(" -->")
    )

    assert written == {"implement.future": "x", RESULT: "ready"}


# ── typed_result and no_result: the Service reads the result of a Job ─────────────────────


@pytest.fixture
def store() -> InMemoryRoadmapStore:
    return InMemoryRoadmapStore(repo=STAGE_REPO)


@pytest.fixture
def api(github_api: GitHubApiFake) -> GitHubApiFake:
    route_pull_status(github_api)
    return github_api


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
    return cluster


def _round(store: InMemoryRoadmapStore, repo: StageRepo) -> JobOutcome:
    """One round of the row, as the Service runs it in its model clone."""
    return IMPLEMENT_ROW.runner(store=store, repo=STAGE_REPO, clone_path=repo.clone)


def _end(kube: FakeCluster, condition: str) -> None:
    """The Job controller marks the Job Complete or Failed."""
    kube.custom_objects.objects[JOBS][0]["status"] = {
        "conditions": [{"type": condition, "status": "True"}]
    }


def _held(store: InMemoryRoadmapStore) -> Any:
    item = store.item(1)
    assert item is not None
    return item


def _record(store: InMemoryRoadmapStore) -> dict[str, str | None]:
    return {str(key): value for key, value in _held(store).job_record.items()}


def _failures(failure_class: str) -> float:
    return GLOBAL_METRICS.get_counter(
        CONST_SERVICE_METRIC_IMPLEMENT_FAILURES,
        labels={"class": failure_class, "repo": STAGE_REPO},
    )


@pytest.mark.usefixtures("app_slug", "no_continuation")
@pytest.mark.parametrize(
    ("result", "status", "after", "state"),
    [
        ("yielded", "In Progress", "In Progress", "succeeded"),
        ("ready", "In Progress", "In Progress", "succeeded"),
        # An item that is Ready and not stopped is eligible, so the same round gives it a new Job.
        ("returned", "Ready", "In Progress", None),
    ],
)
def test_typed_result_a_job_with_a_result_that_is_no_stop_makes_no_stop(
    store: InMemoryRoadmapStore,
    staged_repo: StageRepo,
    api: GitHubApiFake,
    kube: FakeCluster,
    result: str,
    status: str,
    after: str,
    state: str | None,
) -> None:
    """The Job ended its run on purpose, so the Status that it left is not a stop that nobody
    wrote."""
    number = seed_staged(store)
    _round(store, staged_repo)
    store.set_marks(_held(store), {Mark.RESULT: result})
    store.set_field(_held(store), ItemField.STATUS, status)
    _end(kube, "Complete")
    before = sum(_failures(c) for c in ("oom", "timeout", "provider", "parser"))

    _round(store, staged_repo)

    held = _held(store)
    assert (held.status, _record(store).get("implement.stopped")) == (after, None)
    assert _record(store)["implement.job_state"] == state
    assert sum(_failures(c) for c in ("oom", "timeout", "provider", "parser")) == before
    assert number == 1


@pytest.mark.usefixtures("app_slug", "no_continuation")
def test_no_result_a_job_that_left_no_result_gets_the_class_of_its_log(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    seed_staged(store)
    _round(store, staged_repo)
    name = kube.custom_objects.objects[JOBS][0]["metadata"]["name"]
    store.set_field(_held(store), ItemField.STATUS, "In Progress")
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = OUT_OF_MEMORY
    before = _failures("oom")

    _round(store, staged_repo)

    assert _failures("oom") - before == 1
    assert (_held(store).status, _record(store)["implement.failure"]) == ("Blocked", "oom")
    assert _record(store).get(RESULT) is None


@pytest.mark.usefixtures("app_slug", "no_continuation")
def test_no_result_a_stop_that_the_runner_wrote_keeps_its_class_with_the_result_stopped(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    seed_staged(store)
    _round(store, staged_repo)
    name = kube.custom_objects.objects[JOBS][0]["metadata"]["name"]
    store.set_field(
        _held(store),
        ItemField.STATUS,
        "Blocked",
        marks={
            ImplementRecordKey.STOPPED: "group 2",
            ImplementRecordKey.FAILURE: "timeout",
            Mark.RESULT: "stopped",
        },
    )
    _end(kube, "Failed")
    kube.core.answers["list_namespaced_pod"] = [pod(f"{name}-x1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = OUT_OF_MEMORY
    before = (_failures("timeout"), _failures("oom"))

    _round(store, staged_repo)

    assert (_failures("timeout") - before[0], _failures("oom") - before[1]) == (1, 0)
    assert (_record(store)["implement.failure"], _record(store).get(RESULT)) == (
        "timeout",
        "stopped",
    )


@pytest.mark.usefixtures("app_slug")
def test_no_result_a_new_job_clears_the_result_of_the_run_before(
    store: InMemoryRoadmapStore, staged_repo: StageRepo, api: GitHubApiFake, kube: FakeCluster
) -> None:
    """A Job that dies before its first write must not leave the result of the run before it."""
    seed_staged(store)
    store.set_marks(_held(store), {Mark.RESULT: "yielded"})

    _round(store, staged_repo)

    assert bool(_record(store).get("implement.job"))
    assert _raw_record(store).get(RESULT) is None


# ── handoff: the first step of a run gets the stop of the earlier Job ─────────────────────


def test_handoff_the_first_step_of_a_retry_gets_the_check_log_and_the_conflict_files(
    job_world: JobWorld,
) -> None:
    _stopped_with_a_log(job_world, retry=True)
    script = two_groups()

    applied = job_world.run(script)

    first = _prompt(script, 1)
    assert applied.ready == (1,)
    assert (HEADING in first, LOG in first) == (True, True)
    assert all(name in first for name in FILES)


def test_handoff_no_later_step_of_the_run_gets_it(job_world: JobWorld) -> None:
    _stopped_with_a_log(job_world, retry=True)
    script = two_groups()

    job_world.run(script)

    second = _prompt(script, 3)
    assert "Document the function" in second
    assert (HEADING in second, LOG in second, FILES[0] in second) == (False, False, False)


def test_handoff_the_first_step_after_a_clear_rule_of_the_service_gets_it_too(
    job_world: JobWorld,
) -> None:
    """The Service removed the stop and left the Job to take the item: no retry comment."""
    _stopped_with_a_log(job_world, retry=False)
    script = two_groups()

    job_world.run(script)

    first = _prompt(script, 1)
    assert (HEADING in first, LOG in first, FILES[1] in first) == (True, True, True)


def test_handoff_a_run_with_no_recorded_stop_gets_no_section(job_world: JobWorld) -> None:
    script = two_groups()

    job_world.run(script)

    assert HEADING not in _prompt(script, 1)


def test_handoff_the_keys_are_cleared_in_the_first_write_of_the_new_job(
    job_world: JobWorld,
) -> None:
    """A Job that starts after a clear rule clears both keys, and is killed in group 2: the
    record holds neither key, though the first step read them."""
    _stopped_with_a_log(job_world, retry=False)

    script = _killed_in_group_two(job_world)

    _, record = _item(job_world)
    assert LOG in _prompt(script, 1)
    assert (record.get("implement.check_log"), record.get("implement.conflict")) == (None, None)


def test_handoff_a_retry_clears_both_keys_in_the_first_write_of_the_new_job(
    job_world: JobWorld,
) -> None:
    _stopped_with_a_log(job_world, retry=True)

    _killed_in_group_two(job_world)

    _, record = _item(job_world)
    assert (record.get("implement.check_log"), record.get("implement.conflict")) == (None, None)
    assert record.get("implement.stopped") is None


def test_handoff_the_prompt_of_the_step_describes_the_section() -> None:
    prompt = fill_prompt(load_task_prompt("roadmap_implement_step.md"))

    assert HEADING.removeprefix("# ") in prompt
