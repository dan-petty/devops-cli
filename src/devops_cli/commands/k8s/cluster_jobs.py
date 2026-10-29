"""`devops k8s run-job`: run one devops command as a Job in the cluster and follow it.

`kubectl create job --from=cronjob/devops-cli` cannot change a template's args, and a hand-built
pod fails the namespace's `restricted` Pod Security or drifts from git, so this command builds
the Job from a CronJob's template with only the args, name and label changed. `--template`
chooses the CronJob: `default` is CronJob devops-cli, `runner` is CronJob devops-cli-runner, the
template of the implement job's runner (#2667).
`--dry-run` makes no request: it prints the kubectl requests a run would make, in order.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

import typer
from pydantic import ValidationError

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.constants import CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.env import setting_variables
from devops_cli.config.settings import GitHubAppConfig
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import PlannedRequest, is_dry_run, render_request_plan
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.k8s.cluster_job import (
    DEFAULT_TEMPLATE,
    JOB_NAME_LABEL,
    JOB_NAME_LABEL_VALUE,
    JOB_NAMESPACE,
    JOB_POD_SELECTOR_LABEL,
    JobTemplate,
    TemplateName,
    build_job,
    job_name,
)
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info

DEFAULT_JOB_START_TIMEOUT_SECONDS = 120.0
_POLL_SECONDS = 2.0
_EXIT_CODE_ATTEMPTS = 10
# The CronJob's activeDeadlineSeconds, and a margin for the log stream to drain.
_LOG_STREAM_TIMEOUT_SECONDS = 7200.0 + 300.0


_CREATE_ARGS = ["create", "-f", "-", "-o", "name"]
_PHASE_PATH = ".status.phase"


def _name_placeholder(template: JobTemplate) -> str:
    """Where a dry run shows the Job's name, which a run chooses when it creates the Job."""
    return f"<{template.cronjob}-yyyymmdd-hhmmss-xxxx>"


def _cronjob_args(template: JobTemplate) -> list[str]:
    return ["get", "cronjob", template.cronjob, "--ignore-not-found", "-o", "json"]


def _exit_code_path(template: JobTemplate) -> str:
    return f'.status.containerStatuses[?(@.name=="{template.container}")].state.terminated.exitCode'


@dataclass(frozen=True)
class JobRun:
    """What run-job returns: the Job's name and, when followed, its container's exit code.

    A dry run creates nothing: its name is a placeholder, and `requests` lists the requests a
    run would make, in order.
    """

    name: str
    exit_code: int | None = None
    requests: tuple[PlannedRequest, ...] = ()
    dry_run: bool = False


def _kubectl_argv(args: Sequence[str], context: str | None) -> list[str]:
    """The kubectl argv run-job runs in namespace devops, the dry run's list included."""
    return ["kubectl", "-n", JOB_NAMESPACE, *args, *(["--context", context] if context else [])]


def _pod_field_args(name: str, path: str) -> list[str]:
    selector = f"{JOB_POD_SELECTOR_LABEL}={name}"
    return ["get", "pods", "-l", selector, "-o", f"jsonpath={{.items[*]{path}}}"]


def _logs_args(name: str) -> list[str]:
    return ["logs", "-f", f"job/{name}"]


def _kubectl(args: Sequence[str], context: str | None, *, stdin: str | None = None) -> str:
    """Run kubectl in namespace devops and return its stdout, raising when it fails."""
    result = run_subprocess(
        _kubectl_argv(args, context),
        input=stdin,
        quiet=True,
        timeout=DEFAULT_SUBPROCESS_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise ClusterJobError(
            f"`kubectl {' '.join(args[:2])}` failed: {(result.stderr or '').strip()[:256]}"
        )
    return result.stdout or ""


def _read_cronjob(context: str | None, template: JobTemplate) -> dict[str, Any] | None:
    """The template's CronJob, or None when it is not applied."""
    raw = _kubectl(_cronjob_args(template), context)
    return json.loads(raw) if raw.strip() else None


def _pod_field(name: str, context: str | None, path: str) -> str:
    """One field of the Job's pod, empty while there is no pod."""
    return _kubectl(_pod_field_args(name, path), context).strip()


def _wait_until_started(name: str, context: str | None, timeout: float) -> bool:
    """Whether the Job's pod left Pending within the timeout."""
    deadline = time.monotonic() + timeout
    while True:
        phase = _pod_field(name, context, _PHASE_PATH)
        if phase and phase != "Pending":
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(_POLL_SECONDS)


def _stream_logs(name: str, context: str | None) -> None:
    """Stream the Job's log to the terminal until its container exits."""
    run_subprocess(
        _kubectl_argv(_logs_args(name), context),
        capture_output=False,
        quiet=True,
        timeout=_LOG_STREAM_TIMEOUT_SECONDS,
    )


def _exit_code(name: str, context: str | None, template: JobTemplate) -> int | None:
    """The container's `state.terminated.exitCode`, waiting briefly for the status to land."""
    for attempt in range(_EXIT_CODE_ATTEMPTS):
        code = _pod_field(name, context, _exit_code_path(template))
        if code:
            return int(code.split()[0])
        if attempt + 1 < _EXIT_CODE_ATTEMPTS:
            time.sleep(_POLL_SECONDS)
    return None


def _follow(name: str, context: str | None, start_timeout: float, template: JobTemplate) -> int:
    """Wait for the pod, stream its log and return the container's exit code."""
    if not _wait_until_started(name, context, start_timeout):
        print_error(
            MESSAGES.k8s.job_not_started.format(name=name, seconds=start_timeout),
            prefix=False,
            safe=True,
        )
        return 1
    _stream_logs(name, context)
    code = _exit_code(name, context, template)
    if code is None:
        print_error(MESSAGES.k8s.job_no_exit_code.format(name=name), prefix=False, safe=True)
        return 1
    return code


def _env_entries(env: Mapping[str, str] | None) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in (env or {}).items()]


def _job_preview(
    args: Sequence[str], template: JobTemplate, env: Mapping[str, str] | None = None
) -> str:
    """The Job a run creates, with what it copies from the CronJob as placeholders."""
    copied = f"<from CronJob {JOB_NAMESPACE}/{template.cronjob}'s jobTemplate>"
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": _name_placeholder(template),
            "namespace": JOB_NAMESPACE,
            "labels": {"...": copied, JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE},
        },
        "spec": {
            "...": copied,
            "template": {
                "metadata": {"labels": {"...": copied, JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE}},
                "spec": {
                    "...": copied,
                    "containers": [
                        {
                            "name": template.container,
                            "...": copied,
                            "args": list(args),
                            **({"env": _env_entries(env)} if env else {}),
                        }
                    ],
                },
            },
        },
    }
    return json.dumps(job, indent=2)


def dry_run_job(
    args: Sequence[str],
    context: str | None,
    *,
    wait: bool,
    start_timeout: float,
    template: JobTemplate = DEFAULT_TEMPLATE,
    env: Mapping[str, str] | None = None,
) -> JobRun:
    """The requests a run would make, in order, making none: not even the CronJob is read."""
    name = _name_placeholder(template)

    def kubectl(command: Sequence[str], target: str, **extra: Any) -> PlannedRequest:
        method = f"kubectl {command[0]}"
        return PlannedRequest(method, target, tuple(_kubectl_argv(command, context)), **extra)

    requests = [
        kubectl(_cronjob_args(template), f"cronjob {JOB_NAMESPACE}/{template.cronjob}"),
        kubectl(
            _CREATE_ARGS,
            f"job {JOB_NAMESPACE}/{name}",
            stdin=_job_preview(args, template, env),
            condition=f"CronJob {JOB_NAMESPACE}/{template.cronjob} exists",
        ),
    ]
    if wait:
        requests += [
            kubectl(
                _pod_field_args(name, _PHASE_PATH),
                f"pods of job {name}",
                repeat=(
                    f"every {_POLL_SECONDS:g} s while the pod is Pending, "
                    f"for up to {start_timeout:g} s"
                ),
            ),
            kubectl(_logs_args(name), f"job {name}", condition="the pod left Pending"),
            kubectl(
                _pod_field_args(name, _exit_code_path(template)),
                f"pods of job {name}",
                condition="the pod left Pending",
                repeat=(
                    f"every {_POLL_SECONDS:g} s until the exit code is set, "
                    f"up to {_EXIT_CODE_ATTEMPTS} times"
                ),
            ),
        ]
    return JobRun(name, requests=tuple(requests), dry_run=True)


def execute_job(
    args: Sequence[str],
    context: str | None,
    *,
    wait: bool,
    start_timeout: float,
    template: JobTemplate = DEFAULT_TEMPLATE,
    env: Mapping[str, str] | None = None,
) -> JobRun:
    """Create the Job from the CronJob's template and, with `wait`, follow it to its exit code.

    Raises ClusterJobError when the CronJob is missing or kubectl fails.
    """
    cronjob = _read_cronjob(context, template)
    if cronjob is None:
        raise ClusterJobError(MESSAGES.k8s.job_cronjob_missing.format(cronjob=template.cronjob))
    name = job_name(template=template)
    job = build_job(cronjob, list(args), name, template=template, env=env)
    _kubectl(_CREATE_ARGS, context, stdin=json.dumps(job))
    if not wait:
        return JobRun(name)
    return JobRun(name, exit_code=_follow(name, context, start_timeout, template))


def _runner_env(template: TemplateName, repo: str | None) -> dict[str, str] | None:
    """The environment a runner Job gets so that its GitHub token names one repository: the
    variable of `service.github_app.token_repository`, as the Service sets it on its Jobs. The
    Job refuses to run without it (#2667), so a runner Job with no `--repo` is refused here, before
    any request. Raises `typer.Exit` after it prints why."""
    if template is not TemplateName.RUNNER:
        if repo is not None:
            print_error(MESSAGES.k8s.job_repo_needs_runner, prefix=False, safe=True)
            raise typer.Exit(1)
        return None
    if repo is None:
        print_error(MESSAGES.k8s.job_runner_needs_repo, prefix=False, safe=True)
        raise typer.Exit(1)
    try:
        GitHubAppConfig.model_validate({"token_repository": repo})
    except ValidationError as exc:
        raise typer.BadParameter(str(repo), param_hint="--repo") from exc
    return {setting_variables()[CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING]: repo}


def run_job(
    args: Annotated[list[str], typer.Argument(help=HELP.k8s.run_job_args, metavar="ARGS...")],
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    template: Annotated[
        TemplateName, typer.Option("--template", help=HELP.k8s.run_job_template)
    ] = TemplateName.DEFAULT,
    repo: Annotated[str | None, typer.Option("--repo", help=HELP.k8s.run_job_repo)] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help=HELP.k8s.run_job_wait)] = True,
    start_timeout: Annotated[
        float, typer.Option("--start-timeout", min=0, help=HELP.k8s.run_job_start_timeout)
    ] = DEFAULT_JOB_START_TIMEOUT_SECONDS,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.k8s.run_job_dry_run)] = False,
) -> None:
    """Run a devops command as a Job from a CronJob's template and follow it."""
    env = _runner_env(template, repo)
    effective_context = runtime.resolve_effective_context(context)
    if effective_context:
        runtime._validate_kubeconfig_context_name(effective_context, "context")
    if dry_run or is_dry_run():
        planned = dry_run_job(
            args,
            effective_context,
            wait=wait,
            start_timeout=start_timeout,
            template=template.template,
            env=env,
        )
        render_request_plan(
            MESSAGES.k8s.job_dry_run_heading,
            planned.requests,
            (MESSAGES.dry_run.placeholders_note,),
        )
        return
    try:
        run = execute_job(
            args,
            effective_context,
            wait=wait,
            start_timeout=start_timeout,
            template=template.template,
            env=env,
        )
    except ClusterJobError as exc:
        print_error(str(exc), prefix=False, safe=True)
        raise typer.Exit(1) from exc
    if run.exit_code is None:
        print_info(MESSAGES.k8s.job_created.format(name=run.name), prefix=False, safe=True)
        return
    raise typer.Exit(run.exit_code)
