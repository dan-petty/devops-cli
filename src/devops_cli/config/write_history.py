"""What a write of a config file leaves behind: a copy of the file it replaces and an audit record
of the change (#1921).

`save_settings` writes a whole config file from the settings in memory. Before this module, a
write kept nothing, so a setting that a write dropped was lost, and nothing showed which command
wrote the file. Now a write that changes the file first copies the file beside itself. Then it
appends a record to the audit log (`data.audit_log_path`) that names the command and the dotted
keys that changed. The record holds no value, so a secret never gets into it.
"""

from __future__ import annotations

import glob
import shutil
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_AUDIT_ACTION_CONFIG_WRITE,
    CONST_CONFIG_BACKUP_INFIX,
    CONST_CONFIG_BACKUP_STAMP_FORMAT,
    CONST_CONFIG_BACKUPS_KEPT,
)

_ABSENT = object()


def back_up(path: Path) -> Path | None:
    """Copy `path` to `<name>.bak-<YYYYMMDD-HHMMSS>` beside it, with the time in UTC, and remove
    all but the newest `CONST_CONFIG_BACKUPS_KEPT` copies. Return the copy, or None when `path`
    does not exist yet.

    A copy made earlier in the same second stays as it is. It holds the older state, which is the
    state a person restores to undo the writes of that second.
    """
    if not path.is_file():
        return None
    stamp = datetime.now(UTC).strftime(CONST_CONFIG_BACKUP_STAMP_FORMAT)
    backup = path.with_name(f"{path.name}{CONST_CONFIG_BACKUP_INFIX}{stamp}")
    if not backup.exists():
        shutil.copy2(path, backup)
    for stale in _copies(path)[:-CONST_CONFIG_BACKUPS_KEPT]:
        stale.unlink()
    return backup


def _copies(path: Path) -> list[Path]:
    """The copies `back_up` made of `path`, the oldest first. Another file whose name starts the
    same way, such as a copy a person made, is not one of them."""
    prefix = f"{path.name}{CONST_CONFIG_BACKUP_INFIX}"
    candidates = path.parent.glob(f"{glob.escape(prefix)}*")
    return sorted(c for c in candidates if _is_stamp(c.name.removeprefix(prefix)))


def _is_stamp(text: str) -> bool:
    """Report whether `text` is a time written in `CONST_CONFIG_BACKUP_STAMP_FORMAT`."""
    try:
        parsed = datetime.strptime(text, CONST_CONFIG_BACKUP_STAMP_FORMAT)
    except ValueError:
        return False
    return parsed.strftime(CONST_CONFIG_BACKUP_STAMP_FORMAT) == text


def changed_keys(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    """The dotted names, such as `ssh.key_prefix`, of the settings that differ between two config
    mappings: each leaf that only one of them holds, or that they hold with different values."""
    old, new = _leaves(before), _leaves(after)
    return sorted(k for k in old.keys() | new.keys() if old.get(k, _ABSENT) != new.get(k, _ABSENT))


def _leaves(mapping: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Each value of a nested mapping that is not itself a mapping with keys, by its dotted name."""
    leaves: dict[str, Any] = {}
    for key, value in mapping.items():
        name = f"{prefix}{key}"
        if isinstance(value, Mapping) and value:
            leaves |= _leaves(value, f"{name}.")
        else:
            leaves[name] = value
    return leaves


def record_write(
    path: Path, previous: bytes | None, written: Mapping[str, Any], backup: Path | None
) -> None:
    """Append the write of `path` to the audit log: the command that made it, the file, its copy
    and the dotted names of the keys that changed from the `previous` content, never a value."""
    from devops_cli.core.audit import record_audit_event

    before = yaml.safe_load(previous) if previous else None
    record_audit_event(
        _running_command(),
        details={
            "action": CONST_AUDIT_ACTION_CONFIG_WRITE,
            "path": str(path),
            "backup": str(backup) if backup is not None else None,
            "changed_keys": changed_keys(before if isinstance(before, Mapping) else {}, written),
        },
    )


def _running_command() -> str:
    """The command path of the command that runs, such as `devops config set`. It holds no
    argument, so a value typed on the command line, such as a credential, stays out of it.
    Outside a command, the name of the program. Typer runs commands on the click it vendors, so
    the context is that click's."""
    from typer._click.globals import get_current_context

    context = get_current_context(silent=True)
    return context.command_path if context is not None else Path(sys.argv[0]).name
