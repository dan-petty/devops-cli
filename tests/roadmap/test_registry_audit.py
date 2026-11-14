"""The registry audit of a test tree (#3332).

The command layer is tested in `tests/commands/test_roadmap_registries.py`.
"""

from __future__ import annotations

from pathlib import Path

from devops_cli.roadmap.registry_audit import audit_registries
from tests.support.paths import REPO_ROOT


def _write(root: Path, relative: str, text: str) -> Path:
    """Write one test module of a temporary tree and return its path."""
    module = root / "tests" / relative
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")
    return module


def test_a_computed_declaration_is_reported_with_its_line(tmp_path: Path) -> None:
    """A declaration whose value calls a function is invalid and lists no entry."""
    text = "def build() -> tuple:\n    return ()\n\nREGISTRY_COUNTS = build()\n"
    _write(tmp_path, "test_computed.py", text)

    audit = audit_registries(tmp_path)

    assert audit.entries == ()
    assert audit.declarations == 0
    assert [(item.severity, item.path, item.line) for item in audit.findings] == [
        ("error", "tests/test_computed.py", 4)
    ]


def test_a_valid_tree_lists_the_entries_of_each_declaration(tmp_path: Path) -> None:
    """A declaration of literal triples lists each entry with its line and its source."""
    text = (
        "REGISTRY_COUNTS = (\n"
        '    ("table", "WRITES", "tests/test_one.py"),\n'
        '    ("name", "stage_requests", "src/x.py"),\n'
        ")\n"
    )
    _write(tmp_path, "test_one.py", text)

    audit = audit_registries(tmp_path)

    assert audit.findings == ()
    assert audit.declarations == 1
    assert [(item.kind, item.token, item.path, item.line) for item in audit.entries] == [
        ("table", "WRITES", "tests/test_one.py", 2),
        ("name", "stage_requests", "src/x.py", 3),
    ]


def test_a_prefix_entry_covers_the_constants_of_its_family(tmp_path: Path) -> None:
    """A limit tuple of constants that a prefix entry covers reports nothing."""
    text = (
        'REGISTRY_COUNTS = (("prefix", "LIMIT_", "tests/test_prefix.py"),)\n'
        "LIMIT_A = 1\n"
        "LIMIT_B = 2\n"
        "\n"
        "\n"
        "def test_the_limits() -> None:\n"
        "    assert (LIMIT_A, LIMIT_B) == (1, 2)\n"
    )
    _write(tmp_path, "test_prefix.py", text)

    audit = audit_registries(tmp_path)

    assert audit.findings == ()
    assert audit.declarations == 1
    assert [item.token for item in audit.entries] == ["LIMIT_"]


def test_a_length_assertion_on_a_module_table_with_no_declaration_is_reported(
    tmp_path: Path,
) -> None:
    """A length ratchet on a module table that no entry covers reports its path and line."""
    text = (
        'TABLE = ("a", "b", "c")\n\n\ndef test_the_table() -> None:\n    assert len(TABLE) == 3\n'
    )
    _write(tmp_path, "test_table.py", text)

    audit = audit_registries(tmp_path)

    assert [(item.severity, item.path, item.line) for item in audit.findings] == [
        ("warning", "tests/test_table.py", 5)
    ]
    assert "TABLE" in audit.findings[0].message


def test_a_limit_tuple_with_no_declaration_is_reported(tmp_path: Path) -> None:
    """A tuple of upper-case names compared with plain integers reports the uncovered names."""
    text = "LIMIT_A = 1\nLIMIT_B = 2\n\n\ndef test_the_limits() -> None:\n    assert (LIMIT_A, LIMIT_B) == (1, 2)\n"
    _write(tmp_path, "test_limits.py", text)

    audit = audit_registries(tmp_path)

    assert [(item.severity, item.path, item.line) for item in audit.findings] == [
        ("warning", "tests/test_limits.py", 6)
    ]
    assert "LIMIT_A" in audit.findings[0].message
    assert "LIMIT_B" in audit.findings[0].message


def test_a_local_length_assertion_is_not_reported(tmp_path: Path) -> None:
    """A length assertion on a local variable of a test function is no ratchet."""
    text = "def test_rows() -> None:\n    rows = [1, 2, 3]\n    assert len(rows) == 3\n"
    _write(tmp_path, "test_local.py", text)

    audit = audit_registries(tmp_path)

    assert audit.findings == ()


def test_a_module_that_raises_at_import_is_still_read(tmp_path: Path) -> None:
    """The audit reads a module with ast: a module that fails at import still lists its entry."""
    text = (
        'REGISTRY_COUNTS = (("name", "stage_requests", "src/x.py"),)\n'
        "\n"
        'raise RuntimeError("the module fails at import")\n'
    )
    _write(tmp_path, "test_broken.py", text)

    audit = audit_registries(tmp_path)

    assert audit.findings == ()
    assert audit.declarations == 1
    assert [(item.kind, item.token, item.declaring_path, item.line) for item in audit.entries] == [
        ("name", "stage_requests", "tests/test_broken.py", 1)
    ]


def test_the_repository_census() -> None:
    """The repository holds the four declaring modules of #3254 and their seven entries. Each
    finding prints; an invalid declaration fails the census (#3332)."""
    audit = audit_registries(REPO_ROOT)

    for finding in audit.findings:
        print(f"{finding.severity} {finding.path}:{finding.line}: {finding.message}")

    assert [item for item in audit.findings if item.severity == "error"] == []
    assert sorted({item.declaring_path for item in audit.entries}) == [
        "tests/roadmap/test_roadmap_dry_runs.py",
        "tests/roadmap/test_roadmap_limit_classes.py",
        "tests/support/fakes/roadmap_store.py",
        "tests/telemetry/test_telemetry_instruments.py",
    ]
    assert (len(audit.entries), audit.declarations) == (7, 4)
