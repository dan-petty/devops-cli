"""The local Ansible facts of an infra repo: its effective config and its inventory (#5121).

devops runs the Ansible commands of the tool environment of `[python.ansible-core]` of the tools
lock as child processes in the root of the checkout. The child gets the environment of
`run_subprocess`, so no `ANSIBLE_` variable of the person reaches it, and the `ansible.cfg` of the
repo alone sets Ansible. Neither command connects to a host. An inventory script or plugin that the
repo names runs, as it does for each Ansible command in the repo.
"""

from __future__ import annotations

import json
import shlex
import shutil
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from devops_cli.config.defaults import DEFAULT_INFRA_ANSIBLE_READ_TIMEOUT_SECONDS
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.infra import InfraReadError
from devops_cli.lang import ERRORS
from devops_cli.tools_lock import PythonTool, installed_commands, load_tools_lock, tool_install_dir

ANSIBLE_TOOL: Final[str] = "ansible-core"
RUNNER_COMMAND: Final[str] = "ansible-runner"
CONFIG_DUMP_ARGS: Final[tuple[str, ...]] = ("dump", "--format", "json", "--only-changed")
INVENTORY_LIST_ARGS: Final[tuple[str, ...]] = ("--list",)
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
    """The Ansible tool environment: its `bin` folder, and the ansible-core version of its pin
    when it is the install of `devops install-tools`."""

    bin_dir: Path
    installed: bool
    version: str | None = None

    def argv(self, command: str, *args: str) -> list[str]:
        """The command line of `command` of the environment, with `args`."""
        return [str(self.bin_dir / command), *args]


def ansible_tool() -> AnsibleTool:
    """The Ansible tool environment: the pinned install of `devops install-tools` under the user
    data root, else the folder of the `ansible-runner` on PATH, such as the one of the devcontainer
    image. Only `ansible-runner` goes on PATH; the other commands are beside it."""
    tool = load_tools_lock().python[ANSIBLE_TOOL]
    bin_dir = tool_install_dir(ANSIBLE_TOOL, tool.version).joinpath(*PythonTool.command_dir)
    if all(path.is_file() for path in installed_commands(ANSIBLE_TOOL, tool).values()):
        return AnsibleTool(bin_dir=bin_dir, installed=True, version=tool.version)
    found = shutil.which(RUNNER_COMMAND)
    if found is not None:
        return AnsibleTool(bin_dir=Path(found).resolve().parent, installed=True)
    return AnsibleTool(bin_dir=bin_dir, installed=False)


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


def _run_json(argv: list[str], root: Path, command: str) -> Any:
    """Run `argv` in `root` and parse what it prints as JSON. `command` names it in an error."""
    result = run_subprocess(
        argv, cwd=root, quiet=True, timeout=DEFAULT_INFRA_ANSIBLE_READ_TIMEOUT_SECONDS
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
    "ANSIBLE_TOOL",
    "CONFIG_DUMP_ARGS",
    "INVENTORY_LIST_ARGS",
    "AnsibleConfig",
    "AnsibleInventory",
    "AnsibleTool",
    "ansible_tool",
    "inventory_argv",
    "inventory_host_key_checks_off",
    "is_ansible_false",
    "is_template",
    "parse_config_dump",
    "parse_inventory",
    "read_config",
    "read_inventory",
    "ssh_options_off",
]
