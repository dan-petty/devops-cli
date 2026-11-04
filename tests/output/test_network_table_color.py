"""Tests for network reference table color formatting."""

from devops_cli.models.vulnerability import NetworkReference
from devops_cli.output.formatters.tables import format_network_references_table


def test_network_table_colors() -> None:
    """Test that the network references table colors statuses correctly."""
    # Test cases with expected colors
    test_cases = [
        # Green statuses (safe)
        ("✓ Safe / Low Risk", "[green]✓ Safe / Low Risk[/green]"),
        ("LOW CONFIDENCE RISK", "[green]LOW CONFIDENCE RISK[/green]"),
        ("✓ Safe (Local)", "[green]✓ Safe (Local)[/green]"),
        ("✓ Safe (Ports: 80)", "[green]✓ Safe (Ports: 80)[/green]"),
        ("✓ Safe (Documented Example)", "[green]✓ Safe (Documented Example)[/green]"),
        ("✓ Safe", "[green]✓ Safe[/green]"),
        # Yellow status (unchecked)
        ("Unchecked", "[yellow]Unchecked[/yellow]"),
        # Red statuses (flagged)
        ("⚠️ Flagged (known botnet)", "[red]⚠️ Flagged (known botnet)[/red]"),
        ("⚠️ Low Risk", "[red]⚠️ Low Risk[/red]"),
        ("High Risk", "[red]High Risk[/red]"),
        ("MALICIOUS host", "[red]MALICIOUS host[/red]"),
    ]

    for status, expected_color in test_cases:
        # Create a NetworkReference with the specific status
        reference = NetworkReference(
            target="https://valid-target.com",
            reference_type="url",
            source_file="src/test.py",
            line_number=1,
            security_status=status,
        )

        # Format the table
        table = format_network_references_table([reference])

        # Check that the status cell has the expected color
        assert len(table.rows) > 0, f"No rows returned for status '{status}'"
        actual_color = table.rows[0][3]  # Status is in column 3
        assert actual_color == expected_color, (
            f"Expected {expected_color}, got {actual_color} for status '{status}'"
        )
