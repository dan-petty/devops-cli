"""`devops k8s run-job`: a Job from CronJob devops-cli's template, followed to its exit code."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from typing import Any

import pytest
import typer
from click.testing import CliRunner

from devops_cli.commands.k8s.cluster_jobs import run_job
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, build_job, job_name, repository_label
from tests.support.fakes.cluster_jobs import CRONJOB, FakeJobs, runner_cronjob_manifest

REPO = "example/roadmap"
REPO_ENV = "DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY"
LOCK_LABEL = "implement-repo"

_app = typer.Typer()
_app.command()(run_job)
RUN_JOB = typer.main.get_command(_app)


def _run(*args: str) -> Any:
    return CliRunner().invoke(RUN_JOB, ["--context", "test-ctx", *args])


def _without(job: dict[str, Any]) -> dict[str, Any]:
    """The Job with args, name and the job label taken back out."""
    stripped = copy.deepcopy(job)
    for metadata in (stripped["metadata"], stripped["spec"]["template"]["metadata"]):
        metadata.get("labels", {}).pop("app.kubernetes.io/name", None)
    stripped["metadata"].pop("name")
    stripped["metadata"].pop("namespace")
    stripped["spec"]["template"]["spec"]["containers"][0].pop("args")
    return stripped


def test_the_job_equals_the_template_but_for_args_name_and_label() -> None:
    job = build_job(CRONJOB, ["ai", "gateway", "status"], "devops-cli-20261004-020000-abcd")
    template = copy.deepcopy(CRONJOB["spec"]["jobTemplate"])
    template["spec"]["template"]["metadata"]["labels"].pop("app.kubernetes.io/name")
    template["spec"]["template"]["spec"]["containers"][0].pop("args")
    assert (
        _without(job)["spec"],
        job["metadata"]["name"],
        job["metadata"]["labels"]["app.kubernetes.io/name"],
        job["spec"]["template"]["metadata"]["labels"]["app.kubernetes.io/name"],
        job["spec"]["template"]["spec"]["containers"][0]["args"],
    ) == (
        template["spec"],
        "devops-cli-20261004-020000-abcd",
        "devops-cli-job",
        "devops-cli-job",
        ["ai", "gateway", "status"],
    )


def test_a_template_without_the_devops_cli_container_is_refused() -> None:
    broken = copy.deepcopy(CRONJOB)
    broken["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["name"] = "other"
    with pytest.raises(ClusterJobError) as raised:
        build_job(broken, ["--version"], "devops-cli-x")
    assert raised.value.error_code == "K8S_CLUSTER_JOB_ERROR"


def test_job_names_carry_utc_time_and_four_hex() -> None:
    name = job_name(datetime(2026, 10, 4, 2, 14, 5, tzinfo=UTC))
    assert (name[:27], len(name), int(name[-4:], 16) >= 0) == (
        "devops-cli-20261004-021405-",
        31,
        True,
    )


def test_the_command_exits_with_the_containers_exit_code(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.exit_code = "3"
    result = _run("--", "no-such-command", "--dry-run")
    created = cluster_jobs.created[0]
    assert (
        result.exit_code,
        created["spec"]["template"]["spec"]["containers"][0]["args"],
        ["kubectl", "-n", "devops", "logs", "-f", f"job/{created['metadata']['name']}"]
        in cluster_jobs.calls,
    ) == (3, ["no-such-command", "--dry-run"], True)


def test_no_wait_creates_the_job_and_prints_its_name(cluster_jobs: FakeJobs) -> None:
    result = _run("--no-wait", "--", "--version")
    name = cluster_jobs.created[0]["metadata"]["name"]
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        name in output,
        f"kubectl -n devops logs -f job/{name}" in output,
    ) == (
        0,
        True,
        True,
    )
    assert [c for c in cluster_jobs.calls if "logs" in c] == []


def test_dry_run_makes_no_request_and_prints_the_requests_in_order() -> None:
    result = _run("--dry-run", "--", "ai", "gateway", "status")
    output = result.output
    order = [
        "kubectl -n devops get cronjob devops-cli --ignore-not-found -o json --context test-ctx",
        "kubectl -n devops create -f - -o name --context test-ctx",
        '"args": [',
        "kubectl -n devops get pods -l "
        "'batch.kubernetes.io/job-name=<devops-cli-yyyymmdd-hhmmss-xxxx>'",
        "kubectl -n devops logs -f 'job/<devops-cli-yyyymmdd-hhmmss-xxxx>' --context test-ctx",
        "state.terminated.exitCode",
    ]
    positions = [output.find(text) for text in order]
    assert (
        result.exit_code,
        result.exception,
        -1 in positions,
        positions == sorted(positions),
        "no request was made" in output,
    ) == (0, None, False, True, True), output


def test_dry_run_with_no_wait_lists_only_the_read_and_the_create() -> None:
    from devops_cli.commands.k8s.cluster_jobs import JobRun, dry_run_job

    result = dry_run_job(["--version"], "test-ctx", wait=False, start_timeout=5.0)
    assert (
        type(result),
        result.dry_run,
        result.exit_code,
        [r.method for r in result.requests],
    ) == (JobRun, True, None, ["kubectl get", "kubectl create"])


def test_the_dry_run_lists_exactly_the_requests_a_run_then_makes(cluster_jobs: FakeJobs) -> None:
    """A run whose pod starts at once and reports its exit code at once makes each listed
    request once, in order, with the Job's name where the placeholder stood."""
    from devops_cli.commands.k8s.cluster_jobs import dry_run_job

    cluster_jobs.phases = ["Running"]
    planned = dry_run_job(["--version"], "test-ctx", wait=True, start_timeout=5.0).requests
    result = _run("--", "--version")
    name = cluster_jobs.created[0]["metadata"]["name"]
    expected = [
        [a.replace("<devops-cli-yyyymmdd-hhmmss-xxxx>", name) for a in r.argv] for r in planned
    ]
    assert (result.exit_code, cluster_jobs.calls) == (
        0,
        [[a for a in argv if a not in ("--context", "test-ctx")] for argv in expected],
    )


def test_a_missing_cronjob_exits_1_with_the_deploy_stack_hint(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.cronjob = None
    result = _run("--", "--version")
    assert (
        result.exit_code,
        "devops k8s deploy-stack --stack devops" in result.output,
        cluster_jobs.created,
    ) == (
        1,
        True,
        [],
    )


def test_a_pod_that_never_starts_exits_1_naming_describe(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.phases = ["Pending"]
    result = _run("--start-timeout", "0", "--", "--version")
    name = cluster_jobs.created[0]["metadata"]["name"]
    output = " ".join(result.output.split())
    assert (result.exit_code, f"kubectl -n devops describe job/{name}" in output) == (1, True)


def test_a_runner_job_changes_only_the_args_of_the_runner_container_and_adds_env_and_labels() -> (
    None
):
    cronjob = runner_cronjob_manifest()
    name = job_name(datetime(2026, 10, 4, 2, 14, 5, tzinfo=UTC), RUNNER_TEMPLATE)
    job = build_job(
        cronjob,
        ["roadmap", "implement", "--item", "7", "--confirm"],
        name,
        template=RUNNER_TEMPLATE,
        env={"DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY": "example/project"},
        labels={"implement-repo": "0123456789abcdef"},
    )
    pod = job["spec"]["template"]
    (container,) = pod["spec"]["containers"]
    template = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
    assert (
        name.startswith("devops-cli-runner-20261004-021405-"),
        container["args"],
        container["env"],
        {key: value for key, value in container.items() if key not in {"args", "env"}},
        job["metadata"]["labels"],
        pod["metadata"]["labels"]["implement-repo"],
    ) == (
        True,
        ["roadmap", "implement", "--item", "7", "--confirm"],
        [
            *template["env"],
            {"name": "DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY", "value": "example/project"},
        ],
        {key: value for key, value in template.items() if key not in {"args", "env"}},
        {"app.kubernetes.io/name": "devops-cli-job", "implement-repo": "0123456789abcdef"},
        "0123456789abcdef",
    )


def test_an_env_name_that_the_template_sets_is_replaced_not_repeated() -> None:
    job = build_job(
        runner_cronjob_manifest(),
        ["--version"],
        "devops-cli-runner-x",
        template=RUNNER_TEMPLATE,
        env={"DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER": "false"},
    )
    (container,) = job["spec"]["template"]["spec"]["containers"]
    assert container["env"] == [
        {"name": "DEVOPS_CLI_ROADMAP_IMPLEMENT_IN_RUNNER", "value": "false"}
    ]


def test_the_runner_template_reads_its_own_cronjob_and_follows_its_container(
    cluster_jobs: FakeJobs,
) -> None:
    result = _run(
        "--template", "runner", "--repo", REPO, "--", "roadmap", "implement", "--item", "7"
    )
    name = cluster_jobs.created[0]["metadata"]["name"]
    (container,) = cluster_jobs.created[0]["spec"]["template"]["spec"]["containers"]
    exit_code_read = next(
        c for c in cluster_jobs.calls if "jsonpath" in c[-1] and "exitCode" in c[-1]
    )
    assert (
        result.exit_code,
        ["kubectl", "-n", "devops", "get", "cronjob", "devops-cli-runner"]
        == cluster_jobs.calls[0][:6],
        name.startswith("devops-cli-runner-"),
        container["name"],
        container["args"],
        '@.name=="runner"' in exit_code_read[-1],
    ) == (0, True, True, "runner", ["roadmap", "implement", "--item", "7"], True)


def test_a_missing_runner_cronjob_names_it(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.runner_cronjob = None
    result = _run("--template", "runner", "--repo", REPO, "--", "--version")
    assert (result.exit_code, "CronJob devops/devops-cli-runner not found" in result.output) == (
        1,
        True,
    )


def test_the_dry_run_of_the_runner_template_names_its_cronjob() -> None:
    result = _run("--template", "runner", "--repo", REPO, "--dry-run", "--", "roadmap", "implement")
    assert (
        result.exit_code,
        "get cronjob devops-cli-runner" in result.output,
        "<devops-cli-runner-yyyymmdd-hhmmss-xxxx>" in result.output,
        "get cronjob devops-cli --" in result.output,
    ) == (0, True, True, False), result.output


def test_an_unknown_template_is_refused() -> None:
    result = _run("--template", "other", "--", "--version")
    assert (result.exit_code, "runner" in result.output) == (2, True)


def test_the_runner_template_scopes_the_token_of_the_job_to_the_repository(
    cluster_jobs: FakeJobs,
) -> None:
    """A runner Job refuses to run unless its token names the one repository (#2667), so
    `--repo` sets the variable that the Service sets on the Jobs it creates."""
    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    (container,) = cluster_jobs.created[0]["spec"]["template"]["spec"]["containers"]
    assert (result.exit_code, {e["name"]: e["value"] for e in container["env"]}[REPO_ENV]) == (
        0,
        REPO,
    )


def test_the_runner_template_without_a_repository_is_refused_before_any_request(
    cluster_jobs: FakeJobs,
) -> None:
    result = _run("--template", "runner", "--", "roadmap", "implement")

    assert (
        result.exit_code,
        "--repo" in result.output,
        cluster_jobs.calls,
        cluster_jobs.created,
    ) == (
        1,
        True,
        [],
        [],
    )


def test_the_dry_run_of_the_runner_template_without_a_repository_is_refused() -> None:
    result = _run("--template", "runner", "--dry-run", "--", "roadmap", "implement")

    assert (result.exit_code, "--repo" in result.output) == (1, True)


def test_the_dry_run_of_the_runner_template_shows_the_token_repository() -> None:
    result = _run("--template", "runner", "--repo", REPO, "--dry-run", "--", "roadmap", "implement")

    assert (result.exit_code, REPO_ENV in result.output, REPO in result.output) == (0, True, True)


def test_a_repository_with_the_default_template_is_refused(cluster_jobs: FakeJobs) -> None:
    result = _run("--repo", REPO, "--", "--version")

    assert (result.exit_code, "--template runner" in result.output, cluster_jobs.created) == (
        1,
        True,
        [],
    )


def test_a_repository_that_is_not_owner_slash_name_is_refused(cluster_jobs: FakeJobs) -> None:
    result = _run("--template", "runner", "--repo", "no-slash", "--", "--version")

    assert (result.exit_code, cluster_jobs.created) == (2, [])


# ── The label and the lock of a runner Job (#2913) ────────────────────────────────────────


def _listed_job(name: str, *conditions: str) -> dict[str, Any]:
    """A Job as `kubectl get jobs -o json` lists it, with the conditions that are True."""
    status = {"conditions": [{"type": kind, "status": "True"} for kind in conditions]}
    return {"metadata": {"name": name}, "status": status}


def test_the_repository_label_is_a_digest_that_fits_a_label_value() -> None:
    label = repository_label(REPO)

    assert (len(label), label == repository_label(REPO), label == repository_label("a/b")) == (
        16,
        True,
        False,
    )
    assert int(label, 16) >= 0


def test_a_runner_job_and_its_pod_carry_the_label_of_the_repository(cluster_jobs: FakeJobs) -> None:
    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    (job,) = cluster_jobs.created
    pod = job["spec"]["template"]["metadata"]["labels"]
    assert (
        result.exit_code,
        job["metadata"]["labels"][LOCK_LABEL],
        pod[LOCK_LABEL],
    ) == (0, repository_label(REPO), repository_label(REPO))


def test_a_job_of_the_default_template_carries_no_repository_label(cluster_jobs: FakeJobs) -> None:
    result = _run("--", "--version")

    (job,) = cluster_jobs.created
    assert (result.exit_code, LOCK_LABEL in job["metadata"]["labels"]) == (0, False)
    assert [call for call in cluster_jobs.calls if call[3:5] == ["get", "jobs"]] == []


def test_a_runner_job_looks_for_the_jobs_of_the_repository_by_their_label(
    cluster_jobs: FakeJobs,
) -> None:
    _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    lookups = [call for call in cluster_jobs.calls if call[3:5] == ["get", "jobs"]]
    assert lookups == [
        [
            "kubectl",
            "-n",
            "devops",
            "get",
            "jobs",
            "-l",
            f"{LOCK_LABEL}={repository_label(REPO)}",
            "-o",
            "json",
        ]
    ]


def test_a_running_job_of_the_repository_blocks_a_runner_job(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.listed = [_listed_job("devops-cli-runner-20261031-010101-abcd")]

    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "devops-cli-runner-20261031-010101-abcd" in output,
        REPO in output,
        cluster_jobs.created,
    ) == (1, True, True, [])


@pytest.mark.parametrize("condition", ["Complete", "Failed"])
def test_a_job_that_ended_does_not_block_a_runner_job(
    cluster_jobs: FakeJobs, condition: str
) -> None:
    cluster_jobs.listed = [_listed_job("devops-cli-runner-20261031-010101-abcd", condition)]

    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    assert (result.exit_code, len(cluster_jobs.created)) == (0, 1)


def test_a_running_job_blocks_a_runner_job_after_one_that_ended(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.listed = [
        _listed_job("devops-cli-runner-old", "Complete"),
        _listed_job("devops-cli-runner-new"),
    ]

    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "devops-cli-runner-new" in output,
        "devops-cli-runner-old" in output,
    ) == (
        1,
        True,
        False,
    )


def test_the_dry_run_of_the_runner_template_lists_the_lookup_and_the_label() -> None:
    result = _run("--template", "runner", "--repo", REPO, "--dry-run", "--", "roadmap", "implement")

    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        f"get jobs -l {LOCK_LABEL}={repository_label(REPO)} -o json" in output,
        f'"{LOCK_LABEL}": "{repository_label(REPO)}"' in result.output,
    ) == (0, True, True), result.output


def test_the_dry_run_of_the_runner_template_lists_exactly_the_requests_a_run_then_makes(
    cluster_jobs: FakeJobs,
) -> None:
    from devops_cli.commands.k8s.cluster_jobs import dry_run_job

    cluster_jobs.phases = ["Running"]
    args = ["roadmap", "implement"]
    planned = dry_run_job(
        args,
        "test-ctx",
        wait=True,
        start_timeout=5.0,
        template=RUNNER_TEMPLATE,
        env={REPO_ENV: REPO},
        repo=REPO,
    ).requests
    result = _run("--template", "runner", "--repo", REPO, "--", *args)
    name = cluster_jobs.created[0]["metadata"]["name"]
    expected = [
        [a.replace("<devops-cli-runner-yyyymmdd-hhmmss-xxxx>", name) for a in r.argv]
        for r in planned
    ]
    assert (result.exit_code, cluster_jobs.calls) == (
        0,
        [[a for a in argv if a not in ("--context", "test-ctx")] for argv in expected],
    )
