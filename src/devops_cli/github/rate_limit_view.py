"""Formatting and parsing helpers for GitHub API rate limit display."""

from __future__ import annotations

import datetime
import json
import time
from typing import Any

from devops_cli.exceptions.git import GitHubOperationError


def format_reset_time(epoch_seconds: int | float) -> str:
    """Format an epoch timestamp into a human-readable UTC string and countdown."""
    now = time.time()
    diff = int(epoch_seconds - now)
    dt_str = datetime.datetime.fromtimestamp(epoch_seconds, datetime.UTC).strftime("%H:%M:%S UTC")
    if diff <= 0:
        return f"{dt_str} (ready)"
    mins, secs = divmod(diff, 60)
    return f"{dt_str} (in {mins}m {secs}s)"


def parse_rate_limit_payload(stdout: str) -> dict[str, Any]:
    """Parse and validate JSON payload from GitHub rate_limit API."""
    try:
        data = json.loads(stdout) if stdout.strip() else {}
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse rate limit response: {exc}") from exc

    if not isinstance(data, dict):
        raise GitHubOperationError("Invalid rate limit response: expected JSON object")

    resources = data.get("resources")
    if not isinstance(resources, dict):
        raise GitHubOperationError("Invalid rate limit response: missing 'resources' object")

    return data


def format_rate_limit_rows(resources: dict[str, Any]) -> list[list[str]]:
    """Format rate limit resources dictionary into display table rows."""
    rows: list[list[str]] = []
    for res_name, info in sorted(resources.items()):
        if not isinstance(info, dict):
            continue
        limit = str(info.get("limit", "-")) if info.get("limit") is not None else "-"
        used = str(info.get("used", "-")) if info.get("used") is not None else "-"
        remaining = str(info.get("remaining", "-")) if info.get("remaining") is not None else "-"
        reset_epoch = info.get("reset")
        reset_str = format_reset_time(float(reset_epoch)) if reset_epoch is not None else "-"
        rows.append([res_name, limit, used, remaining, reset_str])
    return rows
