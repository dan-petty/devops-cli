"""Planned requests for Valkey commands in dry-run mode.

A dry run makes zero external requests and returns ordered PlannedRequest items (#412, #886).
"""

from __future__ import annotations

from devops_cli.dry_run.requests import PlannedRequest


def plan_valkey_ping() -> list[PlannedRequest]:
    """Generate planned requests for valkey ping."""
    return [PlannedRequest(method="valkey", target="PING")]


def plan_valkey_info(section: str | None = None) -> list[PlannedRequest]:
    """Generate planned requests for valkey info."""
    cmd = f"INFO {section}" if section else "INFO"
    return [PlannedRequest(method="valkey", target=cmd)]


def plan_valkey_stats() -> list[PlannedRequest]:
    """Generate planned requests for valkey stats."""
    return [
        PlannedRequest(method="valkey", target="INFO"),
        PlannedRequest(method="valkey", target="DBSIZE"),
    ]


def plan_valkey_keys(pattern: str = "*") -> list[PlannedRequest]:
    """Generate planned requests for valkey keys."""
    return [PlannedRequest(method="valkey", target=f"KEYS {pattern}")]


def plan_valkey_get(key: str) -> list[PlannedRequest]:
    """Generate planned requests for valkey get."""
    return [PlannedRequest(method="valkey", target=f"GET {key}")]


def plan_valkey_set(key: str, value: str, ex: int | None = None) -> list[PlannedRequest]:
    """Generate planned requests for valkey set."""
    cmd = f"SET {key} <value>"
    if ex is not None:
        cmd += f" EX {ex}"
    return [PlannedRequest(method="valkey", target=cmd)]


def plan_valkey_flush(all_databases: bool = False) -> list[PlannedRequest]:
    """Generate planned requests for valkey flush."""
    cmd = "FLUSHALL" if all_databases else "FLUSHDB"
    return [PlannedRequest(method="valkey", target=cmd)]


def plan_valkey_backup() -> list[PlannedRequest]:
    """Generate planned requests for valkey backup."""
    return [PlannedRequest(method="valkey", target="BGSAVE")]


def plan_valkey_cli(command_args: list[str] | None = None) -> list[PlannedRequest]:
    """Generate planned requests for valkey cli."""
    if not command_args:
        return [PlannedRequest(method="valkey", target="<command>")]
    cmd = command_args[0].upper()
    args_str = " ".join(command_args[1:])
    target = f"{cmd} {args_str}".strip()
    return [PlannedRequest(method="valkey", target=target)]
