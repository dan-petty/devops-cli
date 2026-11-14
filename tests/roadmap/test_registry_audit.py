"""The audit of the test registry declarations (#3332).

The audit reads the module-level `REGISTRY_COUNTS` declarations of a test tree with `ast` and
reports a declaration that is no plain literal and a ratchet assertion that no declaration of its
module covers. It imports no test module.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.support.paths import REPO_ROOT

if TYPE_CHECKING:
    from devops_cli.roadmap.registry_audit import RegistryAudit

# The modules of the repository that declare a registry entry (#3254).
_DECLARING_MODULES = (
    "tests/roadmap/test_roadmap_dry_runs.py",
    "tests/roadmap/test_roadmap_limit_classes.py",
    "tests/support/fakes/roadmap_store.py",
    "tests/telemetry/test_telemetry_instruments.py",
)


def _write(root: Path, name: str, text: str) -> None:
    """Write one module under the `tests` folder of `root`."""
    module = root / "tests" / name
    module.parent.mkdir(parents=True, exist_ok=True)
    module.write_text(text, encoding="utf-8")


def _audit(root: Path) -> RegistryAudit:
    """Audit the test tree of `root`. The import sits in this call, so a test fails in its call
    phase on the base commit, which holds no such module, rather than stopping the collection of
    the whole file (#3332)."""
    from devops_cli.roadmap.registry_audit import audit_registries

    return audit_registries(root)


def test_a_computed_declaration_is_reported_with_its_line(tmp_path: Path) -> None:
    """A value that calls a function is no plain literal, so the audit reports it and reads no
    entry from it."""
    _write(tmp_path, "test_computed.py", "REGISTRY_COUNTS = _entries()\n")

    audit = _audit(tmp_path)

    (declaration,) = audit.declarations
    assert declaration.path == "tests/test_computed.py"
    assert declaration.line == 1
    assert declaration.entries == ()
    (finding,) = audit.findings
    assert finding.kind == "invalid-declaration"
    assert finding.source == "tests/test_computed.py:1"


def test_an_entry_that_is_no_literal_triple_is_reported(tmp_path: Path) -> None:
    """An entry of two literals declares no kind, token and path, so the audit reports it."""
    _write(tmp_path, "test_short.py", 'REGISTRY_COUNTS = (("prefix", "CONST_"),)\n')

    audit = _audit(tmp_path)

    (declaration,) = audit.declarations
    assert declaration.entries == ()
    assert "no literal triple" in declaration.problem
    (finding,) = audit.findings
    assert finding.kind == "invalid-declaration"
    assert finding.source == "tests/test_short.py:1"


def test_a_declared_entry_is_listed_with_its_source(tmp_path: Path) -> None:
    """A declaration of literal triples gives one entry for each triple, with its own line."""
    _write(
        tmp_path,
        "test_declared.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_", "tests/test_x.py"),)\n',
    )

    audit = _audit(tmp_path)

    (entry,) = audit.entries
    assert (entry.kind, entry.token, entry.path) == ("prefix", "CONST_", "tests/test_x.py")
    assert entry.line == 1
    assert entry.declaring_path == "tests/test_declared.py"
    assert audit.findings == ()
    assert audit.ok


def test_a_prefix_entry_covers_the_length_of_its_family(tmp_path: Path) -> None:
    """A length assertion on a constant of a declared prefix is no finding."""
    _write(
        tmp_path,
        "test_prefix.py",
        "CONST_ROADMAP_LIMITS = (550, 75)\n"
        'REGISTRY_COUNTS = (("prefix", "CONST_ROADMAP_", "tests/test_prefix.py"),)\n'
        "\n"
        "\n"
        "def test_limits() -> None:\n"
        "    assert len(CONST_ROADMAP_LIMITS) == 2\n",
    )

    audit = _audit(tmp_path)

    assert audit.entries[0].token == "CONST_ROADMAP_"
    assert audit.findings == ()


def test_a_length_assertion_with_no_entry_is_reported_with_its_line(tmp_path: Path) -> None:
    """A length assertion on a module-level table that no entry covers is a warning."""
    _write(
        tmp_path,
        "test_table.py",
        'TABLE = ("a", "b", "c")\n\n\ndef test_table() -> None:\n    assert len(TABLE) == 3\n',
    )

    (finding,) = _audit(tmp_path).findings

    assert finding.kind == "length-assertion"
    assert finding.severity == "warning"
    assert finding.source == "tests/test_table.py:5"
    assert "TABLE" in finding.message


def test_a_local_list_is_not_a_ratchet(tmp_path: Path) -> None:
    """A name that the test function binds itself is no module-level table, so the audit reports
    nothing."""
    _write(
        tmp_path,
        "test_local.py",
        "def test_rows() -> None:\n    rows = [1, 2, 3]\n    assert len(rows) == 3\n",
    )

    audit = _audit(tmp_path)

    assert audit.findings == ()
    assert audit.ok


def test_a_limit_tuple_with_no_entry_is_reported_with_its_line(tmp_path: Path) -> None:
    """A tuple of upper-case names compared with a tuple of integers is a limit ratchet."""
    _write(
        tmp_path,
        "test_limits.py",
        "def test_limits() -> None:\n    assert (A, B, C, D) == (550, 75, 1100, 250)\n",
    )

    (finding,) = _audit(tmp_path).findings

    assert finding.kind == "limit-tuple"
    assert finding.source == "tests/test_limits.py:2"
    assert "A, B, C, D" in finding.message


def test_an_entry_covers_only_its_own_token(tmp_path: Path) -> None:
    """A `name` entry covers the name of its token and no other name of the tuple."""
    _write(
        tmp_path,
        "test_named.py",
        'REGISTRY_COUNTS = (("name", "A", "src/example.py"),)\n'
        "\n"
        "\n"
        "def test_limits() -> None:\n"
        "    assert (A, B) == (1, 2)\n",
    )

    (finding,) = _audit(tmp_path).findings

    assert finding.source == "tests/test_named.py:5"
    assert finding.message.endswith("of B has no REGISTRY_COUNTS entry")


def test_a_module_that_raises_at_import_is_still_read(tmp_path: Path) -> None:
    """The audit parses a module and imports none, so a module that raises at import is listed."""
    _write(
        tmp_path,
        "test_raising.py",
        'raise RuntimeError("no import")\n'
        'REGISTRY_COUNTS = (("name", "TOKEN", "src/example.py"),)\n',
    )

    audit = _audit(tmp_path)

    (declaration,) = audit.declarations
    assert declaration.source == "tests/test_raising.py:2"
    assert [entry.token for entry in audit.entries] == ["TOKEN"]
    assert audit.findings == ()


def test_the_repository_census() -> None:
    """Four modules of the repository declare the registry entries, and no declaration of another
    module is invalid. The test prints each ratchet finding, which the change records."""
    audit = _audit(REPO_ROOT)

    assert {declaration.path for declaration in audit.declarations} == set(_DECLARING_MODULES)
    assert len(audit.entries) == 7
    assert [finding for finding in audit.findings if finding.severity == "error"] == []
    for finding in audit.findings:
        print(f"{finding.severity} {finding.source} {finding.message}")
