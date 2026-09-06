"""Test suite for declarative build_structured_table output builder."""

from __future__ import annotations

from rich.table import Table

from devops_cli.output.table_builder import build_structured_table


def test_build_structured_table_rich_output() -> None:
    """build_structured_table creates a properly configured Rich Table object."""
    cols = ["Name", "Status", "Age"]
    rows = [["app-1", "Running", "2d"], ["app-2", "Pending", "5m"]]

    table = build_structured_table(title="Applications", columns=cols, rows=rows)
    assert isinstance(table, Table)
    assert table.title == "Applications"
    assert len(table.columns) == 3


def test_build_structured_table_json_serialization() -> None:
    """When output_format is 'json', build_structured_table returns structured list of dictionaries."""
    cols = ["Service", "Port", "Protocol"]
    rows = [["vault", "8200", "tcp"], ["argo", "8080", "tcp"]]

    data = build_structured_table(title="Services", columns=cols, rows=rows, output_format="json")
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0] == {"service": "vault", "port": "8200", "protocol": "tcp"}
    assert data[1] == {"service": "argo", "port": "8080", "protocol": "tcp"}


def test_build_structured_table_empty_state() -> None:
    """When rows are empty, build_structured_table handles empty state gracefully."""
    cols = ["Item", "Count"]
    table = build_structured_table(
        title="Inventory", columns=cols, rows=[], empty_message="No items found."
    )
    assert isinstance(table, Table)
    assert len(table.rows) == 1  # Contains empty message placeholder row


def test_build_structured_table_column_formatting() -> None:
    """Supports column tuples specifying (header, style)."""
    cols = [("Pod", "cyan"), ("Restarts", "bold red")]
    rows = [["backend-pod", "3"]]

    table = build_structured_table(title="Pods", columns=cols, rows=rows)
    assert isinstance(table, Table)
    assert table.columns[0].style == "cyan"
    assert table.columns[1].style == "bold red"
