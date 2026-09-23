"""Test suite for the coverage-derived reverse index of covering tests."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from devops_cli.core.coverage_index import (
    INDEX_FORMAT_VERSION,
    CoverageIndex,
    build_index_from_coverage,
    load_index,
    save_index,
    select_from_index,
    staleness_reason,
)


def _coverage_db(tmp_path: Path, rows: list[tuple[str, str]]) -> Path:
    """Write a minimal coverage database in the shape `--cov-context=test` produces."""
    db = tmp_path / "ctx.coverage"
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE file (id INTEGER PRIMARY KEY, path TEXT);"
        "CREATE TABLE context (id INTEGER PRIMARY KEY, context TEXT);"
        "CREATE TABLE line_bits (file_id INTEGER, context_id INTEGER, numbits BLOB);"
    )
    for index, (path, context) in enumerate(rows, start=1):
        con.execute("INSERT INTO file VALUES (?, ?)", (index, path))
        con.execute("INSERT INTO context VALUES (?, ?)", (index, context))
        con.execute("INSERT INTO line_bits VALUES (?, ?, ?)", (index, index, b""))
    con.commit()
    con.close()
    return db


def _repo(tmp_path: Path, test_names: list[str]) -> Path:
    """Build a repository whose tests directory holds the given modules."""
    (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
    for name in test_names:
        (tmp_path / "tests" / name).write_text("", encoding="utf-8")
    return tmp_path


# =============================================================================
# Building
# =============================================================================


def test_a_test_reaching_a_module_indirectly_is_still_recorded(tmp_path: Path) -> None:
    """This is the whole reason the index exists.

    The textual selector greps test sources for an import of the changed module, so it
    only finds tests that name it. Measured over this suite it reaches 65.0% mean recall,
    and picks zero covering tests for 21 source files -- `core/cli.py` has 38 covering
    tests and the grep finds none of them, because the tests import commands, not the
    Typer subclass underneath.
    """
    repo = _repo(tmp_path, ["test_cli.py"])
    db = _coverage_db(
        tmp_path, [("/w/src/devops_cli/core/cli.py", "tests/test_cli.py::test_thing|run")]
    )
    index = build_index_from_coverage(db, repo)
    assert index.covering_tests["src/devops_cli/core/cli.py"] == ["tests/test_cli.py"]


def test_the_suite_snapshot_records_tests_that_produced_no_coverage(tmp_path: Path) -> None:
    """A fully skipped test executes no line, so it appears in no context.

    Recording only the tests seen in contexts would make an index look stale the moment it
    was written: nine of this repository's 317 test files produce no context at all.
    """
    repo = _repo(tmp_path, ["test_covered.py", "test_skipped_entirely.py"])
    db = _coverage_db(tmp_path, [("/w/src/devops_cli/a.py", "tests/test_covered.py::test_one|run")])
    index = build_index_from_coverage(db, repo)
    assert "tests/test_skipped_entirely.py" in index.test_files


def test_contexts_outside_the_tests_tree_are_ignored(tmp_path: Path) -> None:
    """Coverage records setup and teardown contexts too; only test files select tests."""
    repo = _repo(tmp_path, ["test_a.py"])
    db = _coverage_db(tmp_path, [("/w/src/devops_cli/a.py", "scripts/tool.py::main|run")])
    assert build_index_from_coverage(db, repo).covering_tests == {}


def test_an_absent_database_yields_an_empty_index(tmp_path: Path) -> None:
    """A first run has no coverage yet; that is not an error, it is a full run."""
    assert build_index_from_coverage(tmp_path / "missing.coverage", tmp_path).is_empty


def test_a_corrupt_database_yields_an_empty_index(tmp_path: Path) -> None:
    """An unreadable index must degrade to running everything, never to running nothing."""
    broken = tmp_path / "broken.coverage"
    broken.write_text("not a database", encoding="utf-8")
    assert build_index_from_coverage(broken, tmp_path).is_empty


# =============================================================================
# Storage
# =============================================================================


def test_an_index_survives_a_round_trip(tmp_path: Path) -> None:
    """The index is built once and read by later runs; it has to persist intact."""
    index = CoverageIndex(
        covering_tests={"src/a.py": ["tests/test_a.py"]}, test_files=["tests/test_a.py"]
    )
    save_index(index, tmp_path / "index.json")
    assert load_index(tmp_path / "index.json").covering_tests == index.covering_tests


def test_an_index_from_an_older_format_is_treated_as_absent(tmp_path: Path) -> None:
    """Misreading a changed shape would select the wrong tests and report success."""
    path = tmp_path / "index.json"
    path.write_text(
        json.dumps({"version": INDEX_FORMAT_VERSION + 1, "covering_tests": {}}), encoding="utf-8"
    )
    assert load_index(path).is_empty


def test_unreadable_json_is_treated_as_absent(tmp_path: Path) -> None:
    """A truncated write must mean "run everything", not "run nothing"."""
    path = tmp_path / "index.json"
    path.write_text("{ truncated", encoding="utf-8")
    assert load_index(path).is_empty


# =============================================================================
# Fail-closed selection
# =============================================================================


def test_a_new_test_file_invalidates_the_index(tmp_path: Path) -> None:
    """A test added since the build is invisible to the index, and may be the only one
    covering the change."""
    repo = _repo(tmp_path, ["test_a.py", "test_brand_new.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py"]}, test_files=["tests/test_a.py"]
    )
    assert "test_brand_new.py" in staleness_reason(index, repo)


def test_an_unindexed_source_forces_a_full_run(tmp_path: Path) -> None:
    """ "The index cannot say" and "nothing covers it" are the same answer only if you are
    willing to ship untested changes."""
    repo = _repo(tmp_path, ["test_a.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py"]}, test_files=["tests/test_a.py"]
    )
    selection = select_from_index(index, ["src/devops_cli/brand_new.py"], repo)
    assert (selection.needs_full_run, selection.unindexed_sources) == (
        True,
        ["src/devops_cli/brand_new.py"],
    )


def test_a_conftest_change_forces_a_full_run(tmp_path: Path) -> None:
    """A fixture change alters tests that never import the file it lives in."""
    repo = _repo(tmp_path, ["test_a.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py"]}, test_files=["tests/test_a.py"]
    )
    assert select_from_index(index, ["tests/conftest.py"], repo).needs_full_run is True


def test_a_dependency_change_forces_a_full_run(tmp_path: Path) -> None:
    """A different resolved version silently changes outcomes across the whole suite."""
    repo = _repo(tmp_path, ["test_a.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py"]}, test_files=["tests/test_a.py"]
    )
    assert select_from_index(index, ["uv.lock"], repo).needs_full_run is True


def test_a_file_outside_the_source_tree_forces_a_full_run(tmp_path: Path) -> None:
    """Tests read manifests, dashboards and docs at runtime; the index maps none of that."""
    repo = _repo(tmp_path, ["test_a.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py"]}, test_files=["tests/test_a.py"]
    )
    assert (
        select_from_index(index, ["k8s/monitoring/dashboards/ai-spend.json"], repo).needs_full_run
        is True
    )


def test_a_changed_test_file_selects_itself(tmp_path: Path) -> None:
    """Editing a test must run that test, whatever it covers."""
    repo = _repo(tmp_path, ["test_a.py", "test_b.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py"]},
        test_files=["tests/test_a.py", "tests/test_b.py"],
    )
    selection = select_from_index(index, ["tests/test_b.py"], repo)
    assert (selection.needs_full_run, selection.test_files) == (False, ["tests/test_b.py"])


def test_an_indexed_source_selects_every_covering_test(tmp_path: Path) -> None:
    """The property the index exists for: full recall for anything it knows about."""
    repo = _repo(tmp_path, ["test_a.py", "test_b.py", "test_c.py"])
    index = CoverageIndex(
        covering_tests={"src/devops_cli/a.py": ["tests/test_a.py", "tests/test_c.py"]},
        test_files=["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"],
    )
    selection = select_from_index(index, ["src/devops_cli/a.py"], repo)
    assert (selection.needs_full_run, selection.test_files) == (
        False,
        ["tests/test_a.py", "tests/test_c.py"],
    )
