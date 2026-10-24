"""The config writes that the audit log of a test's data directory records (#1921, #1999).

A save of the settings appends one record to the audit log for each write of a config file. The
record names the dotted keys whose values changed in the file and holds no value, so a test reads
from it the keys that a command wrote.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from devops_cli.config.constants import CONST_AUDIT_ACTION_CONFIG_WRITE


def config_writes(data_dir: Path) -> list[dict[str, Any]]:
    """The details of each config write that the audit log of `data_dir` holds, the oldest first."""
    log = data_dir / "logs" / "audit.jsonl"
    if not log.is_file():
        return []
    records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    details = [record.get("details") or {} for record in records]
    return [entry for entry in details if entry.get("action") == CONST_AUDIT_ACTION_CONFIG_WRITE]


def written_keys(data_dir: Path) -> list[list[str]]:
    """The dotted keys that each config write changed, the oldest write first."""
    return [write["changed_keys"] for write in config_writes(data_dir)]
