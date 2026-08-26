"""Data output formatting, table rendering, and canonical location serialization."""

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
    DEFAULT_TABLE_BORDER_STYLE,
)

if TYPE_CHECKING:
    from rich.table import Table


def format_location(
    file_path: str | Path,
    start_line: int | None = None,
    end_line: int | None = None,
) -> str:
    """Format a source code or artifact location in canonical `filename.ext:n-n` syntax.

    Examples:
        format_location("src/main.py", 10, 20) -> "src/main.py:10-20"
        format_location("src/main.py", 15) -> "src/main.py:15"
        format_location("src/main.py") -> "src/main.py"
    """
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


def render_table(
    title: str | Any = "",
    columns: Sequence[Any] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
    *,
    border_style: str | None = DEFAULT_TABLE_BORDER_STYLE,
    box_style: Any = None,
) -> Table:
    """Construct a styled Rich Table from columns and rows or TablePayload.

    Args:
        title: Table header title or TablePayload model instance.
        columns: List of column names, TableColumn instances, or (name, style) tuples.
        rows: List of cell sequences.
        border_style: Rich border style.
        box_style: Rich box border style (e.g. None or box.ROUNDED).

    Returns:
        Configured Rich Table instance.
    """
    from rich.table import Table

    if hasattr(title, "render") and callable(getattr(title, "render")):
        rendered = title.render()
        if isinstance(rendered, Table):
            return rendered
    if hasattr(title, "to_table_payload") and callable(getattr(title, "to_table_payload")):
        payload = title.to_table_payload()
        if hasattr(payload, "render") and callable(getattr(payload, "render")):
            rendered = payload.render()
            if isinstance(rendered, Table):
                return rendered

    effective_title = str(getattr(title, "title", title)) if not isinstance(title, str) else title
    effective_cols = columns or getattr(title, "columns", None) or []
    effective_rows = rows or getattr(title, "rows", None) or []
    effective_border = getattr(title, "border_style", border_style)
    effective_box = getattr(title, "box_style", box_style)

    table = Table(
        title=effective_title,
        border_style=effective_border,
        box=effective_box,
        title_style="bold cyan",
        header_style="bold",
    )
    for col in effective_cols:
        if hasattr(col, "header"):
            # TableColumn Pydantic model
            table.add_column(
                col.header,
                style=col.style,
                justify=getattr(col, "justify", "left"),
                width=getattr(col, "width", None),
                no_wrap=getattr(col, "no_wrap", False),
            )
        elif isinstance(col, (tuple, list)):
            if len(col) >= 2:
                name, style = col[0], col[1]
                if isinstance(style, int):
                    table.add_column(str(name), width=style)
                elif str(style).lower() in ("left", "center", "right", "full"):
                    table.add_column(str(name), justify=str(style).lower())  # type: ignore[arg-type]
                else:
                    table.add_column(str(name), style=str(style))
            elif len(col) == 1:
                table.add_column(str(col[0]))
        else:
            table.add_column(str(col))

    for row in effective_rows:
        table.add_row(*[str(cell) for cell in row])

    return table


def format_status_badge(
    status: str | bool,
    *,
    label: str | None = None,
    ok_color: str = DEFAULT_BADGE_OK_COLOR,
    fail_color: str = DEFAULT_BADGE_FAIL_COLOR,
    warn_color: str = DEFAULT_BADGE_WARN_COLOR,
) -> str:
    """Format a styled Rich status badge string.

    Args:
        status: Boolean (True for success, False for fail) or status string ('ok', 'error', 'warn', etc.).
        label: Explicit display text. Defaults to status representation if None.
        ok_color: Color tag for success states (default: green).
        fail_color: Color tag for failure states (default: red).
        warn_color: Color tag for warning states (default: yellow).

    Returns:
        Rich markup formatted status badge string.
    """
    if isinstance(status, bool):
        color = ok_color if status else fail_color
        text = label if label is not None else ("Active" if status else "Disabled")
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


def format_severity(severity: str) -> str:
    """Format an issue or dependency vulnerability severity tag with standard colors."""
    sev_upper = severity.strip().upper()
    if sev_upper == "CRITICAL":
        return "[bold red]CRITICAL[/bold red]"
    if sev_upper == "HIGH":
        return "[red]HIGH[/red]"
    if sev_upper == "MEDIUM":
        return "[yellow]MEDIUM[/yellow]"
    if sev_upper == "LOW":
        return "[cyan]LOW[/cyan]"
    return f"[green]{sev_upper}[/green]"


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
    """Format output data into JSON, YAML, or Rich Table representation.

    Args:
        data: Raw data object, Pydantic model, or collection to format.
        format_type: Output format ('json', 'yaml', 'table', 'markdown').
        title: Table title (when format_type='table').
        columns: Table columns (when format_type='table').
        rows: Table rows (when format_type='table').

    Returns:
        Formatted string or Rich Table object.
    """
    from rich.table import Table

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
