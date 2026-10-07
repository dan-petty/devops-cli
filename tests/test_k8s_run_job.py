"""`devops k8s run-job`: a Job from CronJob devops-cli's template, followed to its exit code."""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
import yaml
from click.testing import CliRunner

from devops_cli.commands.k8s.cluster_jobs import run_job
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job import build_job, job_name
from tests.cluster_secret_fakes import forbid_requests

REPO_ROOT = Path(__file__).resolve().parent.parent
CRONJOB = yaml.safe_load(
    (REPO_ROOT / "k8s" / "devops" / "cronjob.yaml").read_text(encoding="utf-8")
)
_app = typer.Typer()
_app.command()(run_job)
RUN_JOB = typer.main.get_command(_app)


@dataclass
class FakeJobs:
    """kubectl in namespace devops: the CronJob, the created Job's pod phase and exit code."""

    cronjob: dict[str, Any] | None = field(default_factory=lambda: copy.deepcopy(CRONJOB))
    phases: list[str] = field(default_factory=lambda: ["Pending", "Running"])
    exit_code: str = "0"
    calls: list[list[str]] = field(default_factory=list)
    created: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, cmd: list[str], **kwargs: Any) -> Any:
        import subprocess

        argv = [a for a in cmd if a not in ("--context", "test-ctx")]
        self.calls.append(argv)
        return subprocess.CompletedProcess(cmd, 0, self._answer(argv, kwargs.get("input")), "")

    def _answer(self, argv: list[str], stdin: str | None) -> str:
        verb = argv[3:5]
        if verb == ["get", "cronjob"]:
            return json.dumps(self.cronjob) if self.cronjob else ""
        if argv[3:4] == ["create"]:
            self.created.append(json.loads(stdin or "{}"))
            return "job.batch/created\n"
        if verb == ["get", "pods"] and "phase" in argv[-1]:
            return self.phases.pop(0) if len(self.phases) > 1 else self.phases[0]
        if verb == ["get", "pods"]:
            return self.exit_code
        return ""


@pytest.fixture
def jobs(monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeJobs]:
    monkeypatch.setenv("DEVOPS_CLI_TELEMETRY_ENABLED", "false")
    fake = FakeJobs()
    with (
        patch("devops_cli.core.process.subprocess.run", side_effect=fake),
        patch("devops_cli.commands.k8s.cluster_jobs.time.sleep"),
    ):
        yield fake


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
    with pytest.raises(ClusterJobError):
        build_job(broken, ["--version"], "devops-cli-x")


def test_job_names_carry_utc_time_and_four_hex() -> None:
    name = job_name(datetime(2026, 10, 4, 2, 14, 5, tzinfo=UTC))
    assert (name[:27], len(name), int(name[-4:], 16) >= 0) == (
        "devops-cli-20261004-021405-",
        31,
        True,
    )


def test_the_command_exits_with_the_containers_exit_code(jobs: FakeJobs) -> None:
    jobs.exit_code = "3"
    result = _run("--", "no-such-command", "--dry-run")
    created = jobs.created[0]
    assert (
        result.exit_code,
        created["spec"]["template"]["spec"]["containers"][0]["args"],
        ["kubectl", "-n", "devops", "logs", "-f", f"job/{created['metadata']['name']}"]
        in jobs.calls,
    ) == (3, ["no-such-command", "--dry-run"], True)


def test_no_wait_creates_the_job_and_prints_its_name(jobs: FakeJobs) -> None:
    result = _run("--no-wait", "--", "--version")
    name = jobs.created[0]["metadata"]["name"]
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
    assert [c for c in jobs.calls if "logs" in c] == []


def test_dry_run_makes_no_request_and_prints_the_requests_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted = forbid_requests(monkeypatch)
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
        attempted,
        -1 in positions,
        positions == sorted(positions),
        "no request was made" in output,
    ) == (0, None, [], False, True, True), output


def test_dry_run_with_no_wait_lists_only_the_read_and_the_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from devops_cli.commands.k8s.cluster_jobs import JobRun, dry_run_job

    attempted = forbid_requests(monkeypatch)
    result = dry_run_job(["--version"], "test-ctx", wait=False, start_timeout=5.0)
    assert (
        type(result),
        result.dry_run,
        result.exit_code,
        [r.method for r in result.requests],
        attempted,
    ) == (JobRun, True, None, ["kubectl get", "kubectl create"], [])


def test_the_dry_run_lists_exactly_the_requests_a_run_then_makes(jobs: FakeJobs) -> None:
    """A run whose pod starts at once and reports its exit code at once makes each listed
    request once, in order, with the Job's name where the placeholder stood."""
    from devops_cli.commands.k8s.cluster_jobs import dry_run_job

    jobs.phases = ["Running"]
    planned = dry_run_job(["--version"], "test-ctx", wait=True, start_timeout=5.0).requests
    result = _run("--", "--version")
    name = jobs.created[0]["metadata"]["name"]
    expected = [
        [a.replace("<devops-cli-yyyymmdd-hhmmss-xxxx>", name) for a in r.argv] for r in planned
    ]
    assert (result.exit_code, jobs.calls) == (
        0,
        [[a for a in argv if a not in ("--context", "test-ctx")] for argv in expected],
    )


def test_a_missing_cronjob_exits_1_with_the_deploy_stack_hint(jobs: FakeJobs) -> None:
    jobs.cronjob = None
    result = _run("--", "--version")
    assert (
        result.exit_code,
        "devops k8s deploy-stack --stack devops" in result.output,
        jobs.created,
    ) == (
        1,
        True,
        [],
    )


def test_a_pod_that_never_starts_exits_1_naming_describe(jobs: FakeJobs) -> None:
    jobs.phases = ["Pending"]
    result = _run("--start-timeout", "0", "--", "--version")
    name = jobs.created[0]["metadata"]["name"]
    output = " ".join(result.output.split())
    assert (result.exit_code, f"kubectl -n devops describe job/{name}" in output) == (1, True)
