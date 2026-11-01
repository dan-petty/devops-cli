"""The Kubernetes API calls of the Jobs that the roadmap Service creates (#2667).

The Kubernetes API is faked at its edge (`FakeCluster`). The CronJob template is the committed
manifest `k8s/devops/cronjob-runner.yaml`.
"""

from __future__ import annotations

import copy
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


def test_a_job_with_no_pod_has_an_empty_log_tail(kube: FakeCluster) -> None:
    assert ClusterJobs().log_tail("job-x", 40) == ""
