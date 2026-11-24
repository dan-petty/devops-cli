"""Plan a playbook of an infra repo in check mode, and keep the plan record (#5124).

The plan runs one commit that `origin` holds, never the working tree of the checkout: the reader
exports the commit (`repo_tree.export_commit`) into the project folder of an ansible-runner private
data folder under `<data dir>/infra/<owner>/<name>/plans/` (mode 0700). It reads the profile and
the inventory in the export, installs the pinned collections of `collections/requirements.yml`
once for each version of the file, and runs `ansible-runner run <folder> --playbook <playbook>`
with `--check --diff -v` and the limit `<limit>`, followed by `!<offline group>` as its own comma
term after a comma limit and as a colon term otherwise. The run gets the repo's
`ansible.cfg`, the key of `devops ssh` as `ansible_ssh_private_key_file`, host key checks on, and
the environment of the process runner, so no `ANSIBLE_` variable of the person reaches it. The
`TERM` of the person reaches it, and ansible-runner gives the run a pseudo-terminal, so in a color
terminal the default callback puts color codes around the text of each event. Every run sets
`ANSIBLE_NOCOLOR`, and `ANSIBLE_FORCE_COLOR=False` over a `force_color` of the repo's `ansible.cfg`
(#5352): the event text, and so the plan, is the same in a color terminal and with no terminal.

The job events (`artifacts/<ident>/job_events/*.json`) give the plan of each host, with no read of
the repo's YAML:

- **Changed**: a `runner_on_ok` result with `changed`. Its diff is **hidden** when the result holds
  an empty diff (`diff: false`) or is censored (`no_log`). A censored result does not say whether
  it changed, so the censored results of a host count as changes only when the stats of the run
  count more changes on the host than the other results show: the safe side.
- **Unchecked**: a `runner_on_skipped` task that check mode skipped. At verbosity 1 the default
  callback prints the result of a skip after `=> `, and a skip by a false `when` has the key
  `false_condition`, the first false item of the `when` list. A skip by a false `when` is unchecked
  when that item names `ansible_check_mode`: a task that needs the change of an earlier task, such
  as an install from an apt source that check mode did not add, has such a `when` (#5435). Every
  other skip, and a result that does not read, is unchecked. A loop item counts the same way.
- **Disruptive**: a changed `ansible.builtin.reboot` is `reboot`; a changed
  `kubernetes.core.k8s_drain` with the state `drain` is `drain`; a changed `systemd`,
  `systemd_service` or `service` task with the state `restarted`, `reloaded` or `stopped` is
  `service-restart:<unit>`, unless the host variable `devops_infra_nondisruptive_units` lists the
  unit, and `service-restart-nodrain:<unit>` when the host variable
  `devops_infra_restart_nodrain_units` lists it: the restart of such a unit keeps its containers,
  so the apply cordons the node and skips the drain check and the drain (`skips_drain`, #6338).
  `ANSIBLE_INJECT_INVOCATION` puts the rendered arguments in the result; a result with no
  arguments is disruptive, the safe side.
- **Failed**: a `runner_on_failed` result that the task does not ignore, and a
  `runner_on_unreachable` host.

The plan id is the SHA-256 of the canonical JSON of the facts of the plan (`PlanContent`): not the
time, the runner ident or the folder. The export is removed after the run; the plan record
(`plan.json`) and the runner artifacts stay in `plans/<id>/`.
"""

from __future__ import annotations

import hashlib
import json
import shlex
import shutil
import tempfile
import uuid
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from jinja2 import Environment, TemplateSyntaxError, nodes

from devops_cli.config.defaults import (
    DEFAULT_INFRA_PLAN_TIMEOUT_MARGIN_SECONDS,
    DEFAULT_INFRA_PLAN_TIMEOUT_SECONDS,
)
from devops_cli.config.settings import InfraRepoConfig, Settings
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import resolve_store_path
from devops_cli.crypto.ssh_keys import find_newest_key
from devops_cli.exceptions.infra import InfraReadError
from devops_cli.github.repo_ref import RepoRef
from devops_cli.infra.access import AgentAccess, require_agent_level
from devops_cli.infra.ad_hoc import read_job_events, tool_env
from devops_cli.infra.ansible_facts import (
    RUNNER_COMMAND,
    AnsibleInventory,
    AnsibleTool,
    ansible_tool,
    config_env,
    install_requirements,
    is_template,
    read_inventory,
)
from devops_cli.infra.onboard import OnboardTarget
from devops_cli.infra.repo_content import find_collection_requirements
from devops_cli.infra.repo_tree import export_commit, render_read
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.infra import (
    ChangedTask,
    FailedTask,
    HostPlan,
    InfraPlan,
    PlanContent,
    PlanStatus,
    PlanTask,
    ReadCommit,
)
from devops_cli.project.profile import resolve_profile
from devops_cli.security.sanitizer import mask_secrets

PLAN_ACTION: Final[str] = "devops infra plan"
NONDISRUPTIVE_UNITS_VARIABLE: Final[str] = "devops_infra_nondisruptive_units"
NODRAIN_UNITS_VARIABLE: Final[str] = "devops_infra_restart_nodrain_units"
PLAN_FILE: Final[str] = "plan.json"
PROJECT_FOLDER: Final[str] = "project"
REBOOT: Final[str] = "reboot"
DRAIN: Final[str] = "drain"
SERVICE_RESTART: Final[str] = "service-restart"
SERVICE_RESTART_NODRAIN: Final[str] = "service-restart-nodrain"
# The host pattern when the caller gives no --limit.
_ALL_HOSTS: Final[str] = "all"
_STORE: Final[str] = "infra"
_PLANS: Final[str] = "plans"
_COLLECTIONS: Final[str] = "collections"
_RUN_PREFIX: Final[str] = ".run-"
_INSTALL_PREFIX: Final[str] = ".install-"
_ARTIFACTS: Final[str] = "artifacts"
_JOB_EVENTS: Final[str] = "job_events"
_STATUS_FILE: Final[str] = "status"
_STDOUT_FILE: Final[str] = "stdout"
_SETTINGS_FILE: Final[tuple[str, str]] = ("env", "settings")
_PRIVATE: Final[int] = 0o700
_FOLDER_MARK: Final[str] = "<plan folder>"
# The options of `ansible-playbook` of every plan: check mode, the diffs, and verbosity 1, at which
# the default callback prints the result of a skipped task.
_CHECK_OPTIONS: Final[tuple[str, ...]] = ("--check", "--diff", "-v")
# The options of the run of an apply (#5125): verbosity 1 and no diffs, so the artifacts of a run
# that changes a file with a secret do not hold its text.
_RUN_OPTIONS: Final[tuple[str, ...]] = ("-v",)
# What the run adds to the environment of `tool_env`: the rendered arguments in each result, the
# results as JSON, a line for each skipped host, and no color, also when the repo's `ansible.cfg`
# sets `force_color`. A skip result in color does not read as JSON, and the plan counts it as
# unchecked (#5352).
_PLAN_ENV: Final[dict[str, str]] = {
    "ANSIBLE_INJECT_INVOCATION": "True",
    "ANSIBLE_CALLBACK_RESULT_FORMAT": "json",
    "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "True",
    "ANSIBLE_NOCOLOR": "True",
    "ANSIBLE_FORCE_COLOR": "False",
}

_EVENT_OK: Final[str] = "runner_on_ok"
_EVENT_SKIPPED: Final[str] = "runner_on_skipped"
_EVENT_FAILED: Final[str] = "runner_on_failed"
_EVENT_UNREACHABLE: Final[str] = "runner_on_unreachable"
_EVENT_STATS: Final[str] = "playbook_on_stats"
_SUCCESSFUL: Final[str] = "successful"
_TIMEOUT: Final[str] = "timeout"
_CENSORED: Final[str] = "censored"
_SKIP_MARK: Final[str] = " => "
_FALSE_CONDITION: Final[str] = "false_condition"
_SKIP_REASON: Final[str] = "skip_reason"
_CONDITIONAL_RESULT_FALSE: Final[str] = "Conditional result was False"
_END_HOST_CONDITIONAL: Final[str] = "end_host conditional evaluated to False"
# The variable that is true in check mode. A false `when` item that names it is a check-mode skip.
_CHECK_MODE_NAME: Final[str] = "ansible_check_mode"
# Parses a `when` item to read the names in it. It compiles and renders nothing, so the tests and
# filters of Ansible need not exist here.
_CONDITIONS: Final[Environment] = Environment(autoescape=True)
_BUILTIN: Final[tuple[str, ...]] = ("ansible.builtin", "ansible.legacy")
_REBOOT_ACTIONS: Final[frozenset[str]] = frozenset(f"{ns}.reboot" for ns in _BUILTIN)
_SERVICE_ACTIONS: Final[frozenset[str]] = frozenset(
    f"{ns}.{module}" for ns in _BUILTIN for module in ("systemd", "systemd_service", "service")
)
_DRAIN_ACTIONS: Final[frozenset[str]] = frozenset({"kubernetes.core.k8s_drain"})
_DRAIN_STATE: Final[str] = "drain"
_DISRUPTIVE_STATES: Final[frozenset[str]] = frozenset({"restarted", "reloaded", "stopped"})
_HIDDEN_UNIT: Final[str] = "(hidden)"


def host_pattern(limit: str | None, offline_group: str | None) -> str:
    """The hosts that the run reaches: the limit, else all hosts, and never a host of the group
    of hosts out of service. Ansible splits a pattern that holds a comma on the commas only, so
    the exclusion is its own comma term after a comma limit and a colon term otherwise."""
    pattern = limit or _ALL_HOSTS
    if not offline_group:
        return pattern
    separator = "," if "," in pattern else ":"
    return f"{pattern}{separator}!{offline_group}"


def _listed_units(inventory: AnsibleInventory, variable: str) -> dict[str, frozenset[str]]:
    """The units that each host lists in the host variable `variable`. Only Ansible renders a
    template, so a templated value lists no unit."""
    found: dict[str, frozenset[str]] = {}
    for host, variables in inventory.hostvars.items():
        value = variables.get(variable)
        if isinstance(value, list) and not any(is_template(unit) for unit in value):
            found[host] = frozenset(str(unit) for unit in value)
    return found


def nondisruptive_units(inventory: AnsibleInventory) -> dict[str, frozenset[str]]:
    """The units of each host whose restart does not disrupt it (`devops_infra_nondisruptive_units`).
    Only Ansible renders a template, so a templated value lists no unit: every restart stays
    disruptive."""
    return _listed_units(inventory, NONDISRUPTIVE_UNITS_VARIABLE)


def nodrain_units(inventory: AnsibleInventory) -> dict[str, frozenset[str]]:
    """The units of each host whose restart needs a cordon and no drain
    (`devops_infra_restart_nodrain_units`). Only Ansible renders a template, so a templated value
    lists no unit: every restart stays disruptive."""
    return _listed_units(inventory, NODRAIN_UNITS_VARIABLE)


def skips_drain(disruptive: Collection[str]) -> bool:
    """Whether the disruptive classes of a host are all no-drain restarts, so the apply cordons
    the node and runs neither the drain check nor the drain. A host with no disruptive class runs
    in the together run, and a host that holds any other class drains (#6338)."""
    return bool(disruptive) and all(
        kind.startswith(f"{SERVICE_RESTART_NODRAIN}:") for kind in disruptive
    )


@dataclass
class _Change:
    """A change of a host in run order, with its disruptive class; a censored result is a change
    only when the stats count it."""

    task: ChangedTask
    disruptive: str | None
    censored: bool = False


@dataclass
class _Host:
    """What the events of one host show, before the stats decide on its censored results."""

    changes: list[_Change] = field(default_factory=list)
    unchecked: list[PlanTask] = field(default_factory=list)
    failed: list[FailedTask] = field(default_factory=list)

    def plan(self, host: str, counted: int | None) -> HostPlan:
        shown = sum(1 for change in self.changes if not change.censored)
        with_censored = counted is not None and counted > shown
        kept = [change for change in self.changes if with_censored or not change.censored]
        return HostPlan(
            host=host,
            changed=tuple(change.task for change in kept),
            disruptive=tuple(dict.fromkeys(c.disruptive for c in kept if c.disruptive)),
            unchecked=tuple(self.unchecked),
            failed=tuple(self.failed),
        )


def host_plans(
    events: Iterable[Mapping[str, Any]],
    project: Path,
    nondisruptive: Mapping[str, Collection[str]],
    nodrain: Mapping[str, Collection[str]] | None = None,
) -> tuple[HostPlan, ...]:
    """The plan of each host that the job events name, sorted by host. `project` is the folder
    that the task paths are relative to, `nondisruptive` the units of each host whose restart does
    not disrupt it, and `nodrain` the units of each host whose restart needs a cordon and no
    drain."""
    hosts: dict[str, _Host] = {}
    counted: dict[str, int] = {}
    nodrain = nodrain or {}
    for event in events:
        kind = event.get("event")
        data = event.get("event_data") or {}
        if kind == _EVENT_STATS:
            counted = {str(host): int(count) for host, count in (data.get("changed") or {}).items()}
            continue
        host = data.get("host")
        if not host or kind not in (_EVENT_OK, _EVENT_SKIPPED, _EVENT_FAILED, _EVENT_UNREACHABLE):
            continue
        _add(
            hosts.setdefault(str(host), _Host()),
            str(kind),
            event,
            data,
            project,
            nondisruptive,
            nodrain,
        )
    return tuple(hosts[host].plan(host, counted.get(host)) for host in sorted(hosts))


def _add(
    tasks: _Host,
    kind: str,
    event: Mapping[str, Any],
    data: Mapping[str, Any],
    project: Path,
    nondisruptive: Mapping[str, Collection[str]],
    nodrain: Mapping[str, Collection[str]],
) -> None:
    """Add what one event of a host shows."""
    task = _task(data, project)
    res = data.get("res") or {}
    if kind == _EVENT_SKIPPED:
        if _is_check_mode_skip(str(event.get("stdout") or "")):
            tasks.unchecked.append(task)
    elif kind == _EVENT_FAILED:
        if not data.get("ignore_errors"):
            tasks.failed.append(FailedTask(**task.model_dump(), reason=_reason(res)))
    elif kind == _EVENT_UNREACHABLE:
        tasks.failed.append(FailedTask(**task.model_dump(), reason=_reason(res), unreachable=True))
    elif _CENSORED in res:
        changed = ChangedTask(**task.model_dump(), diff_hidden=True)
        kind_of = _class_of(task.action, {}, str(data.get("host")), nondisruptive, nodrain)
        tasks.changes.append(_Change(changed, kind_of, True))
    else:
        if any(_is_skipped_item(item) for item in res.get("results") or ()):
            tasks.unchecked.append(task)
        if res.get("changed"):
            hidden = "diff" in res and not res["diff"]
            changed = ChangedTask(**task.model_dump(), diff_hidden=hidden)
            kind_of = _class_of(task.action, res, str(data.get("host")), nondisruptive, nodrain)
            tasks.changes.append(_Change(changed, kind_of))


def _class_of(
    action: str,
    res: Mapping[str, Any],
    host: str,
    nondisruptive: Mapping[str, Collection[str]],
    nodrain: Mapping[str, Collection[str]],
) -> str | None:
    """The disruptive class of a change of `host`, from the units that the host lists as
    nondisruptive and as no-drain."""
    return disruptive_class(action, res, nondisruptive.get(host, ()), nodrain.get(host, ()))


def _task(data: Mapping[str, Any], project: Path) -> PlanTask:
    """The task of an event, with its path relative to `project` when it is in it."""
    path = str(data.get("task_path") or "")
    file, colon, line = path.rpartition(":")
    if not colon or not line.isdecimal():
        file, line = path, ""
    location = Path(file)
    if location.is_absolute() and location.is_relative_to(project):
        file = location.relative_to(project).as_posix()
    return PlanTask(
        name=str(data.get("task") or ""),
        path=f"{file}:{line}" if line else file,
        action=str(data.get("resolved_action") or data.get("task_action") or ""),
    )


def _reason(res: Mapping[str, Any]) -> str | None:
    message = res.get("msg")
    return mask_secrets(str(message)) if message else None


def _is_check_mode_skip(stdout: str) -> bool:
    """Whether a skip came from check mode: every skip but one by a false `when` that does not
    name `ansible_check_mode`, as the result that the callback prints after `=> ` shows."""
    _, mark, text = stdout.partition(_SKIP_MARK)
    if not mark:
        return True
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        return True
    if not isinstance(result, dict):
        return True
    items = result.get("results")
    if isinstance(items, list) and items:
        return any(not isinstance(item, dict) or _check_mode_caused(item) for item in items)
    return _check_mode_caused(result)


def _is_skipped_item(item: Any) -> bool:
    """Whether one item of a loop result was skipped by check mode: a skipped item with no false
    `when`, or an item whose false `when` names `ansible_check_mode`."""
    if not isinstance(item, dict):
        return False
    if _FALSE_CONDITION in item or _SKIP_REASON in item:
        return _check_mode_caused(item)
    return bool(item.get("skipped"))


def _check_mode_caused(result: Mapping[str, Any]) -> bool:
    """Whether check mode caused the skip of one result: it has no false `when`, or its false
    `when` item names `ansible_check_mode` (#5435). A `when` item that does not parse is a
    check-mode skip: the safe side."""
    if _FALSE_CONDITION in result:
        condition = result[_FALSE_CONDITION]
        if not isinstance(condition, str):
            return False
        try:
            tree = _CONDITIONS.parse(f"{{{{ {condition} }}}}")
        except TemplateSyntaxError:
            return True
        return any(name.name == _CHECK_MODE_NAME for name in tree.find_all(nodes.Name))
    if _SKIP_REASON in result:
        reason = result[_SKIP_REASON]
        if isinstance(reason, str) and (
            reason == _CONDITIONAL_RESULT_FALSE or reason.startswith(_END_HOST_CONDITIONAL)
        ):
            return _CHECK_MODE_NAME in reason
    return True


def _module_args(res: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The rendered arguments of a result (`ANSIBLE_INJECT_INVOCATION`); none when it has none."""
    invocation = res.get("invocation")
    if not isinstance(invocation, Mapping):
        return None
    args = invocation.get("module_args", invocation)
    return args if isinstance(args, Mapping) else None


def disruptive_class(
    action: str,
    res: Mapping[str, Any],
    units: Collection[str],
    nodrain: Collection[str] = (),
) -> str | None:
    """The disruptive class of a change by `action` with the result `res`; none for a change that
    does not disrupt the host. `units` are the units whose restart does not disrupt it, and
    `nodrain` the units whose restart needs a cordon and no drain (#6338)."""
    args = _module_args(res)
    if action in _REBOOT_ACTIONS:
        return REBOOT
    if action in _DRAIN_ACTIONS:
        state = (args or {}).get("state") or _DRAIN_STATE
        return DRAIN if state == _DRAIN_STATE else None
    if action not in _SERVICE_ACTIONS:
        return None
    if args is not None and args.get("state") not in _DISRUPTIVE_STATES:
        return None
    unit = str((args or {}).get("name") or res.get("name") or _HIDDEN_UNIT)
    if unit in units:
        return None
    if unit in nodrain:
        return f"{SERVICE_RESTART_NODRAIN}:{unit}"
    return f"{SERVICE_RESTART}:{unit}"


def plan_outcome(
    hosts: tuple[HostPlan, ...], status: str, returncode: int, detail: str
) -> tuple[PlanStatus, str | None]:
    """How the run of a plan ended, from the plan of its hosts, the status file of ansible-runner,
    its exit code, and the last line of its output. A failed task names the failure itself."""
    if any(host.failed for host in hosts):
        return PlanStatus.FAILED, None
    if status == _TIMEOUT:
        return PlanStatus.FAILED, MESSAGES.infra.plan_timed_out
    if status != _SUCCESSFUL or returncode != 0:
        return PlanStatus.FAILED, detail or MESSAGES.infra.plan_run_failed.format(code=returncode)
    return PlanStatus.OK, None


def plan_id(content: PlanContent) -> str:
    """The SHA-256 of the canonical JSON of the facts of a plan."""
    facts = content.model_dump(mode="json", include=set(PlanContent.model_fields))
    canonical = json.dumps(facts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def inventory_hash(inventory: AnsibleInventory) -> str:
    """The SHA-256 of the canonical JSON of the groups and the raw host variables."""
    listing = {"groups": inventory.groups, "hostvars": inventory.hostvars}
    canonical = json.dumps(listing, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def plans_folder(repo: RepoRef) -> Path:
    """The folder of the plan records of `repo`: `<data dir>/infra/<owner>/<name>/plans`."""
    owner, name = repo.path_parts
    return resolve_store_path(f"{_STORE}/{owner}/{name}/{_PLANS}")


def collections_folder(requirements: Path) -> Path:
    """The folder of the install of one version of a requirements file, by its SHA-256."""
    digest = hashlib.sha256(requirements.read_bytes()).hexdigest()
    return resolve_store_path(f"{_STORE}/{_COLLECTIONS}/{digest}")


def install_collections(tool: AnsibleTool, project: Path) -> Path | None:
    """The folder of the pinned collections of the repo in `project`, installed once for each
    version of its collection requirements file; none when the repo has no such file.

    Raises:
        InfraReadError: the install fails.
    """
    requirements = find_collection_requirements(project)
    if requirements is None:
        return None
    target = collections_folder(requirements)
    if target.is_dir():
        return target
    target.parent.mkdir(parents=True, exist_ok=True, mode=_PRIVATE)
    staging = Path(tempfile.mkdtemp(prefix=_INSTALL_PREFIX, dir=target.parent))
    try:
        install_requirements(tool, project, staging, requirements=requirements)
        staging.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def runner_env(tool: AnsibleTool, project: Path, collections: Path | None) -> dict[str, str]:
    """The environment that the run adds: the tool environment first on PATH, host key checks on,
    the repo's `ansible.cfg`, the rendered arguments in each result, the results as JSON, a line
    for each skipped host, no color, and the pinned collections."""
    env = tool_env(tool) | _PLAN_ENV | config_env(project)
    if collections is not None:
        env["ANSIBLE_COLLECTIONS_PATH"] = str(collections)
    return env


def runner_argv(
    tool: AnsibleTool,
    folder: Path,
    playbook: str,
    *,
    ident: str,
    pattern: str,
    sources: tuple[str, ...],
    tags: str | None,
    key: Path | None,
    check_mode: bool = True,
) -> list[str]:
    """`ansible-runner run` of `playbook` on the hosts of `pattern`, by default in check mode with
    diffs. The options after `--cmdline=` go to `ansible-playbook`: check mode, the inventory, the
    tags, and the key of `devops ssh` when there is one. With no `check_mode`, the run changes the
    hosts and shows no diffs."""
    options = _CHECK_OPTIONS if check_mode else _RUN_OPTIONS
    words = [*options, *(word for source in sources for word in ("-i", source))]
    if tags:
        words += ["--tags", tags]
    if key is not None:
        words += ["-e", f"ansible_ssh_private_key_file={key}"]
    return tool.argv(
        RUNNER_COMMAND,
        "run",
        str(folder),
        "--playbook",
        playbook,
        "--ident",
        ident,
        "--limit",
        pattern,
        "--quiet",
        f"--cmdline={shlex.join(words)}",
    )


def runner_settings() -> str:
    """The `env/settings` of the run: ansible-runner stops it at the margin below the process
    bound, so it ends with its artifacts and the status `timeout`."""
    job_timeout = (
        int(DEFAULT_INFRA_PLAN_TIMEOUT_SECONDS) - DEFAULT_INFRA_PLAN_TIMEOUT_MARGIN_SECONDS
    )
    return f"job_timeout: {job_timeout}\n"


def plan_entry(target: OnboardTarget, settings: Settings) -> InfraRepoConfig:
    """The settings entry of the repo, or an entry with the defaults when the settings hold none,
    after the check of the level that a plan needs.

    Raises:
        InfraAccessRefusedError: an agent plans on a repo below the level `plan`.
    """
    entry = settings.infra.entry(target.repo) or InfraRepoConfig(repo=target.repo.display)
    require_agent_level(
        entry.agent_access, AgentAccess.PLAN, action=PLAN_ACTION, repo=target.repo.display
    )
    return entry


@dataclass(frozen=True)
class PlanRequest:
    """What the caller plans: a playbook relative to the repo root, the limit, the tags, and the
    ref at origin, by default the default branch."""

    playbook: str
    limit: str | None = None
    tags: str | None = None
    ref: str | None = None


def run_plan(
    target: OnboardTarget,
    entry: InfraRepoConfig,
    settings: Settings,
    request: PlanRequest,
) -> tuple[InfraPlan, ReadCommit]:
    """Plan the playbook of `request` in check mode, keep the plan record, and give it with the
    commit that it read.

    Raises:
        InfraReadError: no Ansible tool environment is installed, a read of the repo fails, the
            playbook is not a file of the repo, the profile names no inventory, or the install
            of the collections fails.
    """
    tool = ansible_tool()
    if not tool.installed:
        raise InfraReadError(ERRORS.infra.tool_missing)
    plans = plans_folder(target.repo)
    plans.mkdir(parents=True, exist_ok=True, mode=_PRIVATE)
    folder = Path(tempfile.mkdtemp(prefix=_RUN_PREFIX, dir=plans))
    try:
        project = folder / PROJECT_FOLDER
        read = export_commit(target.path, project, ref=request.ref)
        content, ident = _run(target, entry, settings, request, tool, folder, read)
        shutil.rmtree(project)
        kept = _keep(folder, plans / plan_id(content))
    except BaseException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    plan = InfraPlan(
        **content.model_dump(),
        id=kept.name,
        created=datetime.now(UTC),
        runner_ident=ident,
        folder=str(kept),
    )
    (kept / PLAN_FILE).write_text(plan.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return plan, read


def _run(
    target: OnboardTarget,
    entry: InfraRepoConfig,
    settings: Settings,
    request: PlanRequest,
    tool: AnsibleTool,
    folder: Path,
    read: ReadCommit,
) -> tuple[PlanContent, str]:
    """Run the playbook in the export in `folder`, and give the facts of the plan and the runner
    ident."""
    project = folder / PROJECT_FOLDER
    playbook = _playbook(project, request.playbook)
    ansible = resolve_profile(project).profile.ansible
    sources = tuple(ansible.inventory)
    if not sources:
        raise InfraReadError(ERRORS.infra.no_inventory.format(repo=target.repo.display))
    inventory = read_inventory(tool, project, sources)
    pattern = host_pattern(request.limit, ansible.offline_group)
    run = Playbook(
        tool=tool,
        folder=folder,
        playbook=playbook,
        sources=sources,
        tags=request.tags,
        key=find_newest_key(settings.ssh.key_dir, prefix=entry.ssh_key_prefix),
        collections=install_collections(tool, project),
        nondisruptive=nondisruptive_units(inventory),
        nodrain=nodrain_units(inventory),
    )
    write_runner_settings(folder)
    outcome = run.run(pattern)
    status, error = plan_outcome(outcome.hosts, outcome.status, outcome.returncode, outcome.detail)
    content = PlanContent(
        repo=target.repo.display,
        ref=read.ref,
        commit=read.commit,
        playbook=playbook,
        limit=request.limit,
        host_pattern=pattern,
        tags=request.tags,
        inventory_hash=inventory_hash(inventory),
        status=status,
        error=error,
        hosts=outcome.hosts,
    )
    return content, outcome.ident


def write_runner_settings(folder: Path) -> None:
    """Write the `env/settings` of the private data folder `folder` (`runner_settings`)."""
    settings_file = folder.joinpath(*_SETTINGS_FILE)
    settings_file.parent.mkdir(mode=_PRIVATE)
    settings_file.write_text(runner_settings(), encoding="utf-8")


@dataclass(frozen=True)
class RunOutcome:
    """How one `ansible-runner` run ended: its ident, the plan of each host from its job events,
    its status file, its exit code and the last line of its output."""

    ident: str
    hosts: tuple[HostPlan, ...]
    status: str
    returncode: int
    detail: str


@dataclass(frozen=True)
class Playbook:
    """A playbook in the export of an infra repo in `<folder>/project`, and what each run of it
    gets: the inventory, the tags, the key of `devops ssh`, the pinned collections, the units of
    each host whose restart does not disrupt it, and the units of each host whose restart needs a
    cordon and no drain (#6338)."""

    tool: AnsibleTool
    folder: Path
    playbook: str
    sources: tuple[str, ...]
    tags: str | None
    key: Path | None
    collections: Path | None
    nondisruptive: Mapping[str, Collection[str]]
    nodrain: Mapping[str, Collection[str]] = field(default_factory=dict)

    @property
    def project(self) -> Path:
        """The export of the repo."""
        return self.folder / PROJECT_FOLDER

    def run(self, pattern: str, *, check_mode: bool = True) -> RunOutcome:
        """Run the playbook on the hosts of `pattern` with a new ident, by default in check mode,
        and read its job events."""
        ident = uuid.uuid4().hex
        result = run_subprocess(
            runner_argv(
                self.tool,
                self.folder,
                self.playbook,
                ident=ident,
                pattern=pattern,
                sources=self.sources,
                tags=self.tags,
                key=self.key,
                check_mode=check_mode,
            ),
            env=runner_env(self.tool, self.project, self.collections),
            quiet=True,
            timeout=DEFAULT_INFRA_PLAN_TIMEOUT_SECONDS,
        )
        artifacts = self.folder / _ARTIFACTS / ident
        hosts = host_plans(
            read_job_events(artifacts / _JOB_EVENTS),
            self.project,
            self.nondisruptive,
            self.nodrain,
        )
        detail = _last_line(_read(artifacts / _STDOUT_FILE) or result.stderr or result.stdout)
        return RunOutcome(
            ident=ident,
            hosts=hosts,
            status=_read(artifacts / _STATUS_FILE).strip(),
            returncode=result.returncode,
            detail=detail.replace(str(self.folder), _FOLDER_MARK),
        )


def _playbook(project: Path, playbook: str) -> str:
    """The playbook as a path relative to the repo root.

    Raises:
        InfraReadError: the playbook is not a file in the repo.
    """
    root = project.resolve()
    direct = (project / playbook).resolve()
    if direct.is_relative_to(root) and direct.is_file():
        return direct.relative_to(root).as_posix()

    for sub in ("ansible/playbooks", "playbooks"):
        candidate = (project / sub / playbook).resolve()
        if candidate.is_relative_to(root) and candidate.is_file():
            return candidate.relative_to(root).as_posix()

    raise InfraReadError(ERRORS.infra.playbook_not_found.format(playbook=playbook))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


def _last_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return mask_secrets(lines[-1]) if lines else ""


def _keep(folder: Path, final: Path) -> Path:
    """Move the run folder to the folder of its plan id; a plan of the same id is replaced."""
    if final.exists():
        shutil.rmtree(final)
    folder.rename(final)
    return final


def render_plan_header(plan: InfraPlan, read: ReadCommit) -> list[str]:
    """The title of the text report and the lines of the commit that it read."""
    title = MESSAGES.infra.plan_title.format(
        repo=plan.repo, playbook=plan.playbook, pattern=plan.host_pattern
    )
    return [title, *render_read(read)]


def plan_tables(plan: InfraPlan) -> tuple[list[str], list[list[str]], list[str], list[list[str]]]:
    """The columns and cells of the table of hosts, then of the table of tasks: one line for
    each change, unchecked task and failed task of each host."""
    texts = MESSAGES.infra
    host_cells = [
        [
            host.host,
            str(len(host.changed)),
            ", ".join(host.disruptive),
            str(len(host.hidden_diffs)),
            str(len(host.unchecked)),
            texts.plan_failed if host.failed else texts.plan_ok,
        ]
        for host in plan.hosts
    ]
    task_cells: list[list[str]] = []
    for host in plan.hosts:
        for change in host.changed:
            kind = texts.plan_kind_hidden if change.diff_hidden else texts.plan_kind_changed
            task_cells.append([host.host, kind, change.name, change.path])
        task_cells += [
            [host.host, texts.plan_kind_unchecked, t.name, t.path] for t in host.unchecked
        ]
        task_cells += [
            [host.host, texts.plan_kind_failed, f"{t.name}: {t.reason or ''}".rstrip(": "), t.path]
            for t in host.failed
        ]
    return list(texts.plan_host_columns), host_cells, list(texts.plan_task_columns), task_cells


def render_plan_footer(plan: InfraPlan) -> list[str]:
    """The lines under the tables: the error of a failed run, and the id and folder of the plan."""
    texts = MESSAGES.infra
    lines = [texts.plan_error.format(error=plan.error)] if plan.error else []
    lines.append(texts.plan_saved.format(id=plan.id, status=plan.status.value, folder=plan.folder))
    return lines


__all__ = [
    "DRAIN",
    "NODRAIN_UNITS_VARIABLE",
    "NONDISRUPTIVE_UNITS_VARIABLE",
    "PLAN_ACTION",
    "PLAN_FILE",
    "PROJECT_FOLDER",
    "REBOOT",
    "SERVICE_RESTART",
    "SERVICE_RESTART_NODRAIN",
    "PlanRequest",
    "Playbook",
    "RunOutcome",
    "collections_folder",
    "disruptive_class",
    "host_pattern",
    "host_plans",
    "install_collections",
    "inventory_hash",
    "nodrain_units",
    "nondisruptive_units",
    "plan_entry",
    "plan_id",
    "plan_outcome",
    "plan_tables",
    "plans_folder",
    "render_plan_footer",
    "render_plan_header",
    "run_plan",
    "runner_argv",
    "runner_env",
    "runner_settings",
    "skips_drain",
    "write_runner_settings",
]
