"""`devops k8s run-job`: a Job from CronJob devops-cli's template, followed to its exit code."""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import typer
from click.testing import CliRunner

from devops_cli.commands.k8s.cluster_jobs import run_job
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, build_job, job_name
from tests.support.fakes.cluster_jobs import (
    CRONJOB,
    FakeJobs,
    listed_job,
    phase_runner_cronjob_manifest,
    runner_cronjob_manifest,
)
from tests.support.job_templates import cronjob_template, phase_cronjob_template

REPO = "example/roadmap"
PHASES = ("prepare", "agent", "publish")
PHASES_HELD = "the CronJob holds the init containers prepare and agent"
REPO_ENV = "DEVOPS_CLI_SERVICE_GITHUB_APP_TOKEN_REPOSITORY"
LOCK_LABEL = "implement-repo"

_app = typer.Typer()
_app.command()(run_job)
RUN_JOB = typer.main.get_command(_app)


def _label(repo: str) -> str:
    """The value of the label `implement-repo` for `repo`, as the Service computes it."""
    from devops_cli.k8s.cluster_job import repository_label

    return repository_label(repo)


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
        {
            "app.kubernetes.io/name": "devops-cli-job",
            "app.kubernetes.io/component": "roadmap-implement",
            "app.kubernetes.io/part-of": "devops-cli-stack",
            "app.kubernetes.io/managed-by": "devops-cli",
            "implement-repo": "0123456789abcdef",
        },
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
        name.startswith("devops-cli-implement-"),
        container["name"],
        container["args"],
        '@.name=="runner"' in exit_code_read[-1],
    ) == (0, True, True, "runner", ["roadmap", "implement", "--item", "7"], True)


def test_the_runner_template_on_the_phases_follows_each_container_in_turn(
    cluster_jobs: FakeJobs,
) -> None:
    """Each container runs its phase, and run-job follows `prepare`, `agent` and `publish` in
    turn and reads the exit code of each by its name (#3700, #6690)."""
    cluster_jobs.runner_cronjob = phase_runner_cronjob_manifest()
    cluster_jobs.container_exit_codes = {"prepare": "0", "agent": "0", "publish": "0"}
    result = _run(
        "--template", "runner", "--repo", REPO, "--", "roadmap", "implement", "--item", "7"
    )
    name = cluster_jobs.created[0]["metadata"]["name"]
    followed = [c[3:] for c in cluster_jobs.calls if c[3:5] == ["logs", "-f"]]
    assert (result.exit_code, followed) == (
        0,
        [["logs", "-f", f"job/{name}", "-c", phase] for phase in ("prepare", "agent", "publish")],
    )


def test_a_phase_that_fails_ends_the_follow_with_its_exit_code(cluster_jobs: FakeJobs) -> None:
    """`publish` does not start after `agent` failed, so run-job follows no more containers."""
    cluster_jobs.runner_cronjob = phase_runner_cronjob_manifest()
    cluster_jobs.container_exit_codes = {"prepare": "0", "agent": "137"}
    result = _run(
        "--template", "runner", "--repo", REPO, "--", "roadmap", "implement", "--item", "7"
    )
    followed = [c[-1] for c in cluster_jobs.calls if c[3:5] == ["logs", "-f"]]
    assert (result.exit_code, followed) == (137, ["prepare", "agent"])


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
        "<devops-cli-implement-name-xxxxxx>" in result.output,
        "get cronjob devops-cli --" in result.output,
    ) == (0, True, True, False), result.output


def test_the_dry_run_of_the_runner_template_lists_the_reads_of_each_phase_container() -> None:
    """A dry run reads no CronJob, so it lists the reads of a template on the phases with their
    condition (#3700, #6690)."""
    result = _run("--template", "runner", "--repo", REPO, "--dry-run", "--", "roadmap", "implement")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        [f"-c {phase}" in output for phase in ("prepare", "agent", "publish")],
        "the CronJob holds the init containers prepare and agent" in output,
    ) == (0, [True, True, True], True), result.output


@pytest.mark.parametrize(
    ("make", "shown"),
    [
        (cronjob_template, {"runner": []}),
        (
            phase_cronjob_template,
            {phase: ["--phase", phase, "--work", "/run/roadmap"] for phase in PHASES},
        ),
    ],
    ids=["one-container", "phases"],
)
def test_the_dry_run_shows_the_containers_of_the_shape_of_the_template(
    monkeypatch: pytest.MonkeyPatch, make: Any, shown: dict[str, list[str]]
) -> None:
    """The preview reads the shape of the template from the manifests of git, as `build_job` reads
    it from the CronJob: one container `runner` today, and on the phases (#3700) the init
    containers prepare and agent and the container publish, each with its phase (#6743)."""
    from devops_cli.commands.k8s import cluster_jobs

    pod_spec = make(RUNNER_TEMPLATE)["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    monkeypatch.setattr(cluster_jobs, "_template_pod_spec", lambda _template: pod_spec)
    args = ["roadmap", "implement", "--item", "7"]
    planned = cluster_jobs.dry_run_job(
        args, None, wait=False, start_timeout=5.0, template=RUNNER_TEMPLATE
    )
    (create,) = (r for r in planned.requests if r.stdin)
    pod = json.loads(create.stdin)["spec"]["template"]["spec"]

    assert {c["name"]: c["args"] for c in [*pod.get("initContainers", []), *pod["containers"]]} == {
        name: [*args, *extra] for name, extra in shown.items()
    }


def test_the_dry_run_without_a_tree_of_manifests_shows_the_container_of_the_template(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dry run outside a checkout finds no manifest and reads no cluster, so it shows the one
    container that the template names."""
    from devops_cli.commands.k8s import cluster_jobs

    monkeypatch.setattr(cluster_jobs, "resolve_environment", _no_tree)
    planned = cluster_jobs.dry_run_job(
        ["--version"], None, wait=False, start_timeout=5.0, template=RUNNER_TEMPLATE
    )
    (create,) = (r for r in planned.requests if r.stdin)

    assert [
        c["name"] for c in json.loads(create.stdin)["spec"]["template"]["spec"]["containers"]
    ] == ["runner"]


def _no_tree(*_args: Any, **_kwargs: Any) -> Any:
    from devops_cli.exceptions import ConfigurationError

    raise ConfigurationError("no environment tree")


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


def test_the_repository_label_is_a_digest_that_fits_a_label_value() -> None:
    label = _label(REPO)

    assert (len(label), label == _label(REPO), label == _label("a/b")) == (
        16,
        True,
        False,
    )
    assert int(label, 16) >= 0


def test_the_repository_label_is_the_same_for_every_spelling_of_the_name() -> None:
    """GitHub names are not case sensitive, so one repository has one label."""
    assert _label("Example/Roadmap") == _label(REPO)


def test_a_running_job_blocks_a_runner_job_of_another_spelling_of_the_repository(
    cluster_jobs: FakeJobs,
) -> None:
    cluster_jobs.listed = [listed_job("devops-cli-runner-20261031-010101-abcd", REPO)]

    result = _run("--template", "runner", "--repo", "Example/Roadmap", "--", "roadmap", "implement")

    assert (result.exit_code, cluster_jobs.created) == (1, [])


def test_a_running_job_of_another_repository_does_not_block_a_runner_job(
    cluster_jobs: FakeJobs,
) -> None:
    cluster_jobs.listed = [listed_job("devops-cli-runner-20261031-010101-abcd", "example/other")]

    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    assert (result.exit_code, len(cluster_jobs.created)) == (0, 1)


def test_a_runner_job_and_its_pod_carry_the_label_of_the_repository(cluster_jobs: FakeJobs) -> None:
    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    (job,) = cluster_jobs.created
    pod = job["spec"]["template"]["metadata"]["labels"]
    assert (
        result.exit_code,
        job["metadata"]["labels"][LOCK_LABEL],
        pod[LOCK_LABEL],
    ) == (0, _label(REPO), _label(REPO))


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
            f"{LOCK_LABEL}={_label(REPO)}",
            "-o",
            "json",
        ]
    ]


def test_a_running_job_of_the_repository_blocks_a_runner_job(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.listed = [listed_job("devops-cli-runner-20261031-010101-abcd", REPO)]

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
    cluster_jobs.listed = [listed_job("devops-cli-runner-20261031-010101-abcd", REPO, condition)]

    result = _run("--template", "runner", "--repo", REPO, "--", "roadmap", "implement")

    assert (result.exit_code, len(cluster_jobs.created)) == (0, 1)


def test_a_running_job_blocks_a_runner_job_after_one_that_ended(cluster_jobs: FakeJobs) -> None:
    cluster_jobs.listed = [
        listed_job("devops-cli-runner-old", REPO, "Complete"),
        listed_job("devops-cli-runner-new", REPO),
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
        f"get jobs -l {LOCK_LABEL}={_label(REPO)} -o json" in output,
        f'"{LOCK_LABEL}": "{_label(REPO)}"' in result.output,
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
        [a.replace("<devops-cli-implement-name-xxxxxx>", name) for a in r.argv]
        for r in planned
        if not r.condition.startswith(PHASES_HELD)
    ]
    assert (result.exit_code, cluster_jobs.calls) == (
        0,
        [[a for a in argv if a not in ("--context", "test-ctx")] for argv in expected],
    )


def test_the_dry_run_lists_exactly_the_requests_of_a_run_on_the_phases(
    cluster_jobs: FakeJobs,
) -> None:
    """For a CronJob on the phases, a run makes the shared requests and the reads of each
    container, and none of the reads of one container (#3700, #6690)."""
    from devops_cli.commands.k8s.cluster_jobs import dry_run_job

    cluster_jobs.runner_cronjob = phase_runner_cronjob_manifest()
    cluster_jobs.container_exit_codes = {"prepare": "0", "agent": "0", "publish": "0"}
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
        [a.replace("<devops-cli-implement-name-xxxxxx>", name) for a in r.argv]
        for r in planned
        if not r.condition.startswith("the CronJob holds one container")
    ]
    assert (result.exit_code, cluster_jobs.calls) == (
        0,
        [[a for a in argv if a not in ("--context", "test-ctx")] for argv in expected],
    )


def test_the_dry_run_of_the_runner_template_shows_job_name_placeholder_and_repo_labels() -> None:
    result = _run(
        "--template", "runner", "--repo", "dan-petty/devops-cli", "--dry-run", "--", "true"
    )
    assert result.exit_code == 0
    assert "<devops-cli-implement-name-xxxxxx>" in result.output
    assert '"roadmap.devops-cli/owner": "dan-petty"' in result.output
    assert '"roadmap.devops-cli/repo": "devops-cli"' in result.output
    assert '"roadmap.devops-cli/repository": "dan-petty/devops-cli"' in result.output
    assert '"app.kubernetes.io/component": "roadmap-implement"' in result.output


# ── The stage template (#5483) ────────────────────────────────────────────────

STAGE_ARGS = ("roadmap", "stage", "--repo", REPO, "--job-item", "7", "--confirm")


def test_a_stage_job_carries_the_labels_of_its_item_and_names_itself_and_its_deadline(
    cluster_jobs: FakeJobs,
) -> None:
    before = datetime.now(UTC)

    result = _run("--template", "stage", "--repo", REPO, "--item", "7", "--", *STAGE_ARGS)

    (job,) = cluster_jobs.created
    (container,) = job["spec"]["template"]["spec"]["containers"]
    env = {entry["name"]: entry.get("value") for entry in container["env"]}
    deadline = datetime.fromisoformat(env["DEVOPS_CLI_ROADMAP_STAGE_JOB_DEADLINE"])
    labels = job["spec"]["template"]["metadata"]["labels"]
    assert result.exit_code == 0, result.output
    assert (
        job["metadata"]["name"].startswith("devops-cli-stage-roadmap-7-"),
        container["name"],
        container["args"],
        env["DEVOPS_CLI_ROADMAP_STAGE_JOB"],
        env[REPO_ENV],
        deadline >= before + timedelta(seconds=10800),
        labels["roadmap.devops-cli/item"],
        labels["app.kubernetes.io/component"],
    ) == (
        True,
        "stage",
        list(STAGE_ARGS),
        job["metadata"]["name"],
        REPO,
        True,
        "7",
        "roadmap-stage",
    )


def test_a_running_stage_job_of_the_item_blocks_a_second_one(cluster_jobs: FakeJobs) -> None:
    from devops_cli.github.repo_ref import RepoRef
    from devops_cli.k8s.cluster_job import stage_job_labels

    cluster_jobs.listed = [
        {"metadata": {"name": "devops-cli-stage-a", "labels": stage_job_labels(RepoRef(REPO), 7)}}
    ]

    result = _run("--template", "stage", "--repo", REPO, "--item", "7", "--", *STAGE_ARGS)

    assert (result.exit_code, cluster_jobs.created) == (1, [])
    assert "devops-cli-stage-a" in result.output


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(("--template", "stage", "--repo", REPO), id="stage-without-item"),
        pytest.param(("--template", "stage", "--item", "7"), id="stage-without-repo"),
        pytest.param(("--template", "runner", "--repo", REPO, "--item", "7"), id="item-on-runner"),
        pytest.param(("--item", "7"), id="item-on-default"),
    ],
)
def test_the_item_goes_with_the_stage_template_and_its_repository(
    cluster_jobs: FakeJobs, args: tuple[str, ...]
) -> None:
    result = _run(*args, "--", *STAGE_ARGS)

    assert (result.exit_code, cluster_jobs.calls) == (1, [])


def test_the_dry_run_of_the_stage_template_names_its_cronjob_and_its_labels() -> None:
    result = _run("--template", "stage", "--repo", REPO, "--item", "7", "--dry-run", "--", "x")

    assert result.exit_code == 0, result.output
    assert "cronjob roadmap-stage" in result.output
    assert "roadmap.devops-cli/item=7" in result.output
