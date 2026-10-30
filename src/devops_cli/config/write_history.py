"""What a write of a config file leaves behind: a copy of the file it replaces and an audit record
of the change (#1921).

Before this module, a write of a config file kept nothing, so a setting that a write dropped was
lost, and nothing showed which command wrote the file. Now a write that changes the file first
copies the file beside itself. Then it appends a record to the audit log (`data.audit_log_path`)
that names the command and the dotted keys whose values changed in the file. The record holds no
value, so a secret never gets into it.
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
from collections.abc import Collection, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from devops_cli.config.constants import (
    CONST_AUDIT_ACTION_CONFIG_WRITE,
    CONST_CONFIG_BACKUP_INFIX,
    CONST_CONFIG_BACKUP_STAMP_FORMAT,
    CONST_CONFIG_BACKUPS_KEPT,
    CONST_CONFIG_REDACTED_VALUE,
)
from devops_cli.config.round_trip import KeyPath, changes, edit, leaves
from devops_cli.exceptions import ConfigurationError


def back_up(path: Path, redact: Collection[KeyPath] = ()) -> Path | None:
    """Copy `path` to `<name>.bak-<YYYYMMDD-HHMMSS>` beside it, with the time in UTC, and remove
    all but the newest `CONST_CONFIG_BACKUPS_KEPT` copies. Return the copy, or None when `path`
    does not exist yet.

    A copy made earlier in the same second stays as it is. It holds the older state, which is the
    state a person restores to undo the writes of that second.

    `redact` names the key paths of credentials that the write removes from the file (#2645).
    Each retained copy, the new one and the older ones, then shows the value of such a key as
    `CONST_CONFIG_REDACTED_VALUE`, so the removal of a credential leaves no copy that holds it.
    The rest of each copy stays as it is. A copy that cannot be read as YAML raises
    ConfigurationError, before the caller replaces the file.
    """
    if not path.is_file():
        return None
    stamp = datetime.now(UTC).strftime(CONST_CONFIG_BACKUP_STAMP_FORMAT)
    backup = path.with_name(f"{path.name}{CONST_CONFIG_BACKUP_INFIX}{stamp}")
    if not backup.exists():
        _copy(path, backup, redact)
    for stale in _copies(path)[:-CONST_CONFIG_BACKUPS_KEPT]:
        stale.unlink()
    if redact:
        for copy in _copies(path):
            _copy(copy, copy, redact)
    return backup


def _copy(source: Path, dest: Path, redact: Collection[KeyPath]) -> None:
    """Write `source` to `dest` with its mode, and with the values of the `redact` keys redacted.
    A `dest` that is `source` changes only when a key holds a value to redact, and never shows a
    half-written file."""
    if not redact:
        shutil.copy2(source, dest)
        return
    text = source.read_text(encoding="utf-8")
    redacted = _redact(text, redact, name=str(source))
    if redacted == text and dest == source:
        return
    partial = dest.with_name(f"{dest.name}.tmp")
    partial.write_text(redacted, encoding="utf-8")
    shutil.copystat(source, partial)
    os.replace(partial, dest)


def _redact(text: str, paths: Collection[KeyPath], *, name: str) -> str:
    """The YAML `text` with the value of each key path of `paths` replaced by
    `CONST_CONFIG_REDACTED_VALUE`, when `text` holds a value there that is not empty and is not
    the replacement. `name` names the file in the error for a text that is not YAML. The error
    does not quote the text, which can hold a credential."""
    try:
        held = leaves(_mapping(text.encode("utf-8")))
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"Cannot read {name}: it is not valid YAML ({type(exc).__name__})."
        ) from None
    hidden = {
        path: CONST_CONFIG_REDACTED_VALUE
        for path in paths
        if held.get(path) not in (None, "", CONST_CONFIG_REDACTED_VALUE)
    }
    return edit(text, hidden, name=name) if hidden else text


def credential_paths(
    content: bytes | None, under: KeyPath, credentials: Collection[str]
) -> list[KeyPath]:
    """The key paths of the credentials that the YAML `content` holds at `under` or below it. A
    credential is a dotted key of `credentials`, such as `ai.api_key`."""
    return [
        path
        for path in leaves(_mapping(content))
        if path[: len(under)] == under and ".".join(path) in credentials
    ]


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
    return sorted(".".join(path) for path in changes(before, after))


def record_write(path: Path, previous: bytes | None, content: bytes, backup: Path | None) -> None:
    """Append the write of `path` to the audit log: the command that made it, the file, its copy
    and the dotted names of the keys whose values changed from the `previous` content to the
    written `content`, never a value."""
    from devops_cli.core.audit import record_audit_event

    record_audit_event(
        _running_command(),
        details={
            "action": CONST_AUDIT_ACTION_CONFIG_WRITE,
            "path": str(path),
            "backup": str(backup) if backup is not None else None,
            "changed_keys": changed_keys(_mapping(previous), _mapping(content)),
        },
    )


def _mapping(content: bytes | None) -> Mapping[str, Any]:
    """The mapping that a config file holds, or an empty one for no file or no mapping."""
    loaded = yaml.safe_load(content) if content else None
    return loaded if isinstance(loaded, Mapping) else {}


def _running_command() -> str:
    """The command path of the command that runs, such as `devops config set`. It holds no
    argument, so a value typed on the command line, such as a credential, stays out of it.
    Outside a command, the name of the program. Typer runs commands on the click it vendors, so
    the context is that click's."""
    from typer._click.globals import get_current_context

    context = get_current_context(silent=True)
    return context.command_path if context is not None else Path(sys.argv[0]).name
