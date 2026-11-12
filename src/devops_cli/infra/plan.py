"""Plan a playbook of an infra repo in check mode, and keep the plan record (#5124).

The plan runs one commit that `origin` holds, never the working tree of the checkout: the reader
exports the commit (`repo_tree.export_commit`) into the project folder of an ansible-runner private
data folder under `<data dir>/infra/<owner>/<name>/plans/` (mode 0700). It reads the profile and
the inventory in the export, installs the pinned collections of `collections/requirements.yml`
once for each version of the file, and runs `ansible-runner run <folder> --playbook <playbook>`
with `--check --diff -v` and the limit `<limit>:!<offline group>`. The run gets the repo's
`ansible.cfg`, the key of `devops ssh` as `ansible_ssh_private_key_file`, host key checks on, and
the environment of the process runner, so no `ANSIBLE_` variable of the person reaches it.

The job events (`artifacts/<ident>/job_events/*.json`) give the plan of each host, with no read of
the repo's YAML:

- **Changed**: a `runner_on_ok` result with `changed`. Its diff is **hidden** when the result holds
  an empty diff (`diff: false`) or is censored (`no_log`). A censored result does not say whether
  it changed, so the censored results of a host count as changes only when the stats of the run
  count more changes on the host than the other results show: the safe side.
- **Unchecked**: a `runner_on_skipped` task that check mode skipped. At verbosity 1 the default
  callback prints the result of a skip after `=> `, and a skip by a false `when` has the key
  `false_condition`. Every other skip, and a result that does not read, is unchecked.
- **Disruptive**: a changed `ansible.builtin.reboot` is `reboot`; a changed
  `kubernetes.core.k8s_drain` with the state `drain` is `drain`; a changed `systemd`,
  `systemd_service` or `service` task with the state `restarted`, `reloaded` or `stopped` is
  `service-restart:<unit>`, unless the host variable `devops_infra_nondisruptive_units` lists the
  unit. `ANSIBLE_INJECT_INVOCATION` puts the rendered arguments in the result; a result with no
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

from devops_cli.config.defaults import (
    DEFAULT_INFRA_GALAXY_TIMEOUT_SECONDS,
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
from devops_cli.infra.ansible_facts import (
    RUNNER_COMMAND,
    AnsibleInventory,
    AnsibleTool,
    ansible_tool,
    is_template,
    read_inventory,
)
from devops_cli.infra.onboard import OnboardTarget
from devops_cli.infra.repo_tree import export_commit, render_read
from devops_cli.infra.status import ping_env
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
REQUIREMENTS_FILE: Final[str] = "collections/requirements.yml"
PLAN_FILE: Final[str] = "plan.json"
PROJECT_FOLDER: Final[str] = "project"
REBOOT: Final[str] = "reboot"
DRAIN: Final[str] = "drain"
SERVICE_RESTART: Final[str] = "service-restart"
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
_PARTIAL_SUFFIX: Final[str] = "-partial.json"
_STDOUT_FILE: Final[str] = "stdout"
_SETTINGS_FILE: Final[tuple[str, str]] = ("env", "settings")
_ANSIBLE_CONFIG: Final[str] = "ansible.cfg"
_PRIVATE: Final[int] = 0o700
_FOLDER_MARK: Final[str] = "<plan folder>"
# The options of `ansible-playbook` of every plan: check mode, the diffs, and verbosity 1, at which
# the default callback prints the result of a skipped task.
_CHECK_OPTIONS: Final[tuple[str, ...]] = ("--check", "--diff", "-v")
# What the run adds to the environment of `ping_env`: the rendered arguments in each result, the
# results as JSON, and a line for each skipped host.
_PLAN_ENV: Final[dict[str, str]] = {
    "ANSIBLE_INJECT_INVOCATION": "True",
    "ANSIBLE_CALLBACK_RESULT_FORMAT": "json",
    "ANSIBLE_DISPLAY_SKIPPED_HOSTS": "True",
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
    of hosts out of service."""
    pattern = limit or _ALL_HOSTS
    return f"{pattern}:!{offline_group}" if offline_group else pattern


def nondisruptive_units(inventory: AnsibleInventory) -> dict[str, frozenset[str]]:
    """The units of each host whose restart does not disrupt it (`devops_infra_nondisruptive_units`).
    Only Ansible renders a template, so a templated value lists no unit: every restart stays
    disruptive."""
    found: dict[str, frozenset[str]] = {}
    for host, variables in inventory.hostvars.items():
        value = variables.get(NONDISRUPTIVE_UNITS_VARIABLE)
        if isinstance(value, list) and not any(is_template(unit) for unit in value):
            found[host] = frozenset(str(unit) for unit in value)
    return found


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
) -> tuple[HostPlan, ...]:
    """The plan of each host that the job events name, sorted by host. `project` is the folder
    that the task paths are relative to, and `nondisruptive` the units of each host whose restart
    does not disrupt it."""
    hosts: dict[str, _Host] = {}
    counted: dict[str, int] = {}
    for event in events:
        kind = event.get("event")
        data = event.get("event_data") or {}
        if kind == _EVENT_STATS:
            counted = {str(host): int(count) for host, count in (data.get("changed") or {}).items()}
            continue
        host = data.get("host")
        if not host or kind not in (_EVENT_OK, _EVENT_SKIPPED, _EVENT_FAILED, _EVENT_UNREACHABLE):
            continue
        _add(hosts.setdefault(str(host), _Host()), str(kind), event, data, project, nondisruptive)
    return tuple(hosts[host].plan(host, counted.get(host)) for host in sorted(hosts))


def _add(
    tasks: _Host,
    kind: str,
    event: Mapping[str, Any],
    data: Mapping[str, Any],
    project: Path,
    nondisruptive: Mapping[str, Collection[str]],
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
        units = nondisruptive.get(str(data.get("host")), ())
        changed = ChangedTask(**task.model_dump(), diff_hidden=True)
        tasks.changes.append(_Change(changed, disruptive_class(task.action, {}, units), True))
    else:
        if any(_is_skipped_item(item) for item in res.get("results") or ()):
            tasks.unchecked.append(task)
        if res.get("changed"):
            hidden = "diff" in res and not res["diff"]
            changed = ChangedTask(**task.model_dump(), diff_hidden=hidden)
            units = nondisruptive.get(str(data.get("host")), ())
            tasks.changes.append(_Change(changed, disruptive_class(task.action, res, units)))


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
    """Whether a skip came from check mode: every skip but one by a false `when`, as the result
    that the callback prints after `=> ` shows."""
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
        return any(not isinstance(item, dict) or _FALSE_CONDITION not in item for item in items)
    return _FALSE_CONDITION not in result


def _is_skipped_item(item: Any) -> bool:
    """Whether one item of a loop result was skipped by check mode."""
    return isinstance(item, dict) and bool(item.get("skipped")) and _FALSE_CONDITION not in item


def _module_args(res: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """The rendered arguments of a result (`ANSIBLE_INJECT_INVOCATION`); none when it has none."""
    invocation = res.get("invocation")
    if not isinstance(invocation, Mapping):
        return None
    args = invocation.get("module_args", invocation)
    return args if isinstance(args, Mapping) else None


def disruptive_class(action: str, res: Mapping[str, Any], units: Collection[str]) -> str | None:
    """The disruptive class of a change by `action` with the result `res`; none for a change that
    does not disrupt the host. `units` are the units whose restart does not disrupt it."""
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


def galaxy_argv(tool: AnsibleTool, requirements: Path, target: Path) -> list[str]:
    """`ansible-galaxy collection install` of a requirements file into `target`."""
    return tool.argv(
        "ansible-galaxy", "collection", "install", "-r", str(requirements), "-p", str(target)
    )


def install_collections(tool: AnsibleTool, project: Path) -> Path | None:
    """The folder of the pinned collections of the repo in `project`, installed once for each
    version of `collections/requirements.yml`; none when the repo has no such file.

    Raises:
        InfraReadError: the install fails.
    """
    requirements = project / REQUIREMENTS_FILE
    if not requirements.is_file():
        return None
    target = collections_folder(requirements)
    if target.is_dir():
        return target
    target.parent.mkdir(parents=True, exist_ok=True, mode=_PRIVATE)
    staging = Path(tempfile.mkdtemp(prefix=_INSTALL_PREFIX, dir=target.parent))
    try:
        result = run_subprocess(
            galaxy_argv(tool, requirements, staging),
            cwd=project,
            env=_config_env(project),
            quiet=True,
            timeout=DEFAULT_INFRA_GALAXY_TIMEOUT_SECONDS,
        )
        if result.returncode != 0:
            raise InfraReadError(
                ERRORS.infra.read_failed.format(
                    command="ansible-galaxy collection install",
                    code=result.returncode,
                    detail=_last_line(result.stderr or result.stdout),
                )
            )
        staging.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return target


def _config_env(project: Path) -> dict[str, str]:
    """`ANSIBLE_CONFIG` of the repo's `ansible.cfg`, when it has one."""
    config = project / _ANSIBLE_CONFIG
    return {"ANSIBLE_CONFIG": str(config)} if config.is_file() else {}


def runner_env(tool: AnsibleTool, project: Path, collections: Path | None) -> dict[str, str]:
    """The environment that the run adds: the tool environment first on PATH, host key checks on,
    the repo's `ansible.cfg`, the rendered arguments in each result, the results as JSON, a line
    for each skipped host, and the pinned collections."""
    env = ping_env(tool) | _PLAN_ENV | _config_env(project)
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
) -> list[str]:
    """`ansible-runner run` of `playbook` in check mode with diffs on the hosts of `pattern`. The
    options after `--cmdline=` go to `ansible-playbook`: check mode, the inventory, the tags, and
    the key of `devops ssh` when there is one."""
    words = [*_CHECK_OPTIONS, *(word for source in sources for word in ("-i", source))]
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
    collections = install_collections(tool, project)
    key = find_newest_key(settings.ssh.key_dir, prefix=entry.ssh_key_prefix)
    pattern = host_pattern(request.limit, ansible.offline_group)
    ident = uuid.uuid4().hex
    settings_file = folder.joinpath(*_SETTINGS_FILE)
    settings_file.parent.mkdir(mode=_PRIVATE)
    settings_file.write_text(runner_settings(), encoding="utf-8")
    result = run_subprocess(
        runner_argv(
            tool,
            folder,
            playbook,
            ident=ident,
            pattern=pattern,
            sources=sources,
            tags=request.tags,
            key=key,
        ),
        env=runner_env(tool, project, collections),
        quiet=True,
        timeout=DEFAULT_INFRA_PLAN_TIMEOUT_SECONDS,
    )
    artifacts = folder / _ARTIFACTS / ident
    hosts = host_plans(
        read_job_events(artifacts / _JOB_EVENTS), project, nondisruptive_units(inventory)
    )
    detail = _last_line(_read(artifacts / _STDOUT_FILE) or result.stderr or result.stdout)
    status, error = plan_outcome(
        hosts,
        _read(artifacts / _STATUS_FILE).strip(),
        result.returncode,
        detail.replace(str(folder), _FOLDER_MARK),
    )
    content = PlanContent(
        repo=target.repo.display,
        ref=read.ref,
        commit=read.commit,
        playbook=playbook,
        limit=request.limit,
        host_pattern=pattern,
        tags=request.tags,
        ansible_core=tool.version,
        inventory_hash=inventory_hash(inventory),
        status=status,
        error=error,
        hosts=hosts,
    )
    return content, ident


def _playbook(project: Path, playbook: str) -> str:
    """The playbook as a path relative to the repo root.

    Raises:
        InfraReadError: the playbook is not a file in the repo.
    """
    path = (project / playbook).resolve()
    root = project.resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise InfraReadError(ERRORS.infra.playbook_not_found.format(playbook=playbook))
    return path.relative_to(root).as_posix()


def read_job_events(folder: Path) -> list[dict[str, Any]]:
    """The job events in `folder`, in the order of their counter; none when the run wrote none.
    ansible-runner writes each event as `<counter>-<uuid>.json` with a rename, and a run that
    stops can leave the callback's `<uuid>-partial.json`, which is not an event."""
    events = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in folder.glob("*.json")
        if not path.name.endswith(_PARTIAL_SUFFIX)
    ]
    return sorted(events, key=lambda event: int(event.get("counter") or 0))


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
    "NONDISRUPTIVE_UNITS_VARIABLE",
    "PLAN_ACTION",
    "PLAN_FILE",
    "PROJECT_FOLDER",
    "REBOOT",
    "REQUIREMENTS_FILE",
    "SERVICE_RESTART",
    "PlanRequest",
    "collections_folder",
    "disruptive_class",
    "galaxy_argv",
    "host_pattern",
    "host_plans",
    "install_collections",
    "inventory_hash",
    "nondisruptive_units",
    "plan_entry",
    "plan_id",
    "plan_outcome",
    "plan_tables",
    "plans_folder",
    "read_job_events",
    "render_plan_footer",
    "render_plan_header",
    "run_plan",
    "runner_argv",
    "runner_env",
    "runner_settings",
]
