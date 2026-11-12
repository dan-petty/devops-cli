"""Apply a saved plan of an infra repo, one disruptive node at a time (#5125).

`devops infra apply <repo> <playbook> --plan <id>` runs the plan that `devops infra plan` saved,
with these guards for every caller and at every level:

1. **Access level.** An agent needs `safe` for a plan with no disruptive class and no unchecked
   task, else `full` (`apply_level`). A person may apply every plan.
2. **Same plan.** The record `plans/<id>/plan.json` exists, its facts give its id again, it
   ended `ok`, it is not older than `infra.plan_max_age_hours`, and the caller gives its playbook,
   limit and tags.
3. **Commit.** `origin` holds the commit (`origin_holds`). An agent applies only a commit of the
   default branch, or, at `full`, the head of an open pull request of the infra repo. The apply
   exports that commit; it never reads the working tree.
4. **Host keys.** An agent apply is refused when the config or the inventory of the commit turns
   host key checks off.
5. **Health before** (`Cluster.health`).
6. **One disruptive node at a time.** The hosts with no disruptive class run together in one run.
   Each disruptive host runs alone, in plan order: read its node, check the drain with a server
   dry run, drain, a fresh check of the host that must equal its plan, the run, wait for Ready
   and the GPUs of before, the health of the nodes, uncordon only a node that was schedulable
   before, and wait for the critical alerts to clear.
7. **Result matches the plan.** A task that changed in the run and that the plan does not show
   as changed or unchecked stops the apply.
8. **Stop at the first failure.** The apply stops, the node stays cordoned, and the command
   exits 1 with the host, the step and the reason.
9. **Audit and telemetry.** Each apply that passes the argument checks writes one audit record
   (`infra.apply`) with the caller, the level, the repo, the commit, the plan id and each host
   with its result, and adds one to `devops_cli_infra_runs_total`.

The run gets the key of `devops ssh` and no other credential, and runs with no diffs, so the
artifacts of a run that writes a file with a secret do not hold its text. The export is removed
after the apply; the runner artifacts stay in `plans/<id>/applies/<apply id>/` (mode 0700).
"""

from __future__ import annotations

import shutil
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Final

from pydantic import ValidationError

from devops_cli.config.settings import InfraRepoConfig, Settings
from devops_cli.core import clock
from devops_cli.core.caller import agent_tool, in_mcp_call, is_agent_caller
from devops_cli.crypto.ssh_keys import find_newest_key
from devops_cli.exceptions.base import DevOpsCLIError
from devops_cli.exceptions.config import ConfigurationError
from devops_cli.exceptions.infra import InfraApplyRefusedError, InfraReadError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.infra.access import AgentAccess, apply_level, require_agent_level
from devops_cli.infra.ansible_facts import (
    AnsibleInventory,
    AnsibleTool,
    ansible_tool,
    inventory_host_key_checks_off,
    read_config,
    read_inventory,
)
from devops_cli.infra.nodes import Cluster, parse_node
from devops_cli.infra.onboard import OnboardTarget
from devops_cli.infra.plan import (
    PLAN_FILE,
    PROJECT_FOLDER,
    Playbook,
    RunOutcome,
    host_pattern,
    install_collections,
    nondisruptive_units,
    plan_id,
    plan_outcome,
    plans_folder,
    write_runner_settings,
)
from devops_cli.infra.repo_tree import OriginHold, export_tree, origin_holds, pull_number
from devops_cli.infra.status import node_name
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.infra import (
    ApplyReport,
    ApplyResult,
    ApplyStep,
    HostApply,
    HostOutcome,
    HostPlan,
    InfraPlan,
    NodeState,
    PlanContent,
    PlanStatus,
    PlanTask,
)
from devops_cli.project.profile import resolve_profile
from devops_cli.security.sanitizer import mask_secrets

APPLY_ACTION: Final[str] = "devops infra apply"
PULL_HEAD_ACTION: Final[str] = "devops infra apply of the head of a pull request"
AUDIT_COMMAND: Final[str] = "infra.apply"
APPLIES_FOLDER: Final[str] = "applies"
PERSON: Final[str] = "person"
AGENT: Final[str] = "agent"
_MCP: Final[str] = "mcp"
_JOB: Final[str] = "job"
_PLAN_ID_LENGTH: Final[int] = 64
_HEX: Final[frozenset[str]] = frozenset("0123456789abcdef")
_OPEN: Final[str] = "open"
_PRIVATE: Final[int] = 0o700
_KUBE_CONTEXT_KEY: Final[str] = "infra.repos[].kube_context"


@dataclass(frozen=True)
class ApplyRequest:
    """What the caller applies: the id of a saved plan, and the playbook, limit and tags that the
    plan must have."""

    plan_id: str
    playbook: str
    limit: str | None = None
    tags: str | None = None


@dataclass(frozen=True)
class Caller:
    """Who runs the apply: a person, or an agent with its tool (`mcp` for an MCP call, `job` for a
    cluster Job)."""

    kind: str
    tool: str | None = None

    @property
    def is_agent(self) -> bool:
        return self.kind == AGENT

    @classmethod
    def current(cls) -> Caller:
        """The caller of this process."""
        if not is_agent_caller():
            return cls(PERSON)
        return cls(AGENT, agent_tool() or (_MCP if in_mcp_call() else _JOB))


def _refused(message: str) -> InfraApplyRefusedError:
    return InfraApplyRefusedError(message)


def read_plan(repo: RepoRef, request: ApplyRequest) -> InfraPlan:
    """The saved plan of `repo` whose id the caller gave.

    Raises:
        InfraApplyRefusedError: the id is not a plan id, no plan of the repo has it, or its record
            does not read.
    """
    texts = ERRORS.infra
    given = request.plan_id
    if len(given) != _PLAN_ID_LENGTH or not set(given) <= _HEX:
        raise _refused(texts.apply_plan_id_invalid.format(id=given[:80]))
    record = plans_folder(repo) / given / PLAN_FILE
    if not record.is_file():
        raise _refused(texts.apply_plan_not_found.format(id=given, repo=repo.display))
    try:
        return InfraPlan.model_validate_json(record.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise _refused(texts.apply_plan_not_readable.format(id=given, path=record)) from exc


def saved_plan(repo: RepoRef, request: ApplyRequest) -> InfraPlan | None:
    """The saved plan of the request when it reads, else none: the dry run lists the hosts of a
    plan when it can, and refuses nothing."""
    try:
        return read_plan(repo, request)
    except InfraApplyRefusedError:
        return None


def check_plan(
    plan: InfraPlan, request: ApplyRequest, repo: RepoRef, *, max_age_hours: int, now: datetime
) -> None:
    """Refuse a plan whose facts do not give its id, that failed, that is too old, or whose repo,
    playbook, limit or tags are not the ones of the request.

    Raises:
        InfraApplyRefusedError: a check fails.
    """
    texts = ERRORS.infra
    content = PlanContent.model_validate(plan.model_dump(include=set(PlanContent.model_fields)))
    computed = plan_id(content)
    if computed != plan.id or plan.id != request.plan_id:
        raise _refused(texts.apply_plan_hash_differs.format(id=request.plan_id, hash=computed))
    if plan.status is not PlanStatus.OK:
        raise _refused(texts.apply_plan_failed.format(id=plan.id))
    age = now - plan.created
    if age > timedelta(hours=max_age_hours):
        raise _refused(
            texts.apply_plan_too_old.format(
                id=plan.id, created=plan.created.isoformat(timespec="seconds"), hours=max_age_hours
            )
        )
    given = {
        "repo": repo.display,
        "playbook": request.playbook,
        "limit": request.limit,
        "tags": request.tags,
    }
    planned = {"repo": plan.repo, "playbook": plan.playbook, "limit": plan.limit, "tags": plan.tags}
    if RepoRef(plan.repo) == repo:
        planned["repo"] = repo.display
    for name, value in given.items():
        if planned[name] != value:
            raise _refused(
                texts.apply_plan_differs.format(
                    id=plan.id, name=name, planned=planned[name], given=value
                )
            )


def apply_entry(target: OnboardTarget, settings: Settings) -> InfraRepoConfig:
    """The settings entry of the repo, after the check of the lowest level that an apply needs.

    Raises:
        InfraAccessRefusedError: an agent applies on a repo below the level `safe`.
        ConfigurationError: the repo has no kube context.
    """
    repo = target.repo.display
    entry = settings.infra.entry(target.repo) or InfraRepoConfig(repo=repo)
    require_agent_level(entry.agent_access, AgentAccess.SAFE, action=APPLY_ACTION, repo=repo)
    if entry.kube_context is None:
        raise ConfigurationError(
            ERRORS.infra.no_kube_context.format(repo=repo), key=_KUBE_CONTEXT_KEY
        )
    return entry


def check_commit(
    target: OnboardTarget, plan: InfraPlan, caller: Caller, level: AgentAccess
) -> None:
    """Refuse a commit that `origin` does not hold, and for an agent a commit that is not on the
    default branch or, at `full`, the head of an open pull request.

    Raises:
        InfraApplyRefusedError: a check fails.
        InfraAccessRefusedError: an agent applies the head of a pull request below `full`.
        InfraReadError: the fetch of `origin` fails.
    """
    texts = ERRORS.infra
    repo = target.repo.display
    hold = origin_holds(target.path, plan.commit, plan.ref)
    if hold is None:
        raise _refused(texts.apply_commit_not_on_origin.format(commit=plan.commit, ref=plan.ref))
    if not caller.is_agent or hold is OriginHold.DEFAULT_BRANCH:
        return
    number = pull_number(plan.ref)
    if hold is OriginHold.BRANCH or number is None:
        raise _refused(texts.apply_agent_branch.format(commit=plan.commit, ref=plan.ref))
    require_agent_level(level, AgentAccess.FULL, action=PULL_HEAD_ACTION, repo=repo)
    from devops_cli.github.session import get_github_session

    status = get_github_session().client.get_pull_status(repo, number)
    if status.state != _OPEN or status.head_sha != plan.commit:
        raise _refused(
            texts.apply_agent_pull_not_open.format(
                number=number, commit=plan.commit, state=status.state, head=status.head_sha
            )
        )


def fresh_differences(planned: HostPlan, fresh: HostPlan | None) -> list[str]:
    """How the fresh check of a host differs from its plan: the changed tasks, the disruptive
    classes, the unchecked tasks, or a failure."""
    texts = MESSAGES.infra
    if fresh is None:
        return [texts.apply_fresh_no_host]
    differences = [
        texts.apply_fresh_failed.format(task=task.name, reason=task.reason or "")
        for task in fresh.failed
    ]
    for label, plan_part, fresh_part in (
        (texts.apply_fresh_changed, planned.changed, fresh.changed),
        (texts.apply_fresh_disruptive, planned.disruptive, fresh.disruptive),
        (texts.apply_fresh_unchecked, planned.unchecked, fresh.unchecked),
    ):
        if plan_part != fresh_part:
            differences.append(
                texts.apply_fresh_part.format(
                    part=label, plan=_names(plan_part), fresh=_names(fresh_part)
                )
            )
    return differences


def _names(items: Iterable[PlanTask | str]) -> str:
    names = [item if isinstance(item, str) else item.name for item in items]
    return ", ".join(names) or "-"


def unplanned_changes(planned: HostPlan, ran: HostPlan) -> tuple[PlanTask, ...]:
    """The tasks that changed in the run of a host and that its plan does not show as changed or
    unchecked."""
    known = {(task.path, task.name) for task in (*planned.changed, *planned.unchecked)}
    return tuple(
        PlanTask(name=task.name, path=task.path, action=task.action)
        for task in ran.changed
        if (task.path, task.name) not in known
    )


def _run_problem(outcome: RunOutcome, host: str) -> str | None:
    """Why the run did not end well on `host`: a failed task, or the run's own status."""
    ran = _host(outcome, host)
    if ran is None:
        return MESSAGES.infra.apply_host_not_reached.format(host=host)
    if ran.failed:
        failed = ran.failed[0]
        return MESSAGES.infra.apply_task_failed.format(
            task=failed.name, path=failed.path, reason=failed.reason or ""
        )
    status, error = plan_outcome(outcome.hosts, outcome.status, outcome.returncode, outcome.detail)
    if status is PlanStatus.FAILED:
        return error or MESSAGES.infra.apply_run_failed.format(code=outcome.returncode)
    return None


def _host(outcome: RunOutcome, host: str) -> HostPlan | None:
    return next((plan for plan in outcome.hosts if plan.host == host), None)


@dataclass
class _Progress:
    """What the apply knows so far, for the report of a refusal or a stop."""

    plan: InfraPlan | None = None
    folder: Path | None = None
    hosts: list[HostApply] = field(default_factory=list)
    changing: bool = False


@dataclass(frozen=True)
class _Context:
    """What each step of the apply of a plan uses."""

    plan: InfraPlan
    run: Playbook
    cluster: Cluster
    inventory: AnsibleInventory
    offline_group: str | None

    def node(self, host: str) -> str:
        return node_name(host, self.inventory.hostvars.get(host, {}))


def apply_saved_plan(
    target: OnboardTarget,
    settings: Settings,
    request: ApplyRequest,
    *,
    approve: Callable[[InfraPlan], bool],
) -> ApplyReport:
    """Apply the saved plan of `request` to the hosts of the repo, after `approve` says yes, and
    record the audit record and the metric of the apply. A refusal raises after its record; a stop
    gives the report with the result `stopped`.

    Raises:
        InfraAccessRefusedError: an agent applies on a repo below the level that the plan needs.
        InfraApplyRefusedError: a guard refuses the apply, or `approve` says no.
        ConfigurationError: the repo has no kube context.
        InfraReadError: no Ansible tool environment is installed, or a read of the repo fails.
    """
    caller = Caller.current()
    entry = settings.infra.entry(target.repo) or InfraRepoConfig(repo=target.repo.display)
    progress = _Progress()
    apply_id = uuid.uuid4().hex
    started = datetime.now(UTC)
    start = clock.monotonic()

    def report(result: ApplyResult, reason: str | None) -> ApplyReport:
        plan = progress.plan
        return ApplyReport(
            id=apply_id,
            repo=target.repo.display,
            plan_id=request.plan_id,
            commit=plan.commit if plan else None,
            ref=plan.ref if plan else None,
            playbook=request.playbook,
            limit=request.limit,
            tags=request.tags,
            caller=caller.kind,
            tool=caller.tool,
            level=entry.agent_access.value,
            result=result,
            reason=reason,
            hosts=tuple(progress.hosts),
            started=started,
            duration_seconds=round(clock.monotonic() - start, 3),
            folder=str(progress.folder) if progress.folder else None,
        )

    try:
        entry = apply_entry(target, settings)
        plan = read_plan(target.repo, request)
        progress.plan = plan
        check_plan(
            plan,
            request,
            target.repo,
            max_age_hours=settings.infra.plan_max_age_hours,
            now=datetime.now(UTC),
        )
        require_agent_level(
            entry.agent_access,
            apply_level(plan.hosts),
            action=APPLY_ACTION,
            repo=target.repo.display,
        )
        if not approve(plan):
            raise _refused(ERRORS.infra.apply_not_approved.format(id=plan.id))
        result = _apply(target, entry, settings, plan, caller, apply_id, progress)
    except BaseException as exc:
        kind = ApplyResult.STOPPED if progress.changing else ApplyResult.REFUSED
        reason = exc.message if isinstance(exc, DevOpsCLIError) else mask_secrets(repr(exc))
        record_apply(report(kind, reason))
        raise
    done = report(*result)
    record_apply(done)
    return done


def _apply(
    target: OnboardTarget,
    entry: InfraRepoConfig,
    settings: Settings,
    plan: InfraPlan,
    caller: Caller,
    apply_id: str,
    progress: _Progress,
) -> tuple[ApplyResult, str | None]:
    """The steps of the apply after the plan checks: the commit, the export, the host keys, the
    health before, then the hosts. The export is removed after the last step."""
    tool = ansible_tool()
    if not tool.installed:
        raise InfraReadError(ERRORS.infra.tool_missing)
    check_commit(target, plan, caller, entry.agent_access)
    applies = plans_folder(target.repo) / plan.id / APPLIES_FOLDER
    applies.mkdir(parents=True, exist_ok=True, mode=_PRIVATE)
    folder = applies / apply_id
    folder.mkdir(mode=_PRIVATE)
    progress.folder = folder
    project = folder / PROJECT_FOLDER
    try:
        export_tree(target.path, project, plan.commit)
        context = _prepare(target, entry, settings, plan, caller, folder, tool)
        return _apply_hosts(context, progress)
    finally:
        shutil.rmtree(project, ignore_errors=True)


def _prepare(
    target: OnboardTarget,
    entry: InfraRepoConfig,
    settings: Settings,
    plan: InfraPlan,
    caller: Caller,
    folder: Path,
    tool: AnsibleTool,
) -> _Context:
    """Read the export, check the host keys for an agent and the health of the cluster, and give
    what each step uses.

    Raises:
        InfraApplyRefusedError: an agent applies with host key checks off, or the cluster is not
            healthy.
        InfraReadError: the profile names no inventory, or a read fails.
    """
    project = folder / PROJECT_FOLDER
    ansible = resolve_profile(project).profile.ansible
    sources = tuple(ansible.inventory)
    if not sources:
        raise InfraReadError(ERRORS.infra.no_inventory.format(repo=target.repo.display))
    inventory = read_inventory(tool, project, sources)
    if caller.is_agent:
        found = read_config(tool, project).host_key_checks_off
        found += inventory_host_key_checks_off(inventory)
        if found:
            raise _refused(ERRORS.infra.apply_host_key_checks_off.format(found="; ".join(found)))
    offline = inventory.groups.get(ansible.offline_group, ()) if ansible.offline_group else ()
    cluster = Cluster(
        context=str(entry.kube_context),
        settings=settings,
        offline_nodes=frozenset(
            node_name(host, inventory.hostvars.get(host, {})) for host in offline
        ),
    )
    problems = cluster.health()
    if problems:
        raise _refused(ERRORS.infra.apply_unhealthy.format(problems="; ".join(problems)))
    run = Playbook(
        tool=tool,
        folder=folder,
        playbook=plan.playbook,
        sources=sources,
        tags=plan.tags,
        key=find_newest_key(settings.ssh.key_dir, prefix=entry.ssh_key_prefix),
        collections=install_collections(tool, project),
        nondisruptive=nondisruptive_units(inventory),
    )
    write_runner_settings(folder)
    return _Context(plan, run, cluster, inventory, ansible.offline_group)


def _apply_hosts(context: _Context, progress: _Progress) -> tuple[ApplyResult, str | None]:
    """Run the hosts with no disruptive class together, then each disruptive host alone in plan
    order, and stop at the first host that does not apply."""
    plan = context.plan
    together = [host for host in plan.hosts if not host.disruptive]
    alone = [host for host in plan.hosts if host.disruptive]
    progress.changing = True
    if together:
        progress.hosts += _apply_together(context, together)
    for planned in alone:
        if any(host.outcome is HostOutcome.STOPPED for host in progress.hosts):
            progress.hosts.append(_not_run(context, planned))
            continue
        progress.hosts.append(_apply_alone(context, planned))
    stopped = next((h for h in progress.hosts if h.outcome is HostOutcome.STOPPED), None)
    if stopped is None:
        return ApplyResult.OK, None
    return ApplyResult.STOPPED, MESSAGES.infra.apply_stopped_reason.format(
        host=stopped.host, step=stopped.step, reason=stopped.reason
    )


def _not_run(context: _Context, planned: HostPlan) -> HostApply:
    return HostApply(
        host=planned.host,
        node=context.node(planned.host),
        disruptive=planned.disruptive,
        outcome=HostOutcome.NOT_RUN,
    )


def _apply_together(context: _Context, hosts: list[HostPlan]) -> list[HostApply]:
    """One run of the hosts that have no disruptive class; each host applies when the run did
    not fail on it and changed only what its plan shows."""
    names = ",".join(host.host for host in hosts)
    outcome = context.run.run(host_pattern(names, context.offline_group), check_mode=False)
    results = []
    for planned in hosts:
        problem = _run_problem(outcome, planned.host)
        ran = _host(outcome, planned.host)
        unplanned = unplanned_changes(planned, ran) if ran is not None else ()
        if unplanned and problem is None:
            problem = MESSAGES.infra.apply_unplanned.format(names=_names(unplanned))
        results.append(
            HostApply(
                host=planned.host,
                node=context.node(planned.host),
                outcome=HostOutcome.STOPPED if problem else HostOutcome.APPLIED,
                step=ApplyStep.RUN_TOGETHER if problem else None,
                reason=problem,
                runner_idents=(outcome.ident,),
                unplanned=unplanned,
            )
        )
    return results


@dataclass
class _HostRun:
    """The apply of one disruptive host as it goes."""

    planned: HostPlan
    node: str
    idents: list[str] = field(default_factory=list)
    before: NodeState | None = None
    unplanned: tuple[PlanTask, ...] = ()
    down: tuple[str, ...] = ()

    def result(
        self,
        outcome: HostOutcome,
        *,
        after: NodeState | None = None,
        step: ApplyStep | None = None,
        reason: str | None = None,
    ) -> HostApply:
        return HostApply(
            host=self.planned.host,
            node=self.node,
            disruptive=self.planned.disruptive,
            outcome=outcome,
            step=step,
            reason=reason,
            runner_idents=tuple(self.idents),
            unplanned=self.unplanned,
            down_during_apply=self.down,
            before=self.before,
            after=after,
        )


_Stop = tuple[ApplyStep, str]


def _apply_alone(context: _Context, planned: HostPlan) -> HostApply:
    """Apply one disruptive host: read its node, drain it, change it, and let it settle. The
    first step that stops gives the result, with the node as the step left it."""
    cluster = context.cluster
    work = _HostRun(planned=planned, node=context.node(planned.host))
    read = cluster.node(work.node)
    if read.problem is not None or not read.document:
        reason = read.problem or MESSAGES.infra.apply_no_node.format(node=work.node)
        return work.result(HostOutcome.STOPPED, step=ApplyStep.DRAIN_CHECK, reason=reason)
    work.before = parse_node(read.document)
    for step in (_drain, _change, _settle):
        stopped = step(context, work)
        if stopped is not None:
            return work.result(
                HostOutcome.STOPPED, after=_after(context, work), step=stopped[0], reason=stopped[1]
            )
    return work.result(HostOutcome.APPLIED, after=_after(context, work))


def _after(context: _Context, work: _HostRun) -> NodeState | None:
    read = context.cluster.node(work.node)
    return parse_node(read.document) if read.document else None


def _drain(context: _Context, work: _HostRun) -> _Stop | None:
    """Name the workloads that are down while the node is cordoned, check the drain with a server
    dry run, then drain the node within the longest grace period of its pods."""
    cluster = context.cluster
    pods = cluster.pods(work.node)
    work.down = cluster.down_during_apply(work.node, pods)
    if (problem := cluster.drain_check(work.node)) is not None:
        return ApplyStep.DRAIN_CHECK, problem
    if (problem := cluster.drain(work.node, cluster.drain_bound(pods))) is not None:
        return ApplyStep.DRAIN, problem
    return None


def _change(context: _Context, work: _HostRun) -> _Stop | None:
    """Check the host again, which must give its plan, then run the playbook on it and compare
    what changed with the plan."""
    planned = work.planned
    pattern = host_pattern(planned.host, context.offline_group)
    fresh = context.run.run(pattern)
    work.idents.append(fresh.ident)
    differences = fresh_differences(planned, _host(fresh, planned.host))
    if differences:
        return ApplyStep.FRESH_CHECK, "; ".join(differences)
    ran = context.run.run(pattern, check_mode=False)
    work.idents.append(ran.ident)
    if (problem := _run_problem(ran, planned.host)) is not None:
        return ApplyStep.RUN, problem
    work.unplanned = unplanned_changes(planned, _host(ran, planned.host) or planned)
    if work.unplanned:
        return ApplyStep.RUN, MESSAGES.infra.apply_unplanned.format(names=_names(work.unplanned))
    return None


def _settle(context: _Context, work: _HostRun) -> _Stop | None:
    """Wait for Ready and the GPUs of before, and for the health of every node, then uncordon a
    node that was schedulable before, and wait for the critical alerts to clear. The nodes come
    before the uncordon, so a node that is not healthy after the host leaves it cordoned. The
    alerts come after it, because Prometheus can mount a volume that only this node mounts."""
    cluster = context.cluster
    before = work.before
    gpus = before.gpu_allocatable if before else None
    if problems := cluster.wait_ready(work.node, gpus):
        return ApplyStep.READY, "; ".join(problems)
    if problems := cluster.wait_nodes_healthy():
        return ApplyStep.HEALTH, "; ".join(problems)
    if before is not None and not before.cordoned and (problems := cluster.uncordon(work.node)):
        return ApplyStep.UNCORDON, "; ".join(problems)
    if problems := cluster.wait_alerts_clear():
        return ApplyStep.ALERTS, "; ".join(problems)
    return None


def audit_details(report: ApplyReport) -> dict[str, Any]:
    """The details of the audit record of an apply: who, at which level, what, and each host with
    its result. No path of a key and no output of a task."""
    return {
        "id": report.id,
        "caller": report.caller,
        "tool": report.tool,
        "level": report.level,
        "repo": report.repo,
        "commit": report.commit,
        "ref": report.ref,
        "plan_id": report.plan_id,
        "playbook": report.playbook,
        "limit": report.limit,
        "tags": report.tags,
        "result": report.result.value,
        "reason": report.reason,
        "hosts": [
            {
                "host": host.host,
                "node": host.node,
                "disruptive": list(host.disruptive),
                "outcome": host.outcome.value,
                "step": host.step.value if host.step else None,
                "reason": host.reason,
                "runner_idents": list(host.runner_idents),
                "down_during_apply": list(host.down_during_apply),
            }
            for host in report.hosts
        ],
        "duration_seconds": report.duration_seconds,
    }


def record_apply(report: ApplyReport) -> None:
    """Write the audit record of an apply and add it to `devops_cli_infra_runs_total`."""
    from devops_cli.core.audit import record_audit_event
    from devops_cli.telemetry.instruments import INFRA_RUNS_TOTAL, bounded_label, emit

    record_audit_event(
        AUDIT_COMMAND,
        status=report.result.value,
        duration_ms=report.duration_seconds * 1000,
        details=audit_details(report),
    )
    emit(
        INFRA_RUNS_TOTAL,
        1.0,
        {"repo": bounded_label(report.repo), "command": "apply", "result": report.result.value},
    )


_GIB: Final[int] = 1024**3
_ARROW: Final[str] = " -> "


def _memory(state: NodeState | None) -> str:
    if state is None or state.memory_capacity_bytes is None:
        return ""
    allocatable = state.memory_allocatable_bytes
    shown = f"{allocatable / _GIB:.1f}" if allocatable is not None else "?"
    return f"{state.memory_capacity_bytes / _GIB:.1f} / {shown}"


def _cordoned(host: HostApply) -> str:
    texts = MESSAGES.infra
    marks = [
        "" if state is None else (texts.status_yes if state.cordoned else texts.status_no)
        for state in (host.before, host.after)
    ]
    return _ARROW.join(marks) if any(marks) else ""


def render_apply_header(report: ApplyReport) -> list[str]:
    """The title of the text report and the line of the caller and the level."""
    texts = MESSAGES.infra
    tool = f" ({report.tool})" if report.tool else ""
    return [
        texts.apply_title.format(
            repo=report.repo, playbook=report.playbook, commit=report.commit, plan=report.plan_id
        ),
        texts.apply_caller.format(caller=report.caller, tool=tool, level=report.level),
    ]


def apply_table(report: ApplyReport) -> tuple[list[str], list[list[str]]]:
    """The columns and the cells of the text report, one line for each host."""
    cells = [
        [
            host.host,
            host.node,
            ", ".join(host.disruptive),
            host.outcome.value,
            host.step.value if host.step else "",
            _cordoned(host),
            _memory(host.before),
            _memory(host.after),
        ]
        for host in report.hosts
    ]
    return list(MESSAGES.infra.apply_columns), cells


def render_apply_footer(report: ApplyReport) -> list[str]:
    """The lines under the table: the result, the folder, and the next step of a stop."""
    texts = MESSAGES.infra
    lines = [
        texts.apply_done.format(
            id=report.id, result=report.result.value, seconds=report.duration_seconds
        )
    ]
    lines += [
        texts.apply_down.format(host=host.host, workloads=", ".join(host.down_during_apply))
        for host in report.hosts
        if host.down_during_apply
    ]
    if report.folder:
        lines.append(texts.apply_folder.format(folder=report.folder))
    if report.result is not ApplyResult.OK:
        lines.append(texts.apply_stopped.format(reason=report.reason))
    return lines


__all__ = [
    "AGENT",
    "APPLIES_FOLDER",
    "APPLY_ACTION",
    "AUDIT_COMMAND",
    "PERSON",
    "ApplyRequest",
    "Caller",
    "apply_entry",
    "apply_saved_plan",
    "apply_table",
    "audit_details",
    "check_commit",
    "check_plan",
    "fresh_differences",
    "read_plan",
    "record_apply",
    "render_apply_footer",
    "render_apply_header",
    "saved_plan",
    "unplanned_changes",
]
