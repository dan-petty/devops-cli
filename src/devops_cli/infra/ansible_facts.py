"""The local Ansible facts of an infra repo: its effective config, its inventory and the roles of
its pinned collections (#5121, #6678), and the install of those collections (#5124).

devops runs the Ansible commands of the tool environment of the `ansible-runner` on PATH as child
processes in the root of the checkout. The child gets the environment of
`run_subprocess`, so no `ANSIBLE_` variable of the person reaches it, and the `ansible.cfg` of the
repo alone sets Ansible. No command connects to a host. An inventory script or plugin that the
repo names runs, as it does for each Ansible command in the repo.

`ansible-galaxy collection install` installs the collections of `collections/requirements.yml`
into a folder that the caller gives: it downloads them from Galaxy or from their git sources.
`ansible-doc -t role -l -j` then lists the roles of that folder alone: `ANSIBLE_COLLECTIONS_PATH`
names it, and `ANSIBLE_COLLECTIONS_SCAN_SYS_PATH=False` keeps out the collections of the Python
environment of the tool. The listing holds a role only when the role has an argument spec
(`meta/argument_specs.yml`), and it marks each role of a collection with the key `collection`.
"""

from __future__ import annotations

import json
import shlex
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from devops_cli.config.defaults import (
    DEFAULT_INFRA_ANSIBLE_READ_TIMEOUT_SECONDS,
    DEFAULT_INFRA_GALAXY_TIMEOUT_SECONDS,
)
from devops_cli.core.binaries import check_binary, require_binary
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.infra import InfraReadError
from devops_cli.lang import ERRORS
from devops_cli.security.sanitizer import mask_secrets

RUNNER_COMMAND: Final[str] = "ansible-runner"
CONFIG_DUMP_ARGS: Final[tuple[str, ...]] = ("dump", "--format", "json", "--only-changed")
INVENTORY_LIST_ARGS: Final[tuple[str, ...]] = ("--list",)
REQUIREMENTS_FILE: Final[str] = "collections/requirements.yml"
DOC_COMMAND: Final[str] = "ansible-doc"
ROLE_LIST_ARGS: Final[tuple[str, ...]] = ("-t", "role", "-l", "-j")
_GALAXY_INSTALL: Final[str] = "ansible-galaxy collection install"
_ANSIBLE_CONFIG: Final[str] = "ansible.cfg"
# The settings of ansible-core that give the collection folders of a command
# (`COLLECTIONS_PATHS`, `COLLECTIONS_SCAN_SYS_PATH`), and the key of the listing that names the
# collection of a role.
_COLLECTIONS_PATH_ENV: Final[str] = "ANSIBLE_COLLECTIONS_PATH"
_SCAN_SYS_PATH_ENV: Final[str] = "ANSIBLE_COLLECTIONS_SCAN_SYS_PATH"
_COLLECTION_KEY: Final[str] = "collection"
# The groups that Ansible makes in every inventory.
_IMPLICIT_GROUPS: Final[frozenset[str]] = frozenset({"all", "ungrouped"})
# The options of the `ssh` connection plugin that hold OpenSSH options, and the inventory
# variables that set them for a host (`ansible-doc -t connection ssh`).
_SSH_OPTION_SETTINGS: Final[tuple[str, ...]] = ("ssh_args", "ssh_common_args", "ssh_extra_args")
_SSH_OPTION_VARIABLES: Final[tuple[str, ...]] = (
    "ansible_ssh_args",
    "ansible_ssh_common_args",
    "ansible_ssh_extra_args",
)
_HOST_KEY_VARIABLES: Final[tuple[str, ...]] = (
    "ansible_host_key_checking",
    "ansible_ssh_host_key_checking",
)
# The values that Ansible reads as false (`ansible.module_utils.parsing.convert_bool`).
_ANSIBLE_FALSE: Final[frozenset[str]] = frozenset({"n", "no", "off", "0", "false", "f"})
# The OpenSSH options that turn host key checks off (ssh_config(5)), in lower case.
_STRICT_HOST_KEY_CHECKING: Final[str] = "stricthostkeychecking"
_USER_KNOWN_HOSTS_FILE: Final[str] = "userknownhostsfile"
_STRICT_OFF: Final[frozenset[str]] = frozenset({"no", "off"})
_NO_KNOWN_HOSTS: Final[tuple[str, ...]] = ("/dev/null",)
_TEMPLATE_START: Final[str] = "{{"


@dataclass(frozen=True)
class AnsibleTool:
    """The Ansible tool environment: the `bin` folder of the `ansible-runner` on PATH, or none
    when no `ansible-runner` is on PATH."""

    bin_dir: Path | None

    @property
    def installed(self) -> bool:
        """Whether an `ansible-runner` is on PATH."""
        return self.bin_dir is not None

    def argv(self, command: str, *args: str) -> list[str]:
        """The command line of `command` of the environment, with `args`. With no environment,
        the command has no folder, as a dry run shows it."""
        program = command if self.bin_dir is None else str(self.bin_dir / command)
        return [program, *args]


def ansible_tool() -> AnsibleTool:
    """The Ansible tool environment: the folder of the `ansible-runner` on PATH, such as the one of
    the devtools image (#4362). Only `ansible-runner` goes on PATH; the other commands are beside
    it, so the folder is the one of the resolved file."""
    if not check_binary(RUNNER_COMMAND):
        return AnsibleTool(bin_dir=None)
    return AnsibleTool(bin_dir=require_binary(RUNNER_COMMAND).parent)


@dataclass(frozen=True)
class AnsibleConfig:
    """The effective Ansible config of a checkout, from `ansible-config dump --only-changed`."""

    config_file: Path | None
    # Each setting that turns host key checks off, as `<origin>: <setting>`.
    host_key_checks_off: tuple[str, ...]


@dataclass(frozen=True)
class AnsibleInventory:
    """The hosts and groups of an inventory, from `ansible-inventory --list`. A host variable is
    raw: a template in it is not rendered."""

    groups: dict[str, tuple[str, ...]]
    hostvars: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def hosts(self) -> tuple[str, ...]:
        """Every host of the inventory, sorted."""
        return tuple(sorted(self.hostvars))


def read_config(tool: AnsibleTool, root: Path) -> AnsibleConfig:
    """The effective Ansible config of the checkout at `root`.

    Raises:
        InfraReadError: the dump fails or does not print JSON.
    """
    data = _run_json(tool.argv("ansible-config", *CONFIG_DUMP_ARGS), root, "ansible-config dump")
    if not isinstance(data, list):
        raise InfraReadError(ERRORS.infra.read_not_json.format(command="ansible-config dump"))
    return parse_config_dump(data, root)


def inventory_argv(tool: AnsibleTool, sources: tuple[str, ...]) -> list[str]:
    """`ansible-inventory` with an `-i` for each inventory source, then `--list`."""
    options = [word for source in sources for word in ("-i", source)]
    return tool.argv("ansible-inventory", *options, *INVENTORY_LIST_ARGS)


def read_inventory(tool: AnsibleTool, root: Path, sources: tuple[str, ...]) -> AnsibleInventory:
    """The inventory of `sources`, paths relative to the checkout at `root`.

    Raises:
        InfraReadError: the listing fails or does not print a JSON mapping.
    """
    data = _run_json(inventory_argv(tool, sources), root, "ansible-inventory --list")
    if not isinstance(data, Mapping):
        raise InfraReadError(ERRORS.infra.read_not_json.format(command="ansible-inventory --list"))
    return parse_inventory(data)


def config_env(project: Path) -> dict[str, str]:
    """`ANSIBLE_CONFIG` of the repo's `ansible.cfg`, when it has one."""
    config = project / _ANSIBLE_CONFIG
    return {"ANSIBLE_CONFIG": str(config)} if config.is_file() else {}


def galaxy_argv(tool: AnsibleTool, requirements: Path, target: Path) -> list[str]:
    """`ansible-galaxy collection install` of a requirements file into `target`."""
    return tool.argv(
        "ansible-galaxy", "collection", "install", "-r", str(requirements), "-p", str(target)
    )


def install_requirements(
    tool: AnsibleTool, project: Path, target: Path, requirements: Path | None = None
) -> None:
    """Install the collections of the requirements file of the repo in `project` into the
    folder `target`, with the repo's `ansible.cfg`.

    Raises:
        InfraReadError: the install fails.
    """
    req_file = requirements if requirements is not None else project / REQUIREMENTS_FILE
    result = run_subprocess(
        galaxy_argv(tool, req_file, target),
        cwd=project,
        env=config_env(project),
        quiet=True,
        timeout=DEFAULT_INFRA_GALAXY_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        raise InfraReadError(
            ERRORS.infra.read_failed.format(
                command=_GALAXY_INSTALL,
                code=result.returncode,
                detail=_last_line(result.stderr or result.stdout),
            )
        )


def role_list_argv(tool: AnsibleTool) -> list[str]:
    """`ansible-doc -t role -l -j`: the roles that Ansible finds, as JSON."""
    return tool.argv(DOC_COMMAND, *ROLE_LIST_ARGS)


def read_collection_roles(tool: AnsibleTool, project: Path, collections: Path) -> tuple[str, ...]:
    """The roles of the collections in the folder `collections`, sorted, each by its full name, as
    `ansible-doc -t role -l -j` lists them in the repo at `project`.

    Raises:
        InfraReadError: the listing fails or does not print a JSON mapping.
    """
    command = " ".join((DOC_COMMAND, *ROLE_LIST_ARGS))
    env = config_env(project) | {
        _COLLECTIONS_PATH_ENV: str(collections),
        _SCAN_SYS_PATH_ENV: str(False),
    }
    data = _run_json(role_list_argv(tool), project, command, env=env)
    if not isinstance(data, Mapping):
        raise InfraReadError(ERRORS.infra.read_not_json.format(command=command))
    return tuple(
        sorted(
            name
            for name, role in data.items()
            if isinstance(role, Mapping) and _COLLECTION_KEY in role
        )
    )


def _last_line(text: str) -> str:
    """The last line of `text` that holds a character, with each secret in it masked."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return mask_secrets(lines[-1]) if lines else ""


def _run_json(
    argv: list[str], root: Path, command: str, *, env: dict[str, str] | None = None
) -> Any:
    """Run `argv` in `root`, with `env` added to the environment of the child, and parse what it
    prints as JSON. `command` names it in an error."""
    result = run_subprocess(
        argv, cwd=root, env=env, quiet=True, timeout=DEFAULT_INFRA_ANSIBLE_READ_TIMEOUT_SECONDS
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()[-1:] or [""]
        raise InfraReadError(
            ERRORS.infra.read_failed.format(
                command=command, code=result.returncode, detail=detail[0]
            )
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise InfraReadError(ERRORS.infra.read_not_json.format(command=command)) from exc


def parse_config_dump(data: list[Any], root: Path) -> AnsibleConfig:
    """The config file and the host key settings of an `ansible-config dump --format json
    --only-changed` list. A setting that the dump leaves out has its default: host key checks on.
    The project profile, not the dump, gives the layout of the repo."""
    base = {item["name"]: item for item in data if isinstance(item, Mapping) and "name" in item}
    ssh = dict(_ssh_plugin_settings(data))
    config_file = base.get("CONFIG_FILE", {}).get("value")
    findings: list[str] = []
    for setting in (base.get("HOST_KEY_CHECKING"), ssh.get("host_key_checking")):
        if setting is not None and is_ansible_false(setting["value"]):
            findings.append(f"{_origin(setting, root)}: host_key_checking = False")
    for name in _SSH_OPTION_SETTINGS:
        setting = ssh.get(name)
        if setting is not None:
            origin = _origin(setting, root)
            findings.extend(
                f"{origin}: {name} {option}" for option in ssh_options_off(setting["value"])
            )
    return AnsibleConfig(
        config_file=Path(config_file) if config_file else None,
        host_key_checks_off=tuple(dict.fromkeys(findings)),
    )


def _ssh_plugin_settings(data: list[Any]) -> Iterator[tuple[str, Mapping[str, Any]]]:
    """Each changed setting of the `ssh` connection plugin, by its name."""
    for item in data:
        if not isinstance(item, Mapping) or "CONNECTION_PLUGINS" not in item:
            continue
        for plugin in item["CONNECTION_PLUGINS"]:
            for setting in plugin.get("ssh", ()):
                yield setting["name"], setting


def _origin(setting: Mapping[str, Any], root: Path) -> str:
    """Where a setting comes from: a file relative to `root`, or the origin that Ansible names."""
    origin = str(setting.get("origin") or "")
    path = Path(origin)
    return (
        str(path.relative_to(root)) if path.is_absolute() and path.is_relative_to(root) else origin
    )


def is_ansible_false(value: Any) -> bool:
    """Whether Ansible reads `value` as false."""
    return value is False or str(value).strip().lower() in _ANSIBLE_FALSE


def ssh_options_off(text: str) -> tuple[str, ...]:
    """The OpenSSH options in `text` that turn host key checks off, as written."""
    try:
        words = shlex.split(text)
    except ValueError:
        words = text.split()
    found: list[str] = []
    for spec in _option_specs(words):
        key, value = _split_option(spec)
        off = (key.lower() == _STRICT_HOST_KEY_CHECKING and value.lower() in _STRICT_OFF) or (
            key.lower() == _USER_KNOWN_HOSTS_FILE and tuple(value.split()) == _NO_KNOWN_HOSTS
        )
        if off:
            found.append(f"{key}={value}")
    return tuple(found)


def _option_specs(words: list[str]) -> Iterator[str]:
    """The argument of each `-o` option of an ssh command line."""
    pending = False
    for word in words:
        if pending:
            pending = False
            yield word
        elif word == "-o":
            pending = True
        elif word.startswith("-o"):
            yield word[2:]


def _split_option(spec: str) -> tuple[str, str]:
    """An OpenSSH option `Key=Value` or `Key Value` as its key and its value."""
    key, _, value = spec.strip().replace("=", " ", 1).partition(" ")
    return key, value.strip()


def parse_inventory(data: Mapping[str, Any]) -> AnsibleInventory:
    """The groups, with the hosts of their child groups, and the raw host variables of an
    `ansible-inventory --list` mapping."""
    hostvars: dict[str, dict[str, Any]] = dict(data.get("_meta", {}).get("hostvars", {}))
    names = [name for name in data if name != "_meta"]
    for name in names:
        hostvars.update({host: hostvars.get(host, {}) for host in data[name].get("hosts", ())})
    groups = {
        name: tuple(sorted(_members(data, name, set())))
        for name in sorted(names)
        if name not in _IMPLICIT_GROUPS
    }
    return AnsibleInventory(groups=groups, hostvars=hostvars)


def _members(data: Mapping[str, Any], group: str, seen: set[str]) -> set[str]:
    """The hosts of `group` and of each group under it."""
    if group in seen:
        return set()
    seen.add(group)
    entry = data.get(group, {})
    hosts = set(entry.get("hosts", ()))
    for child in entry.get("children", ()):
        hosts |= _members(data, child, seen)
    return hosts


def inventory_host_key_checks_off(inventory: AnsibleInventory) -> tuple[str, ...]:
    """Each host variable that turns host key checks off, with the count of hosts that set it. A
    templated value is not read."""
    counts: Counter[str] = Counter()
    for variables in inventory.hostvars.values():
        counts.update(_host_findings(variables))
    return tuple(
        f"inventory: {finding} ({count} host{'s' if count != 1 else ''})"
        for finding, count in sorted(counts.items())
    )


def _host_findings(variables: Mapping[str, Any]) -> set[str]:
    """The settings of one host that turn host key checks off."""
    found: set[str] = set()
    for name in _HOST_KEY_VARIABLES:
        if name in variables and is_ansible_false(variables[name]):
            found.add(f"{name} = False")
    for name in _SSH_OPTION_VARIABLES:
        value = variables.get(name)
        if isinstance(value, str) and _TEMPLATE_START not in value:
            found.update(f"{name} {option}" for option in ssh_options_off(value))
    return found


def is_template(value: Any) -> bool:
    """Whether a raw inventory value is a Jinja template, which only Ansible renders."""
    return isinstance(value, str) and _TEMPLATE_START in value


__all__ = [
    "CONFIG_DUMP_ARGS",
    "DOC_COMMAND",
    "INVENTORY_LIST_ARGS",
    "REQUIREMENTS_FILE",
    "ROLE_LIST_ARGS",
    "AnsibleConfig",
    "AnsibleInventory",
    "AnsibleTool",
    "ansible_tool",
    "config_env",
    "galaxy_argv",
    "install_requirements",
    "inventory_argv",
    "inventory_host_key_checks_off",
    "is_ansible_false",
    "is_template",
    "parse_config_dump",
    "parse_inventory",
    "read_collection_roles",
    "read_config",
    "read_inventory",
    "role_list_argv",
    "ssh_options_off",
]
