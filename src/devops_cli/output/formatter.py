"""Data output formatting, table rendering, and canonical location serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
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
    format_type: str = "json",
    *,
    indent: int = 2,
) -> str:
    """Serialize any data structure or Pydantic model into formatted JSON or YAML."""
    prepared = _prepare_serializable_data(data)
    fmt = format_type.lower()
    if fmt in ("yaml", "yml"):
        return yaml.dump(prepared, sort_keys=False, default_flow_style=False)
    return json.dumps(prepared, indent=indent, default=str)


def format_json(data: Any, *, indent: int = 2) -> str:
    """Serialize any data structure or Pydantic model into formatted JSON."""
    return format_serialized(data, format_type="json", indent=indent)


def format_yaml(data: Any) -> str:
    """Serialize any data structure or Pydantic model into formatted YAML."""
    return format_serialized(data, format_type="yaml")


def render_table(
    title: str,
    columns: list[str | tuple[str, str]],
    rows: list[list[str]],
    *,
    border_style: str = "dim",
) -> Table:
    """Construct a styled Rich Table from columns and rows.

    Args:
        title: Table header title.
        columns: List of column names or (name, style) tuples.
        rows: List of string rows.
        border_style: Rich border style.

    Returns:
        Configured Rich Table instance.
    """
    table = Table(title=title, border_style=border_style)
    for col in columns:
        if isinstance(col, tuple):
            name, style = col
            table.add_column(name, style=style)
        else:
            table.add_column(col)

    for row in rows:
        table.add_row(*row)

    return table


def format_output(
    data: Any,
    format_type: str = "json",
    *,
    title: str = "",
    columns: list[str | tuple[str, str]] | None = None,
    rows: list[list[str]] | None = None,
) -> str | Table:
    """Format output data into JSON, YAML, or Rich Table representation.

    Args:
        data: Raw data object to format.
        format_type: Output format ('json', 'yaml', 'table', 'markdown').
        title: Table title (when format_type='table').
        columns: Table columns (when format_type='table').
        rows: Table rows (when format_type='table').

    Returns:
        Formatted string or Rich Table object.
    """
    fmt = format_type.lower()
    if fmt == "json":
        return format_json(data)
    if fmt in ("yaml", "yml"):
        return format_yaml(data)
    if fmt == "table" and columns and rows:
        return render_table(title, columns, rows)
    return format_json(data)
