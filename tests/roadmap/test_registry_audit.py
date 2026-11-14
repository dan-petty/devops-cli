"""The registry audit of the test suite (#3332)."""

from __future__ import annotations

from pathlib import Path

from devops_cli.roadmap.registry_audit import (
    INVALID_DECLARATION,
    LENGTH_RATCHET,
    LIMIT_TUPLE,
    audit_registries,
)
from tests.support.paths import REPO_ROOT

# The four test modules that declare `REGISTRY_COUNTS` at this commit (#3254).
DECLARING_PATHS = frozenset(
    {
        "tests/roadmap/test_roadmap_dry_runs.py",
        "tests/roadmap/test_roadmap_limit_classes.py",
        "tests/support/fakes/roadmap_store.py",
        "tests/telemetry/test_telemetry_instruments.py",
    }
)


def _module(tmp_path: Path, name: str, text: str) -> None:
    module = tmp_path / "tests" / name
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")


def test_a_declared_entry_enters_the_audit(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_declared.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_", "tests/test_declared.py"),)\n',
    )

    audit = audit_registries(tmp_path)

    assert [
        (entry.kind, entry.token, entry.path, entry.declaring_path, entry.line)
        for entry in audit.entries
    ] == [("prefix", "CONST_", "tests/test_declared.py", "tests/test_declared.py", 1)]
    assert audit.valid_declarations == 1
    assert audit.ok


def test_a_computed_declaration_is_reported_with_its_line(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_computed.py",
        "def build() -> tuple[()]:\n    return ()\n\nREGISTRY_COUNTS = build()\n",
    )

    audit = audit_registries(tmp_path)

    assert audit.entries == ()
    (finding,) = audit.findings
    assert finding.kind == INVALID_DECLARATION
    assert (finding.path, finding.line) == ("tests/test_computed.py", 4)
    assert not audit.ok


def test_a_prefix_entry_covers_a_name_that_starts_with_its_token(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_prefix.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_", "tests/test_prefix.py"),)\n'
        'CONST_TABLE = ("a", "b", "c")\n'
        "\n"
        "def test_it() -> None:\n"
        "    assert len(CONST_TABLE) == 3\n",
    )

    audit = audit_registries(tmp_path)

    assert audit.findings == ()
    assert audit.ok


def test_a_length_assertion_with_no_entry_is_reported(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_length.py",
        'TABLE = ("a", "b", "c")\n\ndef test_it() -> None:\n    assert len(TABLE) == 3\n',
    )

    audit = audit_registries(tmp_path)

    (finding,) = audit.findings
    assert finding.kind == LENGTH_RATCHET
    assert (finding.path, finding.line) == ("tests/test_length.py", 4)
    assert "tests/test_length.py:4" in finding.message


def test_a_limit_tuple_with_no_entry_is_reported(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_limit.py",
        "A = 1\n"
        "B = 2\n"
        "C = 3\n"
        "D = 4\n"
        "\n"
        "def test_it() -> None:\n"
        "    assert (A, B, C, D) == (550, 75, 1100, 250)\n",
    )

    audit = audit_registries(tmp_path)

    (finding,) = audit.findings
    assert finding.kind == LIMIT_TUPLE
    assert (finding.path, finding.line) == ("tests/test_limit.py", 7)
    assert "tests/test_limit.py:7" in finding.message


def test_a_local_list_reports_nothing(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_local.py",
        "def test_it() -> None:\n    rows = [1, 2, 3]\n    assert len(rows) == 3\n",
    )

    audit = audit_registries(tmp_path)

    assert audit.findings == ()
    assert audit.ok


def test_a_module_that_raises_at_import_is_still_read(tmp_path: Path) -> None:
    _module(
        tmp_path,
        "test_raises.py",
        "raise RuntimeError('this module must not be imported')\n"
        "\n"
        'REGISTRY_COUNTS = (("table", "WRITES", "tests/test_raises.py"),)\n',
    )

    audit = audit_registries(tmp_path)

    assert [entry.token for entry in audit.entries] == ["WRITES"]
    assert audit.valid_declarations == 1


def test_the_repository_census(capsys) -> None:
    """The audit of this checkout lists the four declaring modules and their seven entries. A
    finding that is an invalid declaration, or that names a declaring module outside the four,
    stops the group."""
    audit = audit_registries(REPO_ROOT)

    for finding in audit.findings:
        print(finding.message)
    capsys.readouterr()

    declaring = {entry.declaring_path for entry in audit.entries}
    assert declaring == DECLARING_PATHS
    assert len(audit.entries) == 7
    assert audit.valid_declarations == 4
    assert [finding for finding in audit.findings if finding.kind == INVALID_DECLARATION] == []
    unexpected = [
        finding for finding in audit.findings if finding.path in declaring - DECLARING_PATHS
    ]
    assert unexpected == []
