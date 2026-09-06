"""Declarative table builder consolidating Rich console and structured output."""

from __future__ import annotations

from collections.abc import Sequence

from rich.table import Table


def _normalize_col_name(col: str | tuple[str, str]) -> str:
    """Normalize column header into machine-readable dict key."""
    header = col[0] if isinstance(col, tuple) else col
    return header.strip().lower().replace(" ", "_").replace("-", "_")


def build_structured_table(
    title: str,
    columns: Sequence[str | tuple[str, str]],
    rows: Sequence[Sequence[str]],
    empty_message: str = "No records found.",
    output_format: str = "table",
) -> Table | list[dict[str, str]]:
    """Construct Rich Table or JSON list of dicts based on output_format."""
    if output_format.lower() == "json":
        dict_keys = [_normalize_col_name(c) for c in columns]
        results: list[dict[str, str]] = []
        for row in rows:
            record: dict[str, str] = {}
            for idx, key in enumerate(dict_keys):
                record[key] = str(row[idx]) if idx < len(row) else ""
            results.append(record)
        return results

    table = Table(title=title)
    for col in columns:
        if isinstance(col, tuple):
            table.add_column(col[0], style=col[1])
        else:
            table.add_column(col)

    if not rows:
        placeholder = [f"[italic]{empty_message}[/italic]"] + [""] * (len(columns) - 1)
        table.add_row(*placeholder)
        return table

    for row in rows:
        str_row = [str(cell) for cell in row]
        table.add_row(*str_row)

    return table
