"""Scalar, primitive, badge, link, duration, and serialization output formatters."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from devops_cli.config.defaults import (
    DEFAULT_BADGE_FAIL_COLOR,
    DEFAULT_BADGE_OK_COLOR,
    DEFAULT_BADGE_WARN_COLOR,
    DEFAULT_CODE_SPAN_COLOR,
    DEFAULT_FORMAT_TYPE,
    DEFAULT_JSON_INDENT,
)
from devops_cli.lang import MESSAGES

if TYPE_CHECKING:
    from rich.table import Table

SEV_COLOR_MAP: dict[str, str] = {
    "CRITICAL": "red",
    "HIGH": "orange3",
    "MEDIUM": "yellow",
    "LOW": "blue",
    "INFO": "green",
}

RECOMMENDATION_COLOR_MAP: dict[str, str] = {
    "APPROVE": "green",
    "REQUEST CHANGES": "yellow",
    "BLOCK": "red",
}


def format_location(
    file_path: str | Path,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Format a source code or artifact location in canonical `filename.ext:n-n` syntax."""
    path_str = str(file_path)
    if start_line is not None and end_line is not None and start_line != end_line:
        return f"{path_str}:{start_line}-{end_line}"
    if start_line is not None:
        return f"{path_str}:{start_line}"
    return path_str


def _prepare_serializable_data(data: Any) -> Any:
    """Normalize Pydantic models or collections of models for serialization."""
    if hasattr(data, "model_dump"):
        return data.model_dump()
    if isinstance(data, list):
        return [item.model_dump() if hasattr(item, "model_dump") else item for item in data]
    return data


def format_serialized(
    data: Any,
    format_type: str = DEFAULT_FORMAT_TYPE,
    *,
    indent: int = DEFAULT_JSON_INDENT,
) -> str:
    """Serialize any data structure or Pydantic model into formatted JSON or YAML."""
    prepared = _prepare_serializable_data(data)
    fmt = format_type.lower()
    if fmt in ("yaml", "yml"):
        import yaml

        return yaml.dump(prepared, sort_keys=False, default_flow_style=False)
    return json.dumps(prepared, indent=indent, default=str)


def format_json(data: Any, *, indent: int = DEFAULT_JSON_INDENT) -> str:
    """Serialize any data structure or Pydantic model into formatted JSON."""
    return format_serialized(data, format_type=DEFAULT_FORMAT_TYPE, indent=indent)


def format_yaml(data: Any) -> str:
    """Serialize any data structure or Pydantic model into formatted YAML."""
    return format_serialized(data, format_type="yaml")


def format_status_badge(
    status: str | bool,
    *,
    label: str | None = None,
    ok_color: str = DEFAULT_BADGE_OK_COLOR,
    fail_color: str = DEFAULT_BADGE_FAIL_COLOR,
    warn_color: str = DEFAULT_BADGE_WARN_COLOR,
) -> str:
    """Format a styled Rich status badge string."""
    if isinstance(status, bool):
        color = ok_color if status else fail_color
        text = (
            label
            if label is not None
            else (MESSAGES.badges.active if status else MESSAGES.badges.disabled)
        )
        return f"[{color}]{text}[/{color}]"

    norm = str(status).strip().lower()
    if norm in (
        "ok",
        "true",
        "active",
        "healthy",
        "pass",
        "passed",
        "connected",
        "clean",
        "approve",
    ):
        color = ok_color
    elif norm in ("warn", "warning", "mitigated", "request changes"):
        color = warn_color
    else:
        color = fail_color

    text = label if label is not None else str(status)
    return f"[{color}]{text}[/{color}]"


def format_link(url: str, text: str | None = None) -> str:
    """Format a clickable terminal hyperlink in Rich markup syntax."""
    display = text or url
    return f"[link={url}]{display}[/link]"


def format_duration(seconds: float) -> str:
    """Format a time duration in seconds or milliseconds."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.0f}µs"
    if seconds < 1.0:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.2f}s"


def format_latency(ms: float) -> str:
    """Format a network or span latency in milliseconds."""
    return f"{ms:.1f}ms"


def format_bytes(raw: int | float | None) -> str:
    """Format raw byte counts into a concise human-readable unit string (B, KB, MB, GB, TB)."""
    n: float = float(raw or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def format_timestamp_age(created_at: str) -> str:
    """Convert an ISO-8601 creation timestamp to a concise human-readable age string."""
    import datetime

    try:
        created = datetime.datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.datetime.now(datetime.UTC)
        delta = now - created
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        if delta.days > 0:
            return f"{delta.days}d{hours}h"
        if hours > 0:
            return f"{hours}h{minutes}m"
        if minutes > 0:
            return f"{minutes}m{seconds}s"
        return f"{seconds}s"
    except Exception:
        return "—"


_SEV_MARKUP_MAP: dict[str, str] = {
    MESSAGES.badges.sev_critical: f"[bold red]{MESSAGES.badges.sev_critical}[/bold red]",
    MESSAGES.badges.sev_high: f"[red]{MESSAGES.badges.sev_high}[/red]",
    MESSAGES.badges.sev_medium: f"[yellow]{MESSAGES.badges.sev_medium}[/yellow]",
    MESSAGES.badges.sev_low: f"[cyan]{MESSAGES.badges.sev_low}[/cyan]",
}

_FINDING_STATUS_MARKUP_MAP: dict[str, str] = {
    "VERIFIED": f"[green]{MESSAGES.badges.verified}[/green]",
    "MITIGATED": f"[cyan]{MESSAGES.badges.mitigated}[/cyan]",
    "FLAGGED": f"[yellow]{MESSAGES.badges.flagged}[/yellow]",
    "INVALIDATED": f"[red]{MESSAGES.badges.invalidated}[/red]",
}


def format_severity(severity: str) -> str:
    """Format an issue or dependency vulnerability severity tag with standard colors."""
    sev_upper = severity.strip().upper()
    return _SEV_MARKUP_MAP.get(sev_upper, f"[green]{sev_upper}[/green]")


def format_finding_status_badge(
    status: str, verified: bool = False, mitigated: bool = False
) -> str:
    """Format finding verification status badge with consistent color styles."""
    norm = status.strip().upper()
    if mitigated:
        return _FINDING_STATUS_MARKUP_MAP["MITIGATED"]
    if verified and norm != "MITIGATED":
        return _FINDING_STATUS_MARKUP_MAP["VERIFIED"]
    return _FINDING_STATUS_MARKUP_MAP.get(norm, f"[dim]{MESSAGES.badges.unverified}[/dim]")


def format_review_recommendation(recommendation: str) -> str:
    """Format persona review recommendation verdict badge."""
    rec_upper = recommendation.strip().upper()
    color = RECOMMENDATION_COLOR_MAP.get(rec_upper, "white")
    return f"[{color} bold]{rec_upper}[/{color} bold]"


def format_code_span(text: str, color: str = DEFAULT_CODE_SPAN_COLOR) -> str:
    """Format a snippet of code or identifier in Rich styled markup."""
    return f"[{color}]{text}[/{color}]"


def format_key_value_pairs(
    items: dict[str, Any] | Sequence[tuple[str, Any]],
) -> list[list[str]]:
    """Convert a dictionary or sequence of key-value pairs into formatted table rows."""
    pairs = items.items() if isinstance(items, dict) else items
    return [[str(k), str(v)] for k, v in pairs]


def format_output(
    data: Any,
    format_type: str = DEFAULT_FORMAT_TYPE,
    *,
    title: str = "",
    columns: Sequence[Any] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
) -> str | Table:
    """Format output data into JSON, YAML, or Rich Table representation."""
    from rich.table import Table

    from devops_cli.output.formatters.tables import render_table

    fmt = format_type.lower()
    if fmt == "json":
        return format_json(data)
    if fmt in ("yaml", "yml"):
        return format_yaml(data)
    if fmt == "table":
        if hasattr(data, "render") and callable(getattr(data, "render")):
            rendered = data.render()
            if isinstance(rendered, Table):
                return rendered
        if hasattr(data, "to_table_payload") and callable(getattr(data, "to_table_payload")):
            payload = data.to_table_payload()
            if hasattr(payload, "render") and callable(getattr(payload, "render")):
                rendered = payload.render()
                if isinstance(rendered, Table):
                    return rendered
        if isinstance(data, list) and data and hasattr(data[0], "model_dump"):
            field_keys = (
                list(type(data[0]).model_fields.keys())
                if hasattr(type(data[0]), "model_fields")
                else list(getattr(data[0], "__dict__", {}).keys())
            )
            auto_cols = [k.replace("_", " ").title() for k in field_keys]
            auto_rows = [[str(getattr(item, k, "")) for k in field_keys] for item in data]
            return render_table(title=title, columns=columns or auto_cols, rows=rows or auto_rows)
        return render_table(title, columns or [], rows or [])
    return format_json(data)


def format_repo_map_text(file_nodes: list[Any]) -> str:
    """Render repository symbol map as clean, indented ASCII text."""
    lines: list[str] = []
    for f in file_nodes:
        path_str = getattr(f, "path", str(f))
        line_count = getattr(f, "line_count", 0)
        lines.append(f"{path_str} ({line_count} lines):")
        symbols = getattr(f, "symbols", [])
        for sym in symbols:
            kind = getattr(sym, "kind", "")
            name = getattr(sym, "name", "")
            docstring = getattr(sym, "docstring", None)
            signature = getattr(sym, "signature", "")
            if kind == "class":
                lines.append(f"  class {name}:")
                if docstring:
                    lines.append(f"    # {docstring}")
                children = getattr(sym, "children", [])
                for m in children:
                    m_name = getattr(m, "name", "")
                    m_sig = getattr(m, "signature", "")
                    lines.append(f"    def {m_name}{m_sig}")
            elif kind == "function":
                lines.append(f"  def {name}{signature}")
                if docstring:
                    lines.append(f"    # {docstring}")
        lines.append("")
    return "\n".join(lines).strip()
