"""Declarative table builder consolidating Rich console and structured output."""

from __future__ import annotations

from collections.abc import Sequence

from rich.table import Table

from devops_cli.output.formatters.tables import render_table
from devops_cli.output.markup import escape_text


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

    if not rows:
        placeholder: list[list[str]] = [
            [f"[italic]{escape_text(empty_message)}[/italic]"] + [""] * (len(columns) - 1)
        ]
        return render_table(title=title, columns=columns, rows=placeholder, safe=False)

    return render_table(title=title, columns=columns, rows=rows, safe=True)
