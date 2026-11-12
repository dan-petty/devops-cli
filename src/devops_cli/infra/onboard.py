"""Check an Ansible infra repo for what `devops infra` needs, and write its settings entry (#5121).

The check reads only the local checkout and local tool output: the project profile of the repo
(`devops_cli.project.profile`), `ansible-config dump` and `ansible-inventory --list` of the Ansible
tool environment, `ssh-keygen -F` against `~/.ssh/known_hosts`, `kubectl config get-contexts`,
and the files of the repo. It opens no connection to a host and sends no request. Each check gives
one row with a state, a reason and the step that fixes a gap, as `devops roadmap onboard` does.

The profile gives the layout: the inventory, the playbook folder, the role folders and the group of
hosts out of service. A host variable comes raw from `ansible-inventory --list`: onboarding reads
whether a host sets `devops_infra_node_service`, and a later command renders its value.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from devops_cli.config.settings import (
    InfraRepoConfig,
    Settings,
    get_active_config_path,
    save_settings,
)
from devops_cli.core.binaries import check_binary
from devops_cli.core.process import run_subprocess
from devops_cli.core.repo import get_repo_origin_name
from devops_cli.crypto.ssh_keys import find_newest_key
from devops_cli.exceptions import DevOpsCLIError
from devops_cli.exceptions.infra import InfraRepoNotFoundError
from devops_cli.github.repo_ref import RepoRef, is_repository_name
from devops_cli.infra.access import AgentAccess
from devops_cli.infra.ansible_facts import (
    AnsibleConfig,
    AnsibleInventory,
    AnsibleTool,
    ansible_tool,
    inventory_host_key_checks_off,
    is_template,
    read_config,
    read_inventory,
)
from devops_cli.infra.repo_content import (
    YamlContent,
    find_ci_workflows,
    find_node_targets,
    find_roles,
    read_collection_requirements,
    read_yaml_content,
)
from devops_cli.lang import ERRORS, MESSAGES
from devops_cli.models.infra import OnboardReport, OnboardRow, OnboardState
from devops_cli.project.profile import ProjectType, ResolvedProfile, resolve_profile

NODE_SERVICE_VARIABLE: Final[str] = "devops_infra_node_service"
KUBE_CONTEXTS_ARGV: Final[tuple[str, ...]] = ("kubectl", "config", "get-contexts", "-o", "name")
_HOST_VARIABLES: Final[tuple[str, ...]] = ("ansible_host", "ansible_ssh_host")
_PORT_VARIABLES: Final[tuple[str, ...]] = ("ansible_port", "ansible_ssh_port")
_SSH_PORT: Final[int] = 22
_LOCAL_READ_TIMEOUT_SECONDS: Final[float] = 30.0
_SETTINGS_ROW: Final[int] = 17

_PRESENT = OnboardState.PRESENT
_MISSING = OnboardState.MISSING
_NOT_READABLE = OnboardState.NOT_READABLE
_LISTED = OnboardState.LISTED


@dataclass(frozen=True)
class OnboardTarget:
    """The infra repo to onboard: its GitHub name, its checkout and the checkout's default place."""

    repo: RepoRef
    path: Path
    default_path: Path


def default_checkout(repo: RepoRef, settings: Settings) -> Path:
    """`<repos.base_dir>/<owner>/<name>`, where `devops repos` puts a clone."""
    return settings.repos.base_dir.expanduser().resolve().joinpath(*repo.path_parts)


def resolve_target(argument: str, *, path: Path | None, settings: Settings) -> OnboardTarget:
    """The repo that `argument` names: `owner/name`, with its checkout from `path`, the settings
    entry or the default place; or the folder of a checkout, named by its remote `origin`.

    Raises:
        InfraRepoNotFoundError: the checkout is not a folder, or a folder has no GitHub origin.
    """
    if is_repository_name(argument):
        repo = RepoRef(argument)
        entry = settings.infra.entry(repo)
        chosen = (
            path or (entry.path if entry is not None else None) or default_checkout(repo, settings)
        )
        checkout = chosen.expanduser().resolve()
        if not checkout.is_dir():
            message = ERRORS.infra.repo_not_found.format(repo=repo.display, path=checkout)
            raise InfraRepoNotFoundError(message, path=str(checkout))
        return OnboardTarget(repo, checkout, default_checkout(repo, settings))
    checkout = Path(argument).expanduser().resolve()
    if not checkout.is_dir():
        message = ERRORS.infra.path_not_a_folder.format(path=checkout)
        raise InfraRepoNotFoundError(message, path=str(checkout))
    origin = get_repo_origin_name(checkout)
    if origin is None or not is_repository_name(origin):
        message = ERRORS.infra.no_origin.format(path=checkout)
        raise InfraRepoNotFoundError(message, path=str(checkout))
    repo = RepoRef(origin)
    return OnboardTarget(repo, checkout, default_checkout(repo, settings))


def onboard_entry(
    target: OnboardTarget,
    settings: Settings,
    *,
    kube_context: str | None = None,
    ssh_key_prefix: str | None = None,
    agent_access: AgentAccess | None = None,
) -> InfraRepoConfig:
    """The settings entry of the repo: the entry that the settings hold, with each option that the
    caller gives. A new entry is at agent access `none`."""
    existing = settings.infra.entry(target.repo)
    base = existing.model_dump() if existing is not None else {"repo": target.repo.display}
    updates: dict[str, object] = {
        "path": None if target.path == target.default_path else target.path
    }
    if kube_context is not None:
        updates["kube_context"] = kube_context
    if ssh_key_prefix is not None:
        updates["ssh_key_prefix"] = ssh_key_prefix
    if agent_access is not None:
        updates["agent_access"] = agent_access
    return InfraRepoConfig.model_validate(base | updates)


@dataclass(frozen=True)
class _Facts:
    """What the checks read: the profile, the Ansible tool, the config, the inventory and the YAML
    files."""

    root: Path
    profile: ResolvedProfile
    tool: AnsibleTool
    config: AnsibleConfig | str
    inventory: AnsibleInventory | str
    content: YamlContent


def check_onboarding(
    target: OnboardTarget,
    settings: Settings,
    *,
    kube_context: str | None = None,
    ssh_key_prefix: str | None = None,
    agent_access: AgentAccess | None = None,
) -> OnboardReport:
    """Check the infra repo of `target` and give one row for each check."""
    entry = onboard_entry(
        target,
        settings,
        kube_context=kube_context,
        ssh_key_prefix=ssh_key_prefix,
        agent_access=agent_access,
    )
    facts = _read_facts(target.path)
    rows = [
        _tool_row(facts),
        _profile_row(facts),
        _config_file_row(facts),
        _inventory_row(facts),
        _offline_row(facts),
        _playbooks_row(facts),
        _roles_row(facts),
        _collections_row(facts),
        _host_key_row(facts),
        _known_hosts_row(facts),
        _ssh_key_row(entry, settings),
        _kube_context_row(entry),
        _ci_row(facts),
        _node_service_row(facts),
        _check_mode_row(facts),
        _node_targets_row(facts),
        _settings_row(target, settings),
    ]
    return OnboardReport(
        repo=target.repo.display,
        path=str(target.path),
        rows=tuple(row.model_copy(update={"number": n}) for n, row in enumerate(rows, start=1)),
        entry=entry.model_dump(mode="json"),
    )


def _read_facts(root: Path) -> _Facts:
    profile = resolve_profile(root)
    sources = tuple(profile.profile.ansible.inventory)
    tool = ansible_tool()
    config: AnsibleConfig | str = MESSAGES.infra.tool_missing
    inventory: AnsibleInventory | str = MESSAGES.infra.tool_missing
    if tool.installed:
        config = _attempt(lambda: read_config(tool, root))
    if isinstance(config, AnsibleConfig):
        inventory = (
            _attempt(lambda: read_inventory(tool, root, sources))
            if sources
            else MESSAGES.infra.no_inventory
        )
    elif tool.installed:
        inventory = config
    return _Facts(root, profile, tool, config, inventory, read_yaml_content(root))


def _attempt[T](read: Callable[[], T]) -> T | str:
    """The result of `read`, or the message of the error that stopped it."""
    try:
        return read()
    except DevOpsCLIError as exc:
        return exc.message


def _row(
    check: str,
    state: OnboardState,
    reason: str | None = None,
    step: str | None = None,
    items: tuple[str, ...] = (),
) -> OnboardRow:
    """A row with no number yet: the report numbers its rows in order."""
    return OnboardRow(number=0, check=check, state=state, reason=reason, step=step, items=items)


def _tool_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    tool = facts.tool
    if not tool.installed:
        return _row(texts.check_tool, _MISSING, texts.tool_missing, texts.tool_step)
    if tool.version is not None:
        return _row(texts.check_tool, _PRESENT, texts.tool_version.format(version=tool.version))
    return _row(texts.check_tool, _PRESENT, texts.tool_on_path.format(folder=tool.bin_dir))


def _profile_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    resolved = facts.profile
    kind = resolved.profile.extends
    check = texts.check_profile.format(type=ProjectType.ANSIBLE_K8S.value)
    if kind is not ProjectType.ANSIBLE_K8S:
        return _row(check, _MISSING, texts.profile_no_type, texts.profile_type_step)
    if resolved.project_file:
        items = _sourced(resolved, list(resolved.sources))
        return _row(check, _PRESENT, texts.profile_declared, items=items)
    reason = texts.profile_detected.format(source=resolved.sources["extends"])
    items = _sourced(resolved, list(resolved.declarable()))
    return _row(check, _LISTED, reason, texts.profile_step, items)


def _sourced(resolved: ResolvedProfile, keys: list[str]) -> tuple[str, ...]:
    """Each value of `keys` with its source, as `<key> = <value> (<source>)`."""
    values = resolved.profile.model_dump(mode="json")
    return tuple(
        f"{key} = {json.dumps(_at(values, key))} ({resolved.sources[key]})" for key in keys
    )


def _at(values: dict[str, object], key: str) -> object:
    """The value of a dotted key in a nested mapping."""
    found: object = values
    for part in key.split("."):
        found = found[part] if isinstance(found, dict) else None
    return found


def _config_file_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    if isinstance(facts.config, str):
        return _row(texts.check_config_file, _NOT_READABLE, facts.config)
    expected = (facts.root / "ansible.cfg").resolve()
    found = facts.config.config_file
    if found is not None and found.resolve() == expected:
        return _row(texts.check_config_file, _PRESENT)
    reason = texts.config_file_other.format(file=found) if found else texts.config_file_none
    return _row(texts.check_config_file, _MISSING, reason, texts.config_file_step)


def _inventory_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    if isinstance(facts.config, str):
        return _row(texts.check_inventory, _NOT_READABLE, facts.config)
    if isinstance(facts.inventory, str):
        state = _MISSING if facts.inventory == texts.no_inventory else _NOT_READABLE
        reason = texts.inventory_none if state is _MISSING else facts.inventory
        return _row(
            texts.check_inventory,
            state,
            reason,
            texts.inventory_step if state is _MISSING else None,
        )
    inventory = facts.inventory
    if not inventory.hosts:
        return _row(texts.check_inventory, _MISSING, texts.inventory_no_hosts, texts.inventory_step)
    items = tuple(f"{name}: {_count(hosts, 'host')}" for name, hosts in inventory.groups.items())
    reason = texts.inventory_found.format(hosts=len(inventory.hosts), groups=len(inventory.groups))
    return _row(texts.check_inventory, _PRESENT, reason, items=items)


def _count(things: tuple[str, ...], noun: str) -> str:
    return f"{len(things)} {noun}{'' if len(things) == 1 else 's'}"


def in_service_hosts(inventory: AnsibleInventory, offline_group: str | None) -> tuple[str, ...]:
    """The hosts that are not in the group of hosts out of service."""
    offline = set(inventory.groups.get(offline_group, ())) if offline_group else set()
    return tuple(host for host in inventory.hosts if host not in offline)


def _offline_group(facts: _Facts) -> str | None:
    return facts.profile.profile.ansible.offline_group


def _offline_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    group = _offline_group(facts)
    check = texts.check_offline.format(group=group or texts.offline_unnamed)
    if isinstance(facts.inventory, str):
        return _row(check, _NOT_READABLE, facts.inventory)
    if group is None or group not in facts.inventory.groups:
        step = texts.offline_step.format(group=group or "offline")
        return _row(check, _MISSING, step=step)
    hosts = facts.inventory.groups[group]
    return _row(check, _PRESENT, texts.offline_found.format(count=len(hosts)), items=hosts)


def _playbooks_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    content = facts.content
    folder = facts.profile.profile.ansible.playbook_dir
    playbooks = tuple(
        path for path in content.playbooks if folder and path.startswith(f"{folder}/")
    )
    unparsed = (
        texts.playbooks_unparsed.format(
            count=len(content.unparsed), files=", ".join(content.unparsed)
        )
        if content.unparsed
        else None
    )
    if not playbooks:
        missing = (
            texts.playbooks_none.format(folder=folder) if folder else texts.playbooks_no_folder
        )
        reason = " ".join(filter(None, [missing, unparsed]))
        return _row(texts.check_playbooks, _MISSING, reason, texts.playbooks_step)
    found = texts.playbooks_found.format(count=len(playbooks), folder=folder)
    reason = " ".join(filter(None, [found, unparsed]))
    return _row(texts.check_playbooks, _PRESENT, reason, items=playbooks)


def _roles_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    folders = tuple(facts.root / folder for folder in facts.profile.profile.ansible.roles_path)
    roles = find_roles(facts.root, folders)
    if not roles:
        return _row(texts.check_roles, _MISSING, step=texts.roles_step)
    return _row(
        texts.check_roles, _PRESENT, texts.roles_found.format(count=len(roles)), items=roles
    )


def _collections_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    used = facts.content.collections_used
    uses = (
        texts.collections_used.format(names=", ".join(used))
        if used
        else texts.collections_none_used
    )
    requirements = read_collection_requirements(facts.root)
    if requirements.path is None:
        reason = f"{texts.collections_no_file} {uses}"
        return _row(texts.check_collections, _MISSING, reason, texts.collections_step)
    if requirements.error is not None:
        reason = texts.collections_not_yaml.format(path=requirements.path, error=requirements.error)
        return _row(texts.check_collections, _MISSING, reason, texts.collections_step)
    if requirements.unpinned:
        reason = texts.collections_unpinned.format(count=len(requirements.unpinned))
        return _row(
            texts.check_collections, _MISSING, reason, texts.collections_step, requirements.unpinned
        )
    return _row(texts.check_collections, _PRESENT, uses)


def _host_key_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    if isinstance(facts.config, str):
        return _row(texts.check_host_key_checks, _NOT_READABLE, facts.config)
    if isinstance(facts.inventory, str) and facts.inventory != texts.no_inventory:
        return _row(texts.check_host_key_checks, _NOT_READABLE, facts.inventory)
    found = facts.config.host_key_checks_off
    if not isinstance(facts.inventory, str):
        found += inventory_host_key_checks_off(facts.inventory)
    if not found:
        return _row(texts.check_host_key_checks, _PRESENT)
    reason = texts.host_key_checks_off.format(count=len(found))
    return _row(texts.check_host_key_checks, _MISSING, reason, texts.host_key_checks_step, found)


def _ssh_target(host: str, variables: dict[str, object]) -> str:
    """The name that `ssh` looks up in `known_hosts` for a host: its address, with the port in
    brackets when it is not 22."""
    address = next((str(variables[name]) for name in _HOST_VARIABLES if variables.get(name)), host)
    port = next((variables[name] for name in _PORT_VARIABLES if variables.get(name)), _SSH_PORT)
    if is_template(address):
        address = host
    return address if str(port) == str(_SSH_PORT) or is_template(port) else f"[{address}]:{port}"


def known_hosts_file() -> Path:
    """The `known_hosts` file of the person, which `ssh` reads."""
    return Path.home() / ".ssh" / "known_hosts"


def _known_hosts_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    if isinstance(facts.inventory, str):
        return _row(texts.check_known_hosts, _NOT_READABLE, facts.inventory)
    hosts = in_service_hosts(facts.inventory, _offline_group(facts))
    file = known_hosts_file()
    unknown = tuple(
        host
        for host in hosts
        if not _is_known(_ssh_target(host, facts.inventory.hostvars[host]), file)
    )
    if not unknown:
        return _row(
            texts.check_known_hosts, _PRESENT, texts.known_hosts_found.format(count=len(hosts))
        )
    reason = texts.known_hosts_unknown.format(count=len(unknown), total=len(hosts), file=file)
    return _row(texts.check_known_hosts, _MISSING, reason, texts.known_hosts_step, unknown)


def _is_known(target: str, file: Path) -> bool:
    """Whether `ssh-keygen -F` finds a key of `target` in `file`."""
    if not file.is_file():
        return False
    result = run_subprocess(
        ["ssh-keygen", "-F", target, "-f", str(file)],
        quiet=True,
        timeout=_LOCAL_READ_TIMEOUT_SECONDS,
    )
    return result.returncode == 0


def _ssh_key_row(entry: InfraRepoConfig, settings: Settings) -> OnboardRow:
    texts = MESSAGES.infra
    prefix = entry.ssh_key_prefix
    check = texts.check_ssh_key.format(prefix=prefix)
    key = find_newest_key(settings.ssh.key_dir, prefix=prefix)
    if key is None:
        reason = texts.ssh_key_none.format(prefix=prefix, folder=settings.ssh.key_dir.expanduser())
        return _row(check, _MISSING, reason, texts.ssh_key_step.format(prefix=prefix))
    return _row(check, _PRESENT, items=(key.name,))


def _kube_context_row(entry: InfraRepoConfig) -> OnboardRow:
    texts = MESSAGES.infra
    if not check_binary("kubectl"):
        return _row(texts.check_kube_context, _NOT_READABLE, texts.kube_context_no_kubectl)
    result = run_subprocess(
        list(KUBE_CONTEXTS_ARGV), quiet=True, timeout=_LOCAL_READ_TIMEOUT_SECONDS
    )
    if result.returncode != 0:
        reason = texts.kube_context_failed.format(code=result.returncode)
        return _row(texts.check_kube_context, _NOT_READABLE, reason)
    contexts = tuple(line.strip() for line in result.stdout.splitlines() if line.strip())
    name = entry.kube_context
    if name is not None and name in contexts:
        return _row(texts.check_kube_context, _PRESENT, items=(name,))
    reason = (
        texts.kube_context_not_set if name is None else texts.kube_context_absent.format(name=name)
    )
    return _row(texts.check_kube_context, _MISSING, reason, texts.kube_context_step, contexts)


def _ci_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    workflows = find_ci_workflows(facts.root)
    if not workflows:
        return _row(texts.check_ci, _MISSING, step=texts.ci_step)
    return _row(texts.check_ci, _PRESENT, items=workflows)


def _node_service_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    if isinstance(facts.inventory, str):
        return _row(texts.check_node_service, _NOT_READABLE, facts.inventory)
    unset = tuple(
        host
        for host in in_service_hosts(facts.inventory, _offline_group(facts))
        if not facts.inventory.hostvars[host].get(NODE_SERVICE_VARIABLE)
    )
    if not unset:
        return _row(texts.check_node_service, _PRESENT)
    reason = texts.node_service_unset.format(count=len(unset))
    return _row(texts.check_node_service, _LISTED, reason, texts.node_service_step, unset)


def _check_mode_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    tasks = facts.content.check_mode_off
    if not tasks:
        return _row(texts.check_check_mode, _PRESENT)
    reason = texts.check_mode_tasks.format(count=len(tasks))
    return _row(texts.check_check_mode, _LISTED, reason, texts.check_mode_step, tasks)


def _node_targets_row(facts: _Facts) -> OnboardRow:
    texts = MESSAGES.infra
    targets = find_node_targets(facts.root)
    if not targets:
        return _row(texts.check_node_targets, _PRESENT)
    reason = texts.node_targets_found.format(count=len(targets))
    return _row(texts.check_node_targets, _LISTED, reason, texts.node_targets_step, targets)


def _settings_row(target: OnboardTarget, settings: Settings) -> OnboardRow:
    texts = MESSAGES.infra
    existing = settings.infra.entry(target.repo)
    if existing is None:
        return _row(texts.check_settings, _MISSING, step=texts.settings_step)
    return _row(
        texts.check_settings, _PRESENT, texts.settings_level.format(level=existing.agent_access)
    )


def write_entry(report: OnboardReport, settings: Settings) -> OnboardReport:
    """Write the entry of the report into `infra.repos` of the active config file, in place of
    the entry of the same repo, and mark the last row present."""
    entry = InfraRepoConfig.model_validate(report.entry)
    repo = RepoRef(entry.repo)
    repos = list(settings.infra.repos)
    index = next((n for n, item in enumerate(repos) if RepoRef(item.repo) == repo), len(repos))
    repos[index : index + 1] = [entry]
    settings.infra.repos = repos
    save_settings(settings)
    path = get_active_config_path()
    texts = MESSAGES.infra
    reason = texts.settings_written.format(level=entry.agent_access, path=path)
    rows = list(report.rows)
    rows[_SETTINGS_ROW - 1] = OnboardRow(
        number=_SETTINGS_ROW, check=texts.check_settings, state=_PRESENT, reason=reason
    )
    return report.model_copy(update={"rows": tuple(rows), "written_to": str(path)})


def render_onboarding(report: OnboardReport) -> str:
    """The report as text: one line for each row, then its items and its step."""
    lines = [MESSAGES.infra.onboard_title.format(repo=report.repo, path=report.path)]
    for row in report.rows:
        reason = f" ({row.reason})" if row.reason else ""
        lines.append(f"{row.number}. {row.check}: {row.state}{reason}")
        lines.extend(f"   - {item}" for item in row.items)
        if row.step and row.state is not _PRESENT:
            lines.append(f"   Step: {row.step}")
    return "\n".join(lines)


__all__ = [
    "NODE_SERVICE_VARIABLE",
    "OnboardTarget",
    "check_onboarding",
    "default_checkout",
    "in_service_hosts",
    "known_hosts_file",
    "onboard_entry",
    "render_onboarding",
    "resolve_target",
    "write_entry",
]
