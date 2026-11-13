"""The Job that a CronJob's template makes: the stage Job of one item (#5483).

The CronJob template is the committed manifest `k8s/devops/cronjob-stage.yaml`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
import yaml

from devops_cli.github.repo_ref import RepoRef
from devops_cli.k8s.cluster_job import (
    STAGE_TEMPLATE,
    TemplateName,
    build_job,
    stage_job_env,
    stage_job_labels,
    stage_job_name,
)
from tests.support.paths import REPO_ROOT

REPO = RepoRef("Example/Project")
DEADLINE = datetime(2026, 11, 13, 15, 0, tzinfo=UTC)
ARGS = ["roadmap", "stage", "--repo", "Example/Project", "--job-item", "42", "--confirm"]


def _cronjob() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(
        (REPO_ROOT / "k8s/devops/cronjob-stage.yaml").read_text(encoding="utf-8")
    )
    return loaded


def _stage_job(item: int = 42, plan_key: str = "body-hash") -> dict[str, Any]:
    name = stage_job_name(REPO, item, plan_key)
    return build_job(
        _cronjob(),
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
