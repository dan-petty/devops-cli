"""`devops roadmap implement --item <n> --confirm` outside a runner (#2913): the command starts the
runner Job through the code of `devops k8s run-job`, and refuses what cannot succeed. The cluster
is the fake `kubectl` of `tests/support/fakes/cluster_jobs.py`, the roadmap is in memory, and the
step itself is tested in `test_roadmap_implement_job.py`."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import GitHubState, ItemField
from tests.support.fakes.cluster_jobs import FakeJobs

REPO = "example/roadmap"
REPO_ENV = "DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY"
RUN_JOB = f"devops k8s run-job --template runner --repo {REPO} -- roadmap implement --repo {REPO}"


def _label(repo: str) -> str:
    """The value of the label `implement-repo` for `repo`, as the Service computes it."""
    from devops_cli.k8s.cluster_job import repository_label

    return repository_label(repo)


def _item(
    store: InMemoryRoadmapStore,
    status: str = "Ready",
    *labels: str,
    state: GitHubState = GitHubState.OPEN,
) -> int:
    return store.seed_issue(
        "Make the sample shout",
        labels=labels,
        state=state,
        fields={ItemField.STATUS: status, ItemField.PRIORITY: "P1-High"},
    )


def _implement(cli: Callable[..., Any], number: int | None, *flags: str, repo: bool = True) -> Any:
    item = ["--item", str(number)] if number is not None else []
    base = ["--repo", REPO] if repo else []
    return cli("roadmap", "implement", *base, *item, "--context", "test-ctx", *flags)


def _output(result: Any) -> str:
    return " ".join(result.output.split())


def _kubectl(cluster_jobs: FakeJobs, *verb: str) -> list[list[str]]:
    return [call for call in cluster_jobs.calls if call[3 : 3 + len(verb)] == list(verb)]


# ── The start ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("status", ["Ready", "Planned"])
def test_confirm_starts_the_runner_job_with_the_args_and_the_repository(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cluster_jobs: FakeJobs,
    status: str,
) -> None:
    number = _item(roadmap_store, status)

    result = _implement(cli, number, "--confirm")

    (job,) = cluster_jobs.created
    (container,) = job["spec"]["template"]["spec"]["containers"]
    assert (
        result.exit_code,
        job["metadata"]["name"].startswith("devops-cli-runner-"),
        container["name"],
        container["args"],
        {entry["name"]: entry["value"] for entry in container["env"]}[REPO_ENV],
        job["metadata"]["labels"]["implement-repo"],
        roadmap_store_repos,
        roadmap_store.job_writes(),
    ) == (
        0,
        True,
        "runner",
        ["roadmap", "implement", "--repo", REPO, "--item", str(number), "--confirm"],
        REPO,
        _label(REPO),
        [REPO],
        [],
    )


def test_confirm_follows_the_log_and_exits_with_the_exit_code_of_the_container(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, cluster_jobs: FakeJobs
) -> None:
    cluster_jobs.exit_code = "3"
    number = _item(roadmap_store)

    result = _implement(cli, number, "--confirm")

    name = cluster_jobs.created[0]["metadata"]["name"]
    assert (result.exit_code, _kubectl(cluster_jobs, "logs")) == (
        3,
        [["kubectl", "-n", "devops", "logs", "-f", f"job/{name}"]],
    )


def test_no_wait_prints_the_name_of_the_job_and_follows_nothing(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, cluster_jobs: FakeJobs
) -> None:
    number = _item(roadmap_store)

    result = _implement(cli, number, "--confirm", "--no-wait")

    name = cluster_jobs.created[0]["metadata"]["name"]
    assert (result.exit_code, name in _output(result), _kubectl(cluster_jobs, "logs")) == (
        0,
        True,
        [],
    )


def test_the_repository_is_the_origin_of_the_checkout_when_repo_is_not_given(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cluster_jobs: FakeJobs,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "devops_cli.commands.roadmap.get_repo_origin_name", lambda _: "example/origin"
    )
    number = _item(roadmap_store)

    result = _implement(cli, number, "--confirm", repo=False)

    (container,) = cluster_jobs.created[0]["spec"]["template"]["spec"]["containers"]
    assert (result.exit_code, container["args"][:4], roadmap_store_repos) == (
        0,
        ["roadmap", "implement", "--repo", "example/origin"],
        ["example/origin"],
    )


def test_an_item_that_the_service_holds_without_a_running_job_is_started(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, cluster_jobs: FakeJobs
) -> None:
    number = _item(roadmap_store, "Ready", "owner/service")

    result = _implement(cli, number, "--confirm")

    assert (result.exit_code, len(cluster_jobs.created)) == (0, 1)


# ── The refusals before the Job ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("owner", ["agent", "human"])
def test_an_item_that_another_owner_claimed_is_refused_and_no_request_reaches_the_cluster(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    cluster_jobs: FakeJobs,
    owner: str,
) -> None:
    number = _item(roadmap_store, "Ready", f"owner/{owner}")

    result = _implement(cli, number, "--confirm")

    assert (result.exit_code, owner in _output(result), cluster_jobs.calls) == (1, True, [])


@pytest.mark.parametrize("status", ["New", "In Progress", "In Review", "Blocked"])
def test_an_item_that_is_not_ready_or_planned_is_refused_and_names_its_status(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    cluster_jobs: FakeJobs,
    status: str,
) -> None:
    number = _item(roadmap_store, status)

    result = _implement(cli, number, "--confirm")

    assert (result.exit_code, status in _output(result), cluster_jobs.calls) == (1, True, [])


def test_an_issue_that_is_no_item_is_refused(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, cluster_jobs: FakeJobs
) -> None:
    result = _implement(cli, 99, "--confirm")

    assert (result.exit_code, "not an item of the roadmap" in _output(result)) == (1, True)
    assert cluster_jobs.calls == []


def test_a_closed_item_is_refused(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, cluster_jobs: FakeJobs
) -> None:
    number = _item(roadmap_store, "Ready", state=GitHubState.CLOSED)

    result = _implement(cli, number, "--confirm")

    assert (result.exit_code, "closed" in _output(result), cluster_jobs.calls) == (1, True, [])


def test_a_runner_job_of_the_repository_that_has_not_ended_refuses_the_start(
    cli: Callable[..., Any], roadmap_store: InMemoryRoadmapStore, cluster_jobs: FakeJobs
) -> None:
    cluster_jobs.listed = [{"metadata": {"name": "devops-cli-runner-20261031-010101-abcd"}}]
    number = _item(roadmap_store)

    result = _implement(cli, number, "--confirm")

    assert (
        result.exit_code,
        "devops-cli-runner-20261031-010101-abcd" in _output(result),
        cluster_jobs.created,
    ) == (1, True, [])


@pytest.mark.parametrize(
    ("flags", "option"),
    [
        (["--source", "."], "--source"),
        (["--filter", "status=ready"], "--filter"),
        (["--limit", "2"], "--limit"),
    ],
)
def test_an_option_that_needs_the_runner_is_refused_with_the_run_job_command(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cluster_jobs: FakeJobs,
    flags: list[str],
    option: str,
) -> None:
    number = _item(roadmap_store)

    result = _implement(cli, number, "--confirm", *flags)

    assert (
        result.exit_code,
        option in _output(result),
        RUN_JOB in _output(result),
        roadmap_store_repos,
        cluster_jobs.calls,
    ) == (1, True, True, [], [])


def test_a_start_with_no_item_names_the_setting_and_the_run_job_command(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cluster_jobs: FakeJobs,
) -> None:
    result = _implement(cli, None, "--confirm")

    assert (
        result.exit_code,
        "roadmap.implement.in_runner" in _output(result),
        RUN_JOB in _output(result),
        roadmap_store_repos,
        cluster_jobs.calls,
    ) == (1, True, True, [], [])


def test_a_step_with_confirm_names_the_command_that_starts_the_job(
    cli: Callable[..., Any], cluster_jobs: FakeJobs
) -> None:
    result = cli("roadmap", "implement", "--repo", REPO, "--item", "1", "--group", "1", "--confirm")

    assert (
        result.exit_code,
        "devops roadmap implement --item <n> --confirm" in _output(result),
        cluster_jobs.calls,
    ) == (1, True, [])


# ── The dry run ───────────────────────────────────────────────────────────────────────────


def test_a_dry_run_makes_no_request_and_prints_the_read_of_the_item_and_the_job(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cluster_jobs: FakeJobs,
) -> None:
    result = _implement(cli, 7, "--dry-run")

    output = _output(result)
    assert (
        result.exit_code,
        f"gh api repos/{REPO}/issues/7" in output,
        "get cronjob devops-cli-runner" in output,
        f"get jobs -l implement-repo={_label(REPO)}" in output,
        '"roadmap", "implement", "--repo", "example/roadmap", "--item", "7", "--confirm"'
        in " ".join(result.output.replace("\n", " ").split()),
        "no request was made" in output,
        roadmap_store_repos,
        cluster_jobs.calls,
    ) == (0, True, True, True, True, True, [], [])


def test_an_exported_dry_run_wins_over_confirm(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    cluster_jobs: FakeJobs,
) -> None:
    with patch("devops_cli.commands.roadmap.is_dry_run", return_value=True):
        result = _implement(cli, 7, "--confirm")

    assert (result.exit_code, roadmap_store_repos, cluster_jobs.calls) == (0, [], [])
    assert "no request was made" in _output(result)


# ── The guard of the pod ──────────────────────────────────────────────────────────────────


def test_in_a_runner_the_command_starts_no_job_and_keeps_the_guard(
    cli: Callable[..., Any],
    roadmap_store: InMemoryRoadmapStore,
    cluster_jobs: FakeJobs,
    config: Callable[..., Path],
) -> None:
    config(roadmap={"implement": {"in_runner": True}})
    number = _item(roadmap_store)

    result = _implement(cli, number, "--confirm")

    assert (
        result.exit_code,
        "runs only as the GitHub App" in _output(result),
        cluster_jobs.calls,
    ) == (1, True, [])
