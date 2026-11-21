"""`devops k8s run-job`: run one devops command as a Job in the cluster and follow it.

`kubectl create job --from=cronjob/devops-cli` cannot change a template's args, and a hand-built
pod fails the namespace's `restricted` Pod Security or drifts from git, so this command builds
the Job from a CronJob's template with only the args, name and label changed. `--template`
chooses the CronJob: `default` is CronJob devops-cli, `runner` is CronJob devops-cli-runner, the
template of the implement job's runner (#2667), and `stage` is CronJob roadmap-stage, the template
of the stage Job of one item (#5483). A runner Job carries the label of its repository, and none
is created while another of that repository has not ended (#2913). A stage Job carries the labels
of its repository and its item (ADR 0022), names itself and the end of its deadline in its
environment, and none is created while another of the item has not ended. `start_job` is the body
of the command; `devops roadmap implement --item` calls it too.
`--dry-run` makes no request: it prints the kubectl requests a run would make, in order.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import typer
from pydantic import ValidationError

import devops_cli.commands.k8s.cluster_runtime as runtime
from devops_cli.config.constants import (
    CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING,
    CONST_ROADMAP_IMPLEMENT_JOB_LABEL,
    CONST_RUNNER_PHASE_AGENT,
    CONST_RUNNER_PHASE_PREPARE,
    CONST_RUNNER_PHASE_PUBLISH,
)
from devops_cli.config.defaults import DEFAULT_SUBPROCESS_TIMEOUT_SECONDS
from devops_cli.config.env import setting_variables
from devops_cli.config.settings import GitHubAppConfig
from devops_cli.core import clock
from devops_cli.core.process import run_subprocess
from devops_cli.dry_run import PlannedRequest, dry_run_class, is_dry_run, render_request_plan
from devops_cli.exceptions.k8s import ClusterJobError
from devops_cli.github.repo_ref import RepoRef, ServiceRow
from devops_cli.k8s.cluster_job import (
    COMPONENT_LABEL,
    DEFAULT_TEMPLATE,
    ITEM_LABEL,
    JOB_NAME_LABEL,
    JOB_NAME_LABEL_VALUE,
    JOB_NAMESPACE,
    JOB_POD_SELECTOR_LABEL,
    MANAGED_BY_LABEL,
    MANAGED_BY_LABEL_VALUE,
    OWNER_LABEL,
    PART_OF_LABEL,
    PART_OF_LABEL_VALUE,
    REPO_LABEL,
    REPOSITORY_ANNOTATION,
    RUNNER_TEMPLATE,
    STAGE_TEMPLATE,
    JobTemplate,
    TemplateName,
    build_job,
    job_name,
    phase_containers,
    repository_label,
    runner_job_name,
    stage_job_env,
    stage_job_labels,
)
from devops_cli.k8s.cluster_job_api import JobState, job_state
from devops_cli.lang import HELP, MESSAGES
from devops_cli.output import print_error, print_info

DEFAULT_JOB_START_TIMEOUT_SECONDS = 120.0
_POLL_SECONDS = 2.0
_EXIT_CODE_ATTEMPTS = 10
# The CronJob's activeDeadlineSeconds, and a margin for the log stream to drain.
_LOG_STREAM_TIMEOUT_SECONDS = 7200.0 + 300.0


_CREATE_ARGS = ["create", "-f", "-", "-o", "name"]
_PHASE_PATH = ".status.phase"
# The status lists of a pod: its init containers run first, one after the other (#3700).
_INIT_STATUSES = "initContainerStatuses"
_APP_STATUSES = "containerStatuses"
# The containers of a runner Job on the phases and the status list of each, as a run follows them.
_PHASE_STATUSES = (
    (CONST_RUNNER_PHASE_PREPARE, _INIT_STATUSES),
    (CONST_RUNNER_PHASE_AGENT, _INIT_STATUSES),
    (CONST_RUNNER_PHASE_PUBLISH, _APP_STATUSES),
)


def _name_placeholder(template: JobTemplate, item: int | None = None) -> str:
    """Where a dry run shows the Job's name, which a run chooses when it creates the Job."""
    if template == STAGE_TEMPLATE:
        return "<devops-cli-stage-name-item-xxxxxx>"
    if template == RUNNER_TEMPLATE:
        return (
            "<devops-cli-implement-name-item-xxxxxx>"
            if item is not None
            else "<devops-cli-implement-name-xxxxxx>"
        )
    return f"<{template.cronjob}-yyyymmdd-hhmmss-xxxx>"


def _cronjob_args(template: JobTemplate) -> list[str]:
    return ["get", "cronjob", template.cronjob, "--ignore-not-found", "-o", "json"]


def _exit_code_path(container: str, statuses: str = _APP_STATUSES) -> str:
    return f'.status.{statuses}[?(@.name=="{container}")].state.terminated.exitCode'


def _started_path(container: str, statuses: str) -> str:
    return f'.status.{statuses}[?(@.name=="{container}")].state.running.startedAt'


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


def _repo_labels(
    repo: str | None, template: JobTemplate = DEFAULT_TEMPLATE, item: int | None = None
) -> dict[str, str]:
    """The labels of the runner Job of `repo`, or of the stage Job of `item`: the ones the
    Service lists its Jobs by."""
    if repo is None:
        return {}
    if template == STAGE_TEMPLATE and item is not None:
        return stage_job_labels(RepoRef(repo), item)
    return {CONST_ROADMAP_IMPLEMENT_JOB_LABEL: repository_label(repo)}


def _new_name(template: JobTemplate, repo: str | None, item: int | None) -> str:
    """The name of a new Job: `RepoRef.adhoc_name` for a stage or runner Job that a person starts,
    so the name starts with the prefix of the row (ADR 0022), else `job_name`."""
    if template == STAGE_TEMPLATE and repo is not None and item is not None:
        return RepoRef(repo).adhoc_name(ServiceRow.STAGE.value, item)
    if template == RUNNER_TEMPLATE and repo is not None:
        return runner_job_name(RepoRef(repo), item)
    return job_name(template=template)


def _stage_env(
    template: JobTemplate, repo: str | None, name: str, cronjob: Mapping[str, Any]
) -> dict[str, str]:
    """The environment of a stage Job: the repository of its token, its name and the end of the
    deadline of its template from now. The deadline counts from the start of the Job, which comes
    after now, so the Job ends its work before its deadline. Empty for any other Job."""
    if template != STAGE_TEMPLATE or repo is None:
        return {}
    seconds = cronjob["spec"]["jobTemplate"]["spec"]["activeDeadlineSeconds"]
    return stage_job_env(RepoRef(repo), name, datetime.now(UTC) + timedelta(seconds=seconds))


def _running_args(labels: Mapping[str, str]) -> list[str]:
    selector = ",".join(f"{key}={value}" for key, value in labels.items())
    return ["get", "jobs", "-l", selector, "-o", "json"]


def _pod_field_args(name: str, path: str) -> list[str]:
    selector = f"{JOB_POD_SELECTOR_LABEL}={name}"
    return ["get", "pods", "-l", selector, "-o", f"jsonpath={{.items[*]{path}}}"]


def _logs_args(name: str, container: str | None = None) -> list[str]:
    return ["logs", "-f", f"job/{name}", *(["-c", container] if container else [])]


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


def _running_jobs(context: str | None, labels: Mapping[str, str]) -> list[str]:
    """The names of the Jobs that carry `labels` and have not ended."""
    raw = _kubectl(_running_args(labels), context)
    listed = json.loads(raw).get("items", []) if raw.strip() else []
    return [job["metadata"]["name"] for job in listed if job_state(job) is JobState.RUNNING]


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
        clock.sleep(_POLL_SECONDS)


def _stream_logs(name: str, context: str | None, container: str | None = None) -> None:
    """Stream the log of the Job's container, or of `container`, to the terminal until it
    exits."""
    run_subprocess(
        _kubectl_argv(_logs_args(name, container), context),
        capture_output=False,
        quiet=True,
        timeout=_LOG_STREAM_TIMEOUT_SECONDS,
    )


def _exit_code(name: str, context: str | None, path: str) -> int | None:
    """The `state.terminated.exitCode` at `path`, waiting briefly for the status to land."""
    for attempt in range(_EXIT_CODE_ATTEMPTS):
        code = _pod_field(name, context, path)
        if code:
            return int(code.split()[0])
        if attempt + 1 < _EXIT_CODE_ATTEMPTS:
            clock.sleep(_POLL_SECONDS)
    return None


def _followed(cronjob: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    """The containers of a Job on the phases (#3700) that run-job follows in turn, each with the
    status list that holds it. Empty for a template with one container."""
    pod_spec = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    inits = {container.get("name") for container in pod_spec.get("initContainers", [])}
    return tuple(
        (phase, _INIT_STATUSES if phase in inits else _APP_STATUSES)
        for phase in phase_containers(pod_spec)
    )


def _container_started(
    name: str, context: str | None, container: str, statuses: str, timeout: float
) -> bool:
    """Whether `container` of the Job's pod runs or ended within the timeout. The pod of a Job on
    the phases stays Pending while its init containers run, so run-job waits for each container."""
    deadline = time.monotonic() + timeout
    while True:
        if _pod_field(name, context, _started_path(container, statuses)) or _pod_field(
            name, context, _exit_code_path(container, statuses)
        ):
            return True
        if time.monotonic() >= deadline:
            return False
        clock.sleep(_POLL_SECONDS)


def _follow_phases(
    name: str, context: str | None, start_timeout: float, followed: tuple[tuple[str, str], ...]
) -> int:
    """Follow each container of a Job on the phases in turn, and return the first exit code that
    is not 0, else 0. A container after one that failed does not start."""
    for container, statuses in followed:
        if not _container_started(name, context, container, statuses, start_timeout):
            print_error(
                MESSAGES.k8s.job_container_not_started.format(
                    name=name, container=container, seconds=start_timeout
                ),
                prefix=False,
                safe=True,
            )
            return 1
        _stream_logs(name, context, container)
        code = _exit_code(name, context, _exit_code_path(container, statuses))
        if code is None:
            print_error(MESSAGES.k8s.job_no_exit_code.format(name=name), prefix=False, safe=True)
            return 1
        if code != 0:
            return code
    return 0


def _follow(
    name: str,
    context: str | None,
    start_timeout: float,
    template: JobTemplate,
    followed: tuple[tuple[str, str], ...] = (),
) -> int:
    """Wait for the pod, stream its log and return the container's exit code. A Job on the phases
    follows each of its containers in turn (`_follow_phases`)."""
    if followed:
        return _follow_phases(name, context, start_timeout, followed)
    if not _wait_until_started(name, context, start_timeout):
        print_error(
            MESSAGES.k8s.job_not_started.format(name=name, seconds=start_timeout),
            prefix=False,
            safe=True,
        )
        return 1
    _stream_logs(name, context)
    code = _exit_code(name, context, _exit_code_path(template.container))
    if code is None:
        print_error(MESSAGES.k8s.job_no_exit_code.format(name=name), prefix=False, safe=True)
        return 1
    return code


def _env_entries(env: Mapping[str, str] | None) -> list[dict[str, str]]:
    return [{"name": name, "value": value} for name, value in (env or {}).items()]


def _job_preview(
    args: Sequence[str],
    template: JobTemplate,
    env: Mapping[str, str] | None = None,
    labels: Mapping[str, str] | None = None,
    repo: str | None = None,
    item: int | None = None,
) -> str:
    """The Job a run creates, with what it copies from the CronJob as placeholders."""
    copied = f"<from CronJob {JOB_NAMESPACE}/{template.cronjob}'s jobTemplate>"
    extra_labels: dict[str, str] = {}
    extra_annotations: dict[str, str] = {}
    if repo is not None:
        repo_ref = RepoRef(repo)
        extra_labels[OWNER_LABEL] = repo_ref.owner_label
        extra_labels[REPO_LABEL] = repo_ref.repo_label
        if item is not None:
            extra_labels[ITEM_LABEL] = str(item)
        if template == RUNNER_TEMPLATE:
            extra_labels[CONST_ROADMAP_IMPLEMENT_JOB_LABEL] = repo_ref.id
        extra_annotations[REPOSITORY_ANNOTATION] = repo_ref.key

    row = (
        ServiceRow.IMPLEMENT.value
        if template == RUNNER_TEMPLATE
        else (ServiceRow.STAGE.value if template == STAGE_TEMPLATE else None)
    )
    if row:
        extra_labels[COMPONENT_LABEL] = f"roadmap-{row}"
        extra_labels[PART_OF_LABEL] = PART_OF_LABEL_VALUE
        extra_labels[MANAGED_BY_LABEL] = MANAGED_BY_LABEL_VALUE

    own = {JOB_NAME_LABEL: JOB_NAME_LABEL_VALUE, **extra_labels, **(labels or {})}
    metadata: dict[str, Any] = {
        "name": _name_placeholder(template, item),
        "namespace": JOB_NAMESPACE,
        "labels": {"...": copied, **own},
    }
    pod_metadata: dict[str, Any] = {"labels": {"...": copied, **own}}
    if extra_annotations:
        metadata["annotations"] = dict(extra_annotations)
        pod_metadata["annotations"] = dict(extra_annotations)
    job = {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": metadata,
        "spec": {
            "...": copied,
            "template": {
                "metadata": pod_metadata,
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
    repo: str | None = None,
    item: int | None = None,
) -> JobRun:
    """The requests a run would make, in order, making none: not even the CronJob is read."""
    name = _name_placeholder(template, item)
    labels = _repo_labels(repo, template, item)

    def kubectl(command: Sequence[str], target: str, **extra: Any) -> PlannedRequest:
        method = f"kubectl {command[0]}"
        return PlannedRequest(method, target, tuple(_kubectl_argv(command, context)), **extra)

    requests = [
        kubectl(_cronjob_args(template), f"cronjob {JOB_NAMESPACE}/{template.cronjob}"),
        *(
            [kubectl(_running_args(labels), f"jobs of {repo} that have not ended")]
            if labels
            else []
        ),
        kubectl(
            _CREATE_ARGS,
            f"job {JOB_NAMESPACE}/{name}",
            stdin=_job_preview(args, template, env, labels, repo=repo, item=item),
            condition=f"CronJob {JOB_NAMESPACE}/{template.cronjob} exists",
        ),
    ]
    # The runner template has one container today, or the containers of the phases (#3700).
    single = "the CronJob holds one container" if template == RUNNER_TEMPLATE else ""
    started = f"{single}, after the pod left Pending" if single else "the pod left Pending"
    if wait:
        requests += [
            kubectl(
                _pod_field_args(name, _PHASE_PATH),
                f"pods of job {name}",
                condition=single,
                repeat=(
                    f"every {_POLL_SECONDS:g} s while the pod is Pending, "
                    f"for up to {start_timeout:g} s"
                ),
            ),
            kubectl(_logs_args(name), f"job {name}", condition=started),
            kubectl(
                _pod_field_args(name, _exit_code_path(template.container)),
                f"pods of job {name}",
                condition=started,
                repeat=(
                    f"every {_POLL_SECONDS:g} s until the exit code is set, "
                    f"up to {_EXIT_CODE_ATTEMPTS} times"
                ),
            ),
        ]
    if wait and template == RUNNER_TEMPLATE:
        # A run reads the CronJob and follows each container of a template on the phases in
        # turn instead (#3700, #6690).
        when = "the CronJob holds the init containers prepare and agent"
        for container, statuses in _PHASE_STATUSES:
            requests += [
                kubectl(
                    _pod_field_args(name, _started_path(container, statuses)),
                    f"pods of job {name}",
                    condition=when,
                    repeat=f"every {_POLL_SECONDS:g} s until {container} starts",
                ),
                kubectl(
                    _logs_args(name, container),
                    f"job {name}",
                    condition=f"{when}, after {container} started",
                ),
                kubectl(
                    _pod_field_args(name, _exit_code_path(container, statuses)),
                    f"pods of job {name}",
                    condition=when,
                    repeat=f"until the exit code is set, up to {_EXIT_CODE_ATTEMPTS} times",
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
    repo: str | None = None,
    item: int | None = None,
) -> JobRun:
    """Create the Job from the CronJob's template and, with `wait`, follow it to its exit code.
    With `repo`, a runner Job's repository, the Job and its pod carry the label that the Service
    lists its Jobs by, and no Job is created while a Job with that label has not ended: a
    repository has one runner Job at a time, whoever starts it. A stage Job of `item` carries the
    labels of its repository and its item, so an item has one stage Job at a time.

    Raises ClusterJobError when the CronJob is missing, a Job of the repository has not ended, or
    kubectl fails.
    """
    cronjob = _read_cronjob(context, template)
    if cronjob is None:
        raise ClusterJobError(MESSAGES.k8s.job_cronjob_missing.format(cronjob=template.cronjob))
    labels = _repo_labels(repo, template, item)
    if labels and (running := _running_jobs(context, labels)):
        raise ClusterJobError(
            MESSAGES.k8s.job_runner_running.format(repo=repo, names=", ".join(running))
        )
    name = _new_name(template, repo, item)
    env = {**(env or {}), **_stage_env(template, repo, name, cronjob)}
    job = build_job(
        cronjob,
        list(args),
        name,
        template=template,
        env=env,
        labels=labels,
        repo=repo,
        item=item,
    )
    _kubectl(_CREATE_ARGS, context, stdin=json.dumps(job))
    if not wait:
        return JobRun(name)
    exit_code = _follow(name, context, start_timeout, template, _followed(cronjob))
    return JobRun(name, exit_code=exit_code)


def check_repo(repo: str) -> None:
    """Raise `typer.BadParameter` unless `repo` is `owner/name`, the form of the token setting."""
    try:
        GitHubAppConfig.model_validate({"token_repository": repo})
    except ValidationError as exc:
        raise typer.BadParameter(repo, param_hint="--repo") from exc


def _refused(message: str) -> typer.Exit:
    print_error(message, prefix=False, safe=True)
    return typer.Exit(1)


def _runner_env(
    template: TemplateName, repo: str | None, item: int | None = None
) -> dict[str, str] | None:
    """The environment a runner Job gets so that its GitHub token names one repository: the
    variable of `service.github_app.token_repository`, as the Service sets it on its Jobs. The
    Job refuses to run without it (#2667), so a runner Job with no `--repo` is refused here, before
    any request. A stage Job needs `--repo` and `--item`, and gets its environment when the Job is
    made (`_stage_env`). Raises `typer.Exit` after it prints why."""
    if item is not None and template is not TemplateName.STAGE:
        raise _refused(MESSAGES.k8s.job_item_needs_stage)
    if template is TemplateName.DEFAULT:
        if repo is not None:
            raise _refused(MESSAGES.k8s.job_repo_needs_runner)
        return None
    if template is TemplateName.STAGE:
        if repo is None or item is None:
            raise _refused(MESSAGES.k8s.job_stage_needs_item)
        check_repo(repo)
        return None
    if repo is None:
        raise _refused(MESSAGES.k8s.job_runner_needs_repo)
    check_repo(repo)
    return {setting_variables()[CONST_GITHUB_APP_TOKEN_REPOSITORY_SETTING]: repo}


def start_job(
    args: Sequence[str],
    *,
    context: str | None,
    template: TemplateName,
    repo: str | None,
    wait: bool,
    start_timeout: float,
    dry_run: bool,
    before: Sequence[PlannedRequest] = (),
    item: int | None = None,
) -> None:
    """Make the Job of `devops k8s run-job` and follow it, or print the requests of a dry run.
    `devops roadmap implement` calls this too, so the two commands make the same Job. `before` are
    the requests the caller makes first, shown in front of the plan of a dry run. Raises
    `typer.Exit`: with the exit code of the container, or 1 when the Job could not run."""
    env = _runner_env(template, repo, item)
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
            repo=repo,
            item=item,
        )
        render_request_plan(
            MESSAGES.k8s.job_dry_run_heading,
            (*before, *planned.requests),
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
            repo=repo,
            item=item,
        )
    except ClusterJobError as exc:
        print_error(str(exc), prefix=False, safe=True)
        raise typer.Exit(1) from exc
    if run.exit_code is None:
        print_info(MESSAGES.k8s.job_created.format(name=run.name), prefix=False, safe=True)
        return
    raise typer.Exit(run.exit_code)


@dry_run_class("request-plan")
def run_job(
    args: Annotated[list[str], typer.Argument(help=HELP.k8s.run_job_args, metavar="ARGS...")],
    context: Annotated[
        str | None, typer.Option("--context", "-c", help=HELP.options.context)
    ] = None,
    template: Annotated[
        TemplateName, typer.Option("--template", help=HELP.k8s.run_job_template)
    ] = TemplateName.DEFAULT,
    repo: Annotated[str | None, typer.Option("--repo", help=HELP.k8s.run_job_repo)] = None,
    item: Annotated[int | None, typer.Option("--item", min=1, help=HELP.k8s.run_job_item)] = None,
    wait: Annotated[bool, typer.Option("--wait/--no-wait", help=HELP.k8s.run_job_wait)] = True,
    start_timeout: Annotated[
        float, typer.Option("--start-timeout", min=0, help=HELP.k8s.run_job_start_timeout)
    ] = DEFAULT_JOB_START_TIMEOUT_SECONDS,
    dry_run: Annotated[bool, typer.Option("--dry-run", help=HELP.k8s.run_job_dry_run)] = False,
) -> None:
    """Run a devops command as a Job from a CronJob's template and follow it."""
    start_job(
        args,
        context=context,
        template=template,
        repo=repo,
        wait=wait,
        start_timeout=start_timeout,
        dry_run=dry_run,
        item=item,
    )
