"""The Job that a CronJob's template makes: the stage Job of one item (#5483).

The CronJob template has the shape of each template (`tests.support.job_templates`), not the values
of a committed manifest.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import (
    PLANNER_TEMPLATE,
    RUNNER_TEMPLATE,
    STAGE_TEMPLATE,
    TemplateName,
    build_job,
    image_digest,
    runner_job_labels,
    runner_job_name,
    stage_job_env,
    stage_job_labels,
    stage_job_name,
    template_container,
)
from tests.support.job_templates import (
    PHASE_RESOURCES,
    cronjob_template,
    phase_cronjob_template,
)

REPO = RepoRef("Example/Project")
DEADLINE = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
ARGS = ["roadmap", "stage", "--repo", "Example/Project", "--job-item", "42", "--confirm"]


def _stage_job(item: int = 42, plan_key: str = "body-hash") -> dict[str, Any]:
    name = stage_job_name(REPO, item, plan_key)
    return build_job(
        cronjob_template(STAGE_TEMPLATE),
        ARGS,
        name,
        template=STAGE_TEMPLATE,
        env=stage_job_env(REPO, name, DEADLINE),
        labels=stage_job_labels(REPO, item),
    )


def test_the_stage_template_is_the_cronjob_roadmap_stage_and_its_container_stage() -> None:
    assert (
        TemplateName.STAGE.template,
        STAGE_TEMPLATE.cronjob,
        STAGE_TEMPLATE.container,
    ) == (STAGE_TEMPLATE, "roadmap-stage", "stage")


def test_the_args_go_to_the_container_stage() -> None:
    (container,) = _stage_job()["spec"]["template"]["spec"]["containers"]

    assert (container["name"], container["args"]) == ("stage", ARGS)


def test_the_job_and_its_pod_carry_the_component_owner_repo_and_item_labels() -> None:
    job = _stage_job()
    wanted = {
        "app.kubernetes.io/name": "devops-cli-job",
        "app.kubernetes.io/component": "roadmap-stage",
        "roadmap.devops-cli/owner": "example",
        "roadmap.devops-cli/repo": "project",
        "roadmap.devops-cli/item": "42",
    }

    assert (
        wanted.items() <= job["metadata"]["labels"].items(),
        wanted.items() <= job["spec"]["template"]["metadata"]["labels"].items(),
    ) == (True, True)


@pytest.mark.parametrize("name", ["a", "a-very-long-repository-name-" * 4])
def test_the_name_has_at_most_63_characters_and_starts_with_the_stage_prefix(name: str) -> None:
    job_name = stage_job_name(RepoRef(f"example/{name}"), 123456, "body-hash")

    assert (len(job_name) <= 63, job_name.startswith("devops-cli-stage-")) == (True, True)


def test_the_same_item_and_plan_key_give_the_same_name_and_another_key_another_name() -> None:
    first = stage_job_name(REPO, 42, "body-hash")

    assert (
        stage_job_name(RepoRef("example/project"), 42, "body-hash"),
        stage_job_name(REPO, 42, "other-hash") != first,
        stage_job_name(REPO, 43, "body-hash") != first,
    ) == (first, True, True)


def test_the_job_names_itself_its_deadline_and_the_repository_of_its_token() -> None:
    job = _stage_job()
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry.get("value") for entry in container["env"]}

    assert (
        env["DEVOPS_CLI_ROADMAP_STAGE_JOB"],
        env["DEVOPS_CLI_ROADMAP_STAGE_JOB_DEADLINE"],
        env["DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY"],
    ) == (job["metadata"]["name"], "2026-11-13T15:00:00+00:00", "Example/Project")


def test_runner_job_labels_and_annotation_reach_job_and_pod() -> None:
    cronjob = cronjob_template(RUNNER_TEMPLATE)
    repo = RepoRef("Dan-Petty/DevOps-CLI")
    item = 4558
    name = runner_job_name(repo, item)
    job = build_job(
        cronjob,
        ["roadmap", "implement", "--repo", repo.display, "--item", str(item), "--confirm"],
        name,
        template=RUNNER_TEMPLATE,
        repo=repo,
        item=item,
    )
    wanted_labels = {
        "app.kubernetes.io/name": "devops-cli-job",
        "app.kubernetes.io/component": "roadmap-implement",
        "app.kubernetes.io/part-of": "devops-cli-stack",
        "app.kubernetes.io/managed-by": "devops-cli",
        "roadmap.devops-cli/owner": "dan-petty",
        "roadmap.devops-cli/repo": "devops-cli",
        "roadmap.devops-cli/item": "4558",
        "implement-repo": repo.id,
    }
    wanted_annotation = {"roadmap.devops-cli/repository": "dan-petty/devops-cli"}

    assert (
        wanted_labels.items() <= job["metadata"]["labels"].items(),
        wanted_labels.items() <= job["spec"]["template"]["metadata"]["labels"].items(),
        wanted_annotation.items() <= job["metadata"].get("annotations", {}).items(),
        wanted_annotation.items()
        <= job["spec"]["template"]["metadata"].get("annotations", {}).items(),
    ) == (True, True, True, True)


@pytest.mark.parametrize("name", ["devops-cli", "a-very-long-repository-name-" * 4])
def test_runner_job_name_matches_adhoc_naming_rules(name: str) -> None:
    repo = RepoRef(f"dan-petty/{name}")
    job_name = runner_job_name(repo, 4558)

    assert (len(job_name) <= 63, job_name.startswith("devops-cli-implement-")) == (True, True)


def test_runner_job_labels_builds_expected_labels() -> None:
    repo = RepoRef("Dan-Petty/DevOps-CLI")
    labels = runner_job_labels(repo, 4558)
    assert labels == {
        "app.kubernetes.io/component": "roadmap-implement",
        "app.kubernetes.io/part-of": "devops-cli-stack",
        "app.kubernetes.io/managed-by": "devops-cli",
        "roadmap.devops-cli/owner": "dan-petty",
        "roadmap.devops-cli/repo": "devops-cli",
        "roadmap.devops-cli/item": "4558",
        "implement-repo": repo.id,
    }


def test_a_planner_job_keeps_the_planner_name_label_on_the_job_and_pod() -> None:
    """The admission policy and the deny-all NetworkPolicy select the planner pod by its own name
    label, so `build_job` sets it on the Job and on its pod (#4003)."""
    job = build_job(
        cronjob_template(PLANNER_TEMPLATE),
        ["--version"],
        "devops-cli-planner-run-20261114-120000-ab12",
        template=PLANNER_TEMPLATE,
    )

    assert (
        job["metadata"]["labels"]["app.kubernetes.io/name"],
        job["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"],
    ) == ("devops-cli-planner-run", "devops-cli-planner-run")


RUN_ARGS = ["roadmap", "implement", "--repo", "Example/Project", "--item", "42"]
TRACE = {"TRACEPARENT": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
SIZE = {"limits": {"memory": "4Gi"}}


def _runner_job(cronjob: dict[str, Any]) -> dict[str, Any]:
    return build_job(
        cronjob, RUN_ARGS, "job-x", template=RUNNER_TEMPLATE, env=TRACE, resources=SIZE
    )


def _containers(job: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pod_spec = job["spec"]["template"]["spec"]
    listed = [*pod_spec.get("initContainers", []), *pod_spec["containers"]]
    return {container["name"]: container for container in listed}


def _env(container: dict[str, Any]) -> dict[str, str]:
    return {entry["name"]: entry.get("value", "") for entry in container.get("env", [])}


def test_the_one_container_runner_template_runs_the_command_with_its_trace_and_size() -> None:
    """The runner template of today keeps its one container `runner`, and the command runs every
    phase in it (#6690)."""
    (runner,) = _containers(_runner_job(cronjob_template(RUNNER_TEMPLATE))).values()
    assert (
        runner["name"],
        runner["args"],
        _env(runner)["TRACEPARENT"],
        runner["resources"]["limits"]["memory"],
    ) == ("runner", RUN_ARGS, TRACE["TRACEPARENT"], "4Gi")


def test_each_phase_container_runs_its_phase_on_the_run_folder_with_one_trace() -> None:
    """On the phases, each container runs the command with its own `--phase` on the run folder,
    and all three get the same trace context. Only `agent` gets the size of the unit; `prepare`
    and `publish` keep the small row of the template (#3700, #6690)."""
    containers = _containers(_runner_job(phase_cronjob_template(RUNNER_TEMPLATE)))
    assert {
        name: (
            container["args"],
            _env(container)["TRACEPARENT"],
            container["resources"]["limits"]["memory"],
        )
        for name, container in containers.items()
    } == {
        phase: (
            [*RUN_ARGS, "--phase", phase, "--work", "/run/roadmap"],
            TRACE["TRACEPARENT"],
            "4Gi" if phase == "agent" else PHASE_RESOURCES["limits"]["memory"],
        )
        for phase in ("prepare", "agent", "publish")
    }


@pytest.mark.parametrize(
    ("cronjob", "name", "found"),
    [
        (cronjob_template(RUNNER_TEMPLATE), None, "runner"),
        (phase_cronjob_template(RUNNER_TEMPLATE), "agent", "agent"),
        (phase_cronjob_template(RUNNER_TEMPLATE), "publish", "publish"),
    ],
    ids=["one-container", "init-container", "app-container"],
)
def test_the_template_container_is_found_by_its_name(
    cronjob: dict[str, Any], name: str | None, found: str
) -> None:
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    assert template_container(pod_spec, RUNNER_TEMPLATE, name)["name"] == found


@pytest.mark.parametrize(
    "make", [cronjob_template, phase_cronjob_template], ids=["one-container", "phases"]
)
def test_the_image_digest_is_read_from_either_template(make: Any) -> None:
    cronjob = make(RUNNER_TEMPLATE, image="registry.example.com/runner@sha256:abc")
    assert image_digest(cronjob, RUNNER_TEMPLATE) == "sha256:abc"
