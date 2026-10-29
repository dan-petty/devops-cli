"""How network references are merged, ordered and located in a report."""

from __future__ import annotations

from devops_cli.models.vulnerability import DependencySpec, NetworkReference
from devops_cli.output.formatters.tables import format_network_references_table
from devops_cli.security.reference_extractor import (
    deduplicate_network_references,
    sort_network_references,
)


def test_a_dependency_location_is_its_file_and_line_and_line_one_without_one() -> None:
    """A dependency without a line number is located at line 1 of its file."""
    with_line = DependencySpec(
        name="pydantic", version_range=">=2.10.0", source_file="pyproject.toml", line_number=42
    )
    without_line = DependencySpec(name="pytest", source_file="requirements.txt")

    assert (with_line.location, without_line.location) == (
        "pyproject.toml:42",
        "requirements.txt:1",
    )


def test_a_network_reference_location_is_its_file_and_line() -> None:
    """A reference is located at `<file>:<line>`."""
    reference = NetworkReference(
        target="https://example.com",
        reference_type="url",
        source_file="src/client.py",
        line_number=88,
    )

    assert reference.location == "src/client.py:88"


def test_deduplicate_network_references() -> None:
    """Duplicate references are merged and their locations consolidated."""
    ref1 = NetworkReference(
        target="http://example.com:8080",
        reference_type="url",
        source_file="src/devops_cli/config/defaults.py",
        line_number=125,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )
    ref2 = NetworkReference(
        target="http://example.com:8080",
        reference_type="url",
        source_file="src/devops_cli/config/defaults.py",
        line_number=324,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )
    ref3 = NetworkReference(
        target="https://api.github.com",
        reference_type="url",
        source_file="src/devops_cli/github/client.py",
        line_number=45,
        security_status="✓ Safe",
        is_local=False,
        scope="external",
    )
    deduped = deduplicate_network_references([ref1, ref2, ref3])
    merged = next(r for r in deduped if r.target == "http://example.com:8080")

    assert (len(deduped), "125" in merged.location, "324" in merged.location) == (2, True, True)


def test_sort_network_references_ordered() -> None:
    """Audit results are sorted by scope (external, then local), security (most severe first),
    type (url, then ip), target and location."""
    ext_flagged = NetworkReference(
        target="https://malicious.example-bad.com",
        reference_type="url",
        source_file="src/bad.py",
        line_number=10,
        security_status="⚠️ Flagged (Malicious)",
        is_local=False,
        scope="external",
    )
    ext_safe_url = NetworkReference(
        target="https://api.vendor.com/v1",
        reference_type="url",
        source_file="src/api.py",
        line_number=20,
        security_status="✓ Safe",
        is_local=False,
        scope="external",
    )
    ext_safe_ip = NetworkReference(
        target="93.184.216.34",
        reference_type="ip",
        source_file="src/dns.py",
        line_number=5,
        security_status="✓ Safe",
        is_local=False,
        scope="external",
    )
    loc_url = NetworkReference(
        target="http://example.com:8080/argocd",
        reference_type="url",
        source_file="src/config.py",
        line_number=15,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )
    loc_ip = NetworkReference(
        target="192.168.49.2",
        reference_type="ip",
        source_file="src/k8s.py",
        line_number=30,
        security_status="✓ Safe / Low Risk",
        is_local=True,
        scope="local",
    )

    ordered = sort_network_references([loc_ip, ext_safe_url, loc_url, ext_safe_ip, ext_flagged])

    assert tuple(ordered) == (ext_flagged, ext_safe_url, ext_safe_ip, loc_url, loc_ip)


def _reference(target: str, status: str, line: int = 1) -> NetworkReference:
    return NetworkReference(
        target=target,
        reference_type="url",
        source_file="src/app.py",
        line_number=line,
        security_status=status,
    )


def test_an_unchecked_reference_sorts_before_a_safe_one() -> None:
    """A reference that no lookup checked sorts after the flagged ones and before every safe one."""
    safe_ports = _reference("https://d.example.net", "✓ Safe (Ports: 80)")
    low_risk = _reference("https://c.example.net", "✓ Safe / Low Risk")
    unchecked = _reference("https://b.example.net", "Unchecked")
    flagged = _reference("https://a.example.net", "⚠️ Flagged (Malware)")

    ordered = sort_network_references([safe_ports, low_risk, unchecked, flagged])

    assert [ref.security_status for ref in ordered] == [
        "⚠️ Flagged (Malware)",
        "Unchecked",
        "✓ Safe / Low Risk",
        "✓ Safe (Ports: 80)",
    ]


def test_an_unchecked_reference_is_not_hidden_by_a_safe_one_of_the_same_target() -> None:
    """Two references to one target keep the status that checked less, in either order."""
    safe = _reference("https://api.example.net/v1", "✓ Safe / Low Risk", line=3)
    unchecked = _reference("https://api.example.net/v1/", "Unchecked", line=9)

    statuses = [
        [ref.security_status for ref in deduplicate_network_references(refs)]
        for refs in ([safe, unchecked], [unchecked, safe])
    ]

    assert statuses == [["Unchecked"], ["Unchecked"]]


def test_the_network_table_colors_an_unchecked_reference_yellow() -> None:
    """An external reference that no lookup checked is not green, the color of a safe one."""
    table = format_network_references_table(
        [
            _reference("https://unchecked-corp.com", "Unchecked"),
            _reference("https://safe-corp.com", "✓ Safe (Ports: 80)"),
        ]
    )

    assert [(row[0], row[3]) for row in table.rows] == [
        ("https://unchecked-corp.com", "[yellow]Unchecked[/yellow]"),
        ("https://safe-corp.com", "[green]✓ Safe (Ports: 80)[/green]"),
    ]
