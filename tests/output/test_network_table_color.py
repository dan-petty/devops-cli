"""Tests for network reference table color formatting."""

import pytest

from devops_cli.models.vulnerability import NetworkReference
from devops_cli.output.formatters.tables import format_network_references_table

STATUS_CELLS = [
    ("✓ Safe / Low Risk", "[green]✓ Safe / Low Risk[/green]"),
    ("LOW CONFIDENCE RISK", "[green]LOW CONFIDENCE RISK[/green]"),
    ("✓ Safe (Local)", "[green]✓ Safe (Local)[/green]"),
    ("✓ Safe (Ports: 80)", "[green]✓ Safe (Ports: 80)[/green]"),
    ("✓ Safe (Documented Example)", "[green]✓ Safe (Documented Example)[/green]"),
    ("✓ Safe", "[green]✓ Safe[/green]"),
    ("Unchecked", "[yellow]Unchecked[/yellow]"),
    ("⚠️ Flagged (known botnet)", "[red]⚠️ Flagged (known botnet)[/red]"),
    ("⚠️ Low Risk", "[red]⚠️ Low Risk[/red]"),
    ("High Risk", "[red]High Risk[/red]"),
    ("MALICIOUS host", "[red]MALICIOUS host[/red]"),
]


@pytest.mark.parametrize(
    ("status", "expected_cell"), STATUS_CELLS, ids=[case[0] for case in STATUS_CELLS]
)
def test_the_network_table_colors_a_status_by_its_risk(status: str, expected_cell: str) -> None:
    """A status cell is green when safe, yellow when unchecked and red when flagged."""
    reference = NetworkReference(
        target="https://valid-target.com",
        reference_type="url",
        source_file="src/test.py",
        line_number=1,
        security_status=status,
    )

    table = format_network_references_table([reference])

    assert len(table.rows) == 1, f"No row returned for status '{status}'"
    assert table.rows[0][3] == expected_cell
