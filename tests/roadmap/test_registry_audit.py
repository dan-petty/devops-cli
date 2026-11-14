"""The audit of the test registry declarations of a tree (#3332): the rules behind
`devops roadmap registries`. The command layer is tested in `tests/commands/`."""

from __future__ import annotations

from pathlib import Path

from devops_cli.roadmap.registry_audit import (
    KIND_INVALID_DECLARATION,
    KIND_MISSING_DECLARATION,
    audit_registries,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

_DRY_RUNS = "tests/roadmap/test_roadmap_dry_runs.py"
_LIMIT_CLASSES = "tests/roadmap/test_roadmap_limit_classes.py"
_FAKE_STORE = "tests/support/fakes/roadmap_store.py"
_INSTRUMENTS = "tests/telemetry/test_telemetry_instruments.py"
_DECLARING = [_DRY_RUNS, _LIMIT_CLASSES, _FAKE_STORE, _INSTRUMENTS]


def _write_module(root: Path, name: str, source: str) -> Path:
    """One module of the tree under audit: `<root>/tests/<name>`."""
    tests_dir = root / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    path = tests_dir / name
    path.write_text(source, encoding="utf-8")
    return path


def test_a_computed_declaration_is_reported_with_its_line(tmp_path: Path) -> None:
    """A `REGISTRY_COUNTS` whose value calls a function is reported with its `path:line`, and it
    contributes no entry."""
    _write_module(tmp_path, "test_computed.py", "REGISTRY_COUNTS = build()\n")

    audit = audit_registries(tmp_path)

    assert audit.entries == ()
    assert [(f.kind, f.path, f.line) for f in audit.findings] == [
        (KIND_INVALID_DECLARATION, "tests/test_computed.py", 1)
    ]


def test_a_plain_declaration_returns_its_entries(tmp_path: Path) -> None:
    """A tuple of literal triples is valid and gives its entries with the declaring `path:line`."""
    _write_module(
        tmp_path,
        "test_plain.py",
        'REGISTRY_COUNTS = (("name", "stage_requests", "src/x.py"),)\n',
    )

    audit = audit_registries(tmp_path)

    assert [(e.kind, e.token, e.path, e.declaring_path, e.line) for e in audit.entries] == [
        ("name", "stage_requests", "src/x.py", "tests/test_plain.py", 1)
    ]
    assert audit.findings == ()


def test_a_prefix_entry_covers_its_family(tmp_path: Path) -> None:
    """A length assertion on a name that a `prefix` entry of the same module covers is no
    finding."""
    _write_module(
        tmp_path,
        "test_prefix.py",
        'REGISTRY_COUNTS = (("prefix", "CONST_ROADMAP_", "src/x.py"),)\n'
        "assert len(CONST_ROADMAP_LIMIT) == 3\n",
    )

    audit = audit_registries(tmp_path)

    assert audit.findings == ()


def test_a_length_assertion_without_a_declaration_is_reported(tmp_path: Path) -> None:
    """A `len(<NAME>) == <int>` assertion on a module table with no entry naming it is reported
    with its `path:line`."""
    _write_module(
        tmp_path,
        "test_ratchet.py",
        'TABLE = ("a", "b", "c")\nassert len(TABLE) == 3\n',
    )

    audit = audit_registries(tmp_path)

    assert [(f.kind, f.path, f.line) for f in audit.findings] == [
        (KIND_MISSING_DECLARATION, "tests/test_ratchet.py", 2)
    ]


def test_a_limit_tuple_without_a_declaration_is_reported(tmp_path: Path) -> None:
    """A tuple of upper-case names compared with plain integers with no entry for those names is
    reported with its `path:line`."""
    _write_module(
        tmp_path,
        "test_tuple.py",
        "A = 1\nB = 2\nassert (A, B) == (550, 75)\n",
    )

    audit = audit_registries(tmp_path)

    assert [(f.kind, f.path, f.line) for f in audit.findings] == [
        (KIND_MISSING_DECLARATION, "tests/test_tuple.py", 3)
    ]


def test_a_local_length_assertion_is_no_finding(tmp_path: Path) -> None:
    """A length assertion inside a function on a name that the function binds locally is no
    ratchet, even when the name is upper-case."""
    _write_module(
        tmp_path,
        "test_local.py",
        "def test_rows() -> None:\n"
        "    rows = [1, 2, 3]\n"
        "    assert len(rows) == 3\n"
        "    LIMIT = [1, 2, 3]\n"
        "    assert len(LIMIT) == 3\n",
    )

    audit = audit_registries(tmp_path)

    assert audit.findings == ()


def test_a_module_that_raises_at_import_is_still_read(tmp_path: Path) -> None:
    """The audit reads the declarations of a module that fails at import time."""
    _write_module(
        tmp_path,
        "test_raises.py",
        'raise RuntimeError("boom")\nREGISTRY_COUNTS = (("name", "stage_requests", "src/x.py"),)\n',
    )

    audit = audit_registries(tmp_path)

    assert [e.token for e in audit.entries] == ["stage_requests"]
    assert audit.findings == ()


def test_the_repository_census() -> None:
    """The audit reads the declarations of the four modules that #3254 added, seven entries, and
    finds no invalid declaration in the repository."""
    audit = audit_registries(REPO_ROOT)

    assert sorted({entry.declaring_path for entry in audit.entries}) == sorted(_DECLARING)
    assert len(audit.entries) == 7
    for finding in audit.findings:
        print(f"{finding.path}:{finding.line} {finding.kind}: {finding.detail}")
    assert [f for f in audit.findings if f.kind == KIND_INVALID_DECLARATION] == []
