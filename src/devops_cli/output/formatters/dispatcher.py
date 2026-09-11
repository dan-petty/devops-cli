"""Output format multiplexer and top-level serialization dispatcher."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rich.table import Table

from devops_cli.config.defaults import DEFAULT_FORMAT_TYPE
from devops_cli.output.formatters.scalars import format_json, format_yaml
from devops_cli.output.formatters.tables import render_table


def format_output(
    data: Any,
    format_type: str = DEFAULT_FORMAT_TYPE,
    *,
    title: str = "",
    columns: Sequence[Any] | None = None,
    rows: Sequence[Sequence[Any]] | None = None,
) -> str | Table:
    """Format output data into JSON, YAML, or Rich Table representation."""
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
