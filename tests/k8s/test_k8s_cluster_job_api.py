"""The Kubernetes API calls of the Jobs that the roadmap Service creates (#2667).

The Kubernetes API is faked at its edge (`FakeCluster`). The CronJob template is the committed
manifest `k8s/devops/cronjob-runner.yaml`.
"""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

import pytest
import yaml

from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE
from devops_cli.k8s.cluster_job_api import ClusterJobs, JobState, job_state
from tests.support.fakes.kubernetes import FakeCluster, api_exception, pod
from tests.support.paths import REPO_ROOT

JOBS = ("batch", "v1", "jobs")
CRONJOBS = ("batch", "v1", "cronjobs")


def _job(name: str, labels: dict[str, str] | None = None, *conditions: tuple[str, str]) -> Any:
    return {
        "metadata": {"name": name, "namespace": "devops", "labels": labels or {}},
        "status": {"conditions": [{"type": t, "status": s} for t, s in conditions]},
    }


@pytest.fixture
def kube(cluster: FakeCluster) -> FakeCluster:
    template = yaml.safe_load((REPO_ROOT / "k8s/devops/cronjob-runner.yaml").read_text("utf-8"))
    cluster.custom_objects.objects[CRONJOBS] = [copy.deepcopy(template)]
    return cluster


@pytest.mark.parametrize(
    ("conditions", "expected"),
    [
        ((), JobState.RUNNING),
        ((("Complete", "False"),), JobState.RUNNING),
        ((("Complete", "True"),), JobState.SUCCEEDED),
        ((("Failed", "True"),), JobState.FAILED),
        ((("Suspended", "True"),), JobState.RUNNING),
    ],
)
def test_a_job_has_ended_only_with_the_condition_complete_or_failed_set_true(
    conditions: tuple[tuple[str, str], ...], expected: JobState
) -> None:
    assert job_state(_job("devops-cli-runner-a", None, *conditions)) == expected


def test_a_job_that_has_no_status_yet_is_running() -> None:
    assert job_state({"metadata": {"name": "devops-cli-runner-a"}}) == JobState.RUNNING


def test_the_list_of_jobs_asks_the_api_for_the_labels_and_gives_name_and_state(
    kube: FakeCluster,
) -> None:
    kube.custom_objects.objects[JOBS] = [
        _job("devops-cli-runner-a", {"implement-repo": "aaaa"}, ("Failed", "True")),
        _job("devops-cli-runner-b", {"implement-repo": "bbbb"}),
        _job("devops-cli-runner-c", {"implement-repo": "aaaa"}),
        _job("devops-cli-runner-d"),
    ]

    listed = ClusterJobs().list_jobs({"implement-repo": "aaaa"})

    (call,) = [c for c in kube.custom_objects.calls if c[0] == "list_namespaced_custom_object"]
    assert (
        [(job.name, job.state) for job in listed],
        call[1]["label_selector"],
        call[1]["namespace"],
    ) == (
        [
            ("devops-cli-runner-a", JobState.FAILED),
            ("devops-cli-runner-c", JobState.RUNNING),
        ],
        "implement-repo=aaaa",
        "devops",
    )


def test_a_job_is_created_from_the_cronjob_with_the_args_env_and_labels_given(
    kube: FakeCluster,
) -> None:
    name = ClusterJobs().create(
        ["roadmap", "implement", "--item", "7"],
        template=RUNNER_TEMPLATE,
        env={"A_SETTING": "value"},
        labels={"implement-repo": "aaaa"},
    )

    (job,) = kube.custom_objects.objects[JOBS]
    (container,) = job["spec"]["template"]["spec"]["containers"]
    assert (
        name == job["metadata"]["name"],
        name.startswith("devops-cli-runner-"),
        container["args"],
        {"name": "A_SETTING", "value": "value"} in container["env"],
        job["metadata"]["labels"]["implement-repo"],
        job["metadata"]["namespace"],
    ) == (True, True, ["roadmap", "implement", "--item", "7"], True, "aaaa", "devops")


def test_a_job_takes_the_name_the_caller_chose(kube: FakeCluster) -> None:
    """The Service records the name on the item before it creates the Job."""
    name = ClusterJobs().create(["roadmap"], template=RUNNER_TEMPLATE, name="devops-cli-runner-x")

    (job,) = kube.custom_objects.objects[JOBS]
    assert (name, job["metadata"]["name"]) == ("devops-cli-runner-x", "devops-cli-runner-x")


def test_a_missing_cronjob_is_an_error_that_names_it_and_creates_no_job(
    cluster: FakeCluster,
) -> None:
    with pytest.raises(ClusterJobError, match="CronJob devops/devops-cli-runner not found"):
        ClusterJobs().create(["roadmap"], template=RUNNER_TEMPLATE)

    assert JOBS not in cluster.custom_objects.objects


DIGEST = "sha256:" + "a" * 64


def _set_image(kube: FakeCluster, image: str) -> None:
    cronjob = kube.custom_objects.objects[CRONJOBS][0]
    (container,) = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][:1]
    container["image"] = image


@pytest.mark.parametrize(
    ("image", "digest"),
    [
        (f"ghcr.io/example/runner:latest@{DIGEST}", DIGEST),
        (f"ghcr.io/example/runner@{DIGEST}", DIGEST),
        ("ghcr.io/example/runner:latest", None),
        ("ghcr.io/example/runner", None),
    ],
)
def test_the_digest_of_the_template_is_the_text_after_the_at_sign_of_its_image(
    kube: FakeCluster, image: str, digest: str | None
) -> None:
    _set_image(kube, image)

    assert ClusterJobs().template_digest(RUNNER_TEMPLATE) == digest


def test_a_job_made_from_the_template_runs_the_digest_that_the_template_names(
    kube: FakeCluster,
) -> None:
    """The record of the Service is the digest of the template at the create: the Job has the
    same image."""
    _set_image(kube, f"ghcr.io/example/runner:latest@{DIGEST}")

    digest = ClusterJobs().template_digest(RUNNER_TEMPLATE)
    ClusterJobs().create(["roadmap"], template=RUNNER_TEMPLATE)

    (job,) = kube.custom_objects.objects[JOBS]
    (container,) = job["spec"]["template"]["spec"]["containers"][:1]
    assert container["image"].partition("@")[2] == digest


def test_the_digest_of_a_missing_cronjob_is_an_error_that_names_it(cluster: FakeCluster) -> None:
    with pytest.raises(ClusterJobError, match="CronJob devops/devops-cli-runner not found"):
        ClusterJobs().template_digest(RUNNER_TEMPLATE)


def test_the_digest_of_a_template_without_the_container_is_an_error(kube: FakeCluster) -> None:
    cronjob = kube.custom_objects.objects[CRONJOBS][0]
    cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["name"] = "other"

    with pytest.raises(ClusterJobError, match="has no container runner"):
        ClusterJobs().template_digest(RUNNER_TEMPLATE)


def test_a_refusal_of_the_api_is_an_error_that_names_the_action_and_the_status(
    kube: FakeCluster,
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise api_exception(403, "Forbidden")

    kube.custom_objects.create_namespaced_custom_object = refuse  # type: ignore[method-assign]

    with pytest.raises(ClusterJobError, match="create Job in namespace devops: HTTP 403 Forbidden"):
        ClusterJobs().create(["roadmap"], template=RUNNER_TEMPLATE)


def test_a_refused_list_of_jobs_is_an_error_that_names_the_status(kube: FakeCluster) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise api_exception(403, "Forbidden")

    kube.custom_objects.list_namespaced_custom_object = refuse  # type: ignore[method-assign]

    with pytest.raises(ClusterJobError, match="list Jobs in namespace devops: HTTP 403"):
        ClusterJobs().list_jobs({"implement-repo": "aaaa"})


def test_the_log_tail_is_read_from_the_pod_of_the_job(kube: FakeCluster) -> None:
    kube.core.answers["list_namespaced_pod"] = [pod("job-x-1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = "line 1\nline 2\n"

    tail = ClusterJobs().log_tail("job-x", 40)

    selector = next(c for c in kube.core.calls if c[0] == "list_namespaced_pod")[1]
    log = next(c for c in kube.core.calls if c[0] == "read_namespaced_pod_log")[1]
    assert (
        tail,
        selector["label_selector"],
        (log["name"], log["namespace"], log["tail_lines"]),
    ) == ("line 1\nline 2\n", "batch.kubernetes.io/job-name=job-x", ("job-x-1", "devops", 40))


@pytest.mark.parametrize(
    "written",
    ["\N{CHECK MARK} Took 1 item(s).\nline 2\n", b"\xe2\x9c\x93 Took 1 item(s).\nline 2\n"],
)
def test_the_log_tail_is_the_text_the_pod_wrote_with_real_line_breaks(
    kube: FakeCluster, written: str | bytes
) -> None:
    kube.core.answers["list_namespaced_pod"] = [pod("job-x-1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = written

    assert ClusterJobs().log_tail("job-x", 40) == "\N{CHECK MARK} Took 1 item(s).\nline 2\n"


def test_the_log_tail_replaces_a_byte_that_is_not_utf_8(kube: FakeCluster) -> None:
    kube.core.answers["list_namespaced_pod"] = [pod("job-x-1", namespace="devops")]
    kube.core.answers["read_namespaced_pod_log"] = b"ok \xff done\n"

    assert ClusterJobs().log_tail("job-x", 40) == "ok \N{REPLACEMENT CHARACTER} done\n"


def test_a_job_with_no_pod_has_an_empty_log_tail(kube: FakeCluster) -> None:
    assert ClusterJobs().log_tail("job-x", 40) == ""


def test_a_listed_job_carries_its_start_time_its_deadline_and_its_annotations(
    kube: FakeCluster,
) -> None:
    started = _job("devops-cli-runner-a", {"implement-repo": "aaaa"})
    started["metadata"]["annotations"] = {"roadmap.devops-cli/progress-at": "1700000000"}
    started["spec"] = {"activeDeadlineSeconds": 3600}
    started["status"]["startTime"] = "2026-11-02T10:00:00Z"
    kube.custom_objects.objects[JOBS] = [
        started,
        _job("devops-cli-runner-b", {"implement-repo": "aaaa"}),
    ]

    first, second = ClusterJobs().list_jobs({"implement-repo": "aaaa"})

    assert (
        first.started,
        first.deadline,
        dict(first.annotations),
        second.started,
        second.deadline,
        dict(second.annotations),
    ) == (
        datetime(2026, 11, 2, 10, 0, tzinfo=UTC),
        3600,
        {"roadmap.devops-cli/progress-at": "1700000000"},
        None,
        None,
        {},
    )


def test_a_job_is_created_with_the_deadline_and_the_annotations_given(kube: FakeCluster) -> None:
    ClusterJobs().create(
        ["roadmap"],
        template=RUNNER_TEMPLATE,
        deadline=3600,
        annotations={"roadmap.devops-cli/progress-at": "1700000000"},
    )

    (job,) = kube.custom_objects.objects[JOBS]
    assert (
        job["spec"]["activeDeadlineSeconds"],
        job["metadata"]["annotations"],
    ) == (3600, {"roadmap.devops-cli/progress-at": "1700000000"})


def test_a_job_is_created_with_the_resources_given_and_keeps_the_other_values_of_the_template(
    kube: FakeCluster,
) -> None:
    ClusterJobs().create(
        ["roadmap"],
        template=RUNNER_TEMPLATE,
        resources={
            "requests": {"cpu": "1", "memory": "2Gi"},
            "limits": {"cpu": "1", "memory": "12Gi"},
        },
        env={"PYTEST_XDIST_AUTO_NUM_WORKERS": "1"},
    )

    (job,) = kube.custom_objects.objects[JOBS]
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry["value"] for entry in container["env"]}
    assert (container["resources"], env["PYTEST_XDIST_AUTO_NUM_WORKERS"]) == (
        {
            "requests": {"cpu": "1", "memory": "2Gi", "ephemeral-storage": "2Gi"},
            "limits": {"cpu": "1", "memory": "12Gi", "ephemeral-storage": "6Gi"},
        },
        "1",
    )


def test_a_job_keeps_the_resources_of_the_template_when_the_caller_gives_none(
    kube: FakeCluster,
) -> None:
    ClusterJobs().create(["roadmap"], template=RUNNER_TEMPLATE)

    (job,) = kube.custom_objects.objects[JOBS]
    (container,) = job["spec"]["template"]["spec"]["containers"]
    assert container["resources"] == {
        "requests": {"cpu": "2", "memory": "4Gi", "ephemeral-storage": "2Gi"},
        "limits": {"cpu": "2", "memory": "8Gi", "ephemeral-storage": "6Gi"},
    }


def test_a_job_keeps_the_deadline_of_the_template_when_the_caller_gives_none(
    kube: FakeCluster,
) -> None:
    ClusterJobs().create(["roadmap"], template=RUNNER_TEMPLATE)

    (job,) = kube.custom_objects.objects[JOBS]
    assert (job["spec"]["activeDeadlineSeconds"], "annotations" in job["metadata"]) == (7200, False)


def test_a_patch_sets_the_deadline_and_merges_the_annotations_of_the_job(
    kube: FakeCluster,
) -> None:
    job = _job("devops-cli-runner-a", {"implement-repo": "aaaa"})
    job["metadata"]["annotations"] = {"kept": "yes", "roadmap.devops-cli/progress": "old"}
    job["spec"] = {"activeDeadlineSeconds": 3600, "backoffLimit": 0}
    kube.custom_objects.objects[JOBS] = [job]

    ClusterJobs().patch_job(
        "devops-cli-runner-a", deadline=5400, annotations={"roadmap.devops-cli/progress": "new"}
    )

    (patched,) = kube.custom_objects.objects[JOBS]
    (call,) = [c for c in kube.custom_objects.calls if c[0] == "patch_namespaced_custom_object"]
    assert (
        patched["spec"],
        patched["metadata"]["annotations"],
        call[1]["name"],
        call[1]["plural"],
    ) == (
        {"activeDeadlineSeconds": 5400, "backoffLimit": 0},
        {"kept": "yes", "roadmap.devops-cli/progress": "new"},
        "devops-cli-runner-a",
        "jobs",
    )


def test_a_patch_without_a_deadline_leaves_the_spec_alone(kube: FakeCluster) -> None:
    job = _job("devops-cli-runner-a")
    job["spec"] = {"activeDeadlineSeconds": 3600}
    kube.custom_objects.objects[JOBS] = [job]

    ClusterJobs().patch_job("devops-cli-runner-a", annotations={"a": "b"})

    (call,) = [c for c in kube.custom_objects.calls if c[0] == "patch_namespaced_custom_object"]
    assert call[1]["body"] == {"metadata": {"annotations": {"a": "b"}}}


def test_a_refused_patch_is_an_error_that_names_the_action_and_the_status(
    kube: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise api_exception(403, "Forbidden")

    monkeypatch.setattr(kube.custom_objects, "patch_namespaced_custom_object", refuse)

    with pytest.raises(ClusterJobError, match="patch Job in namespace devops: HTTP 403 Forbidden"):
        ClusterJobs().patch_job("devops-cli-runner-a", deadline=5400)


DEPLOYMENTS = ("apps", "v1", "deployments")
SERVICE_DIGEST = "sha256:" + "5" * 64


def _deployment(image: str) -> dict[str, Any]:
    return {
        "metadata": {"name": "roadmap-service", "namespace": "devops"},
        "spec": {"template": {"spec": {"containers": [{"name": "service", "image": image}]}}},
    }


def test_the_digest_of_a_deployment_is_the_text_after_the_at_of_its_container_image(
    cluster: FakeCluster,
) -> None:
    image = f"ghcr.io/example/devops-cli/service@{SERVICE_DIGEST}"
    cluster.custom_objects.objects[DEPLOYMENTS] = [_deployment(image)]

    assert ClusterJobs().deployment_digest("roadmap-service", "service") == SERVICE_DIGEST


def test_an_image_with_no_digest_gives_none(cluster: FakeCluster) -> None:
    cluster.custom_objects.objects[DEPLOYMENTS] = [
        _deployment("ghcr.io/example/devops-cli/service")
    ]

    assert ClusterJobs().deployment_digest("roadmap-service", "service") is None


def test_a_missing_deployment_and_a_missing_container_raise(cluster: FakeCluster) -> None:
    with pytest.raises(ClusterJobError, match="Deployment devops/roadmap-service not found"):
        ClusterJobs().deployment_digest("roadmap-service", "service")

    cluster.custom_objects.objects[DEPLOYMENTS] = [_deployment("ghcr.io/e/s@" + SERVICE_DIGEST)]
    with pytest.raises(ClusterJobError, match="no container sidecar"):
        ClusterJobs().deployment_digest("roadmap-service", "sidecar")


def test_a_refused_read_of_a_deployment_raises(
    cluster: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise api_exception(403, "Forbidden")

    monkeypatch.setattr(cluster.custom_objects, "get_namespaced_custom_object", refuse)

    with pytest.raises(ClusterJobError, match="read Deployment in namespace devops: HTTP 403"):
        ClusterJobs().deployment_digest("roadmap-service", "service")


def test_a_delete_removes_the_job_and_lets_the_garbage_collector_remove_its_pods(
    kube: FakeCluster,
) -> None:
    kube.custom_objects.objects[JOBS] = [_job("devops-cli-stage-a"), _job("devops-cli-stage-b")]

    ClusterJobs().delete_job("devops-cli-stage-a")

    (call,) = [c for c in kube.custom_objects.calls if c[0] == "delete_namespaced_custom_object"]
    assert (
        [job["metadata"]["name"] for job in kube.custom_objects.objects[JOBS]],
        call[1]["name"],
        call[1]["plural"],
        call[1]["namespace"],
        call[1]["propagation_policy"],
    ) == (["devops-cli-stage-b"], "devops-cli-stage-a", "jobs", "devops", "Background")


def test_a_delete_of_a_job_that_is_gone_is_no_error(kube: FakeCluster) -> None:
    ClusterJobs().delete_job("devops-cli-stage-gone")

    assert [c[0] for c in kube.custom_objects.calls] == ["delete_namespaced_custom_object"]


def test_a_refused_delete_is_an_error_that_names_the_action_and_the_status(
    kube: FakeCluster, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*_: Any, **__: Any) -> Any:
        raise api_exception(403, "Forbidden")

    monkeypatch.setattr(kube.custom_objects, "delete_namespaced_custom_object", refuse)

    with pytest.raises(ClusterJobError, match="delete Job in namespace devops: HTTP 403 Forbidden"):
        ClusterJobs().delete_job("devops-cli-runner-a")


def test_a_create_of_a_job_that_exists_raises_the_exists_error_and_keeps_the_job(
    kube: FakeCluster,
) -> None:
    """The name of a stage Job comes from its inputs, so a second create of it gets 409 (#4559)."""
    from devops_cli.exceptions.k8s import ClusterJobExistsError

    jobs = ClusterJobs()
    jobs.create(["--version"], template=RUNNER_TEMPLATE, name="devops-cli-stage-a-1-0123456789")

    with pytest.raises(ClusterJobExistsError, match="exists already"):
        jobs.create(["--version"], template=RUNNER_TEMPLATE, name="devops-cli-stage-a-1-0123456789")
    assert len(kube.custom_objects.objects[JOBS]) == 1


def test_a_listed_job_carries_its_labels_and_the_reason_and_message_of_its_failure(
    kube: FakeCluster,
) -> None:
    """The Service reads the item of a stage Job from its labels, and the end of a failed Job
    from the reason and the message of its condition Failed (#4559)."""
    failed = _job("devops-cli-stage-a-1-0123456789", {"roadmap.devops-cli/item": "1"})
    failed["status"]["conditions"] = [
        {"type": "FailureTarget", "status": "True", "reason": "DeadlineExceeded"},
        {
            "type": "Failed",
            "status": "True",
            "reason": "DeadlineExceeded",
            "message": "Job was active longer than specified deadline",
        },
    ]
    kube.custom_objects.objects[JOBS] = [failed, _job("devops-cli-stage-a-2-0123456789")]

    listed = ClusterJobs().list_jobs({})

    assert [(job.labels, job.reason, job.message) for job in listed] == [
        (
            {"roadmap.devops-cli/item": "1"},
            "DeadlineExceeded",
            "Job was active longer than specified deadline",
        ),
        ({}, "", ""),
    ]
