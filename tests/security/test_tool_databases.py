"""`devops review fetch-databases`: the fetch step for the osv-scanner and Trivy databases that a
sandboxed review binds read-only (#2131).

The tools are doubled at the process edge. A case answers the command of each tool with the output
that the tool printed on 2026-11-04 (osv-scanner 2.6.0, Trivy 0.75.0), so no case reaches a network
or starts a scanner.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_OSV_DB_DIR_ENV, CONST_OSV_DB_DIR_NAME
from devops_cli.security.tool_databases import (
    FetchedDatabase,
    fetch_databases,
    plan_database_fetches,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

_DAY = 86400.0
# The report of osv-scanner 2.6.0 for `--all-packages` over a lockfile of PyPI and one of npm. It
# exits 1 when a package is vulnerable, and the report names the ecosystem of every package.
_REPORT = json.dumps(
    {
        "results": [
            {
                "source": {"path": "uv.lock", "type": "lockfile"},
                "packages": [{"package": {"name": "idna", "version": "3.6", "ecosystem": "PyPI"}}],
            },
            {
                "source": {"path": "package-lock.json", "type": "lockfile"},
                "packages": [
                    {"package": {"name": "left-pad", "version": "1.3.0", "ecosystem": "npm"}}
                ],
            },
        ]
    }
)
_TRIVY_ERROR = (
    "FATAL\tFatal error\trun error: init error: DB error: failed to download vulnerability DB"
)


@pytest.fixture
def osv_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The directory that names the offline database of osv-scanner, with no database in it."""
    cache = tmp_path / "osv-cache"
    monkeypatch.setenv(CONST_OSV_DB_DIR_ENV, str(cache))
    return cache


@pytest.fixture
def trivy_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The cache directory of Trivy, with nothing in it."""
    cache = tmp_path / "trivy-cache"
    monkeypatch.setenv("TRIVY_CACHE_DIR", str(cache))
    return cache


@pytest.fixture
def lockfile_tree(tmp_path: Path, osv_cache: Path, trivy_cache: Path) -> Path:
    """A tree with the lockfile of two ecosystems, and the two cache directories of the tools."""
    root = tmp_path / "tree"
    root.mkdir()
    (root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (root / "package-lock.json").write_text("{}\n", encoding="utf-8")
    return root


@pytest.fixture
def old_database(osv_cache: Path) -> Callable[[str, float], Path]:
    """Make the database file of an ecosystem, `age` seconds old, and answer its path."""

    def make(ecosystem: str, age: float) -> Path:
        database = osv_cache / CONST_OSV_DB_DIR_NAME / ecosystem / "all.zip"
        database.parent.mkdir(parents=True, exist_ok=True)
        database.write_bytes(b"advisories\n")
        modified = time.time() - age
        os.utime(database, (modified, modified))
        return database

    return make


def _starts(program: str) -> Callable[[ProcessCall], bool]:
    return lambda call: bool(call.argv) and Path(call.argv[0]).name == program


def _answer_tools(
    process_fake: ProcessFake, *, osv_code: int = 1, trivy: ProcessAnswer | None = None
) -> None:
    process_fake.answer(_starts("osv-scanner"), ProcessAnswer(returncode=osv_code, stdout=_REPORT))
    process_fake.answer(_starts("trivy"), trivy or ProcessAnswer())


def _ran(process_fake: ProcessFake) -> list[tuple[str, ...]]:
    return [call.argv for call in process_fake.calls if Path(call.argv[0]).name != "git"]


def test_the_plan_lists_each_command_with_the_directory_the_sandbox_binds(
    lockfile_tree: Path, osv_cache: Path, trivy_cache: Path
) -> None:
    plan = plan_database_fetches(lockfile_tree)

    assert [(request.argv[0], request.argv[1:3], request.env) for request in plan] == [
        ("osv-scanner", ("scan", "source"), ((CONST_OSV_DB_DIR_ENV, str(osv_cache)),)),
        ("trivy", ("fs", "--download-db-only"), (("TRIVY_CACHE_DIR", str(trivy_cache)),)),
        ("trivy", ("config", "<empty-directory>"), (("TRIVY_CACHE_DIR", str(trivy_cache)),)),
    ]
    assert plan[0].argv[3:] == (
        "--format",
        "json",
        "--offline-vulnerabilities",
        "--download-offline-databases",
        "--all-packages",
        "--lockfile",
        str(lockfile_tree / "package-lock.json"),
        "--lockfile",
        str(lockfile_tree / "uv.lock"),
    )


def test_a_fetch_writes_the_directories_that_a_review_binds(
    process_fake: ProcessFake, lockfile_tree: Path, osv_cache: Path, trivy_cache: Path
) -> None:
    _answer_tools(process_fake)

    fetched, failed = fetch_databases(lockfile_tree)

    assert failed == []
    assert fetched == [
        FetchedDatabase("osv-scanner", osv_cache / CONST_OSV_DB_DIR_NAME, ()),
        FetchedDatabase("trivy", trivy_cache),
    ]
    environments = {call.argv[0]: call.env for call in process_fake.calls if call.env}
    assert environments == {
        "osv-scanner": {CONST_OSV_DB_DIR_ENV: str(osv_cache)},
        "trivy": {"TRIVY_CACHE_DIR": str(trivy_cache)},
    }
    first, second = (argv for argv in _ran(process_fake) if argv[0] == "trivy")
    assert (first[1:3], second[1]) == (("fs", "--download-db-only"), "config")
    assert not Path(second[2]).exists()


def test_a_vulnerable_lockfile_is_a_fetch_that_succeeded(
    process_fake: ProcessFake, lockfile_tree: Path
) -> None:
    """osv-scanner exits with 1 when a package of the lockfile is vulnerable."""
    _answer_tools(process_fake, osv_code=1)

    _, failed = fetch_databases(lockfile_tree)

    assert failed == []


def test_a_fetch_renews_the_age_of_the_database_it_confirmed_and_of_no_other(
    process_fake: ProcessFake, lockfile_tree: Path, old_database: Callable[[str, float], Path]
) -> None:
    """osv-scanner rewrites a file only when upstream changed it, so the fetch sets the modified
    time of the file of each ecosystem in the report."""
    pypi = old_database("PyPI", 2 * _DAY)
    npm = old_database("npm", 2 * _DAY)
    crates = old_database("crates.io", 2 * _DAY)
    _answer_tools(process_fake)

    paths = (pypi, npm, crates)
    before = [path.stat().st_mtime for path in paths]

    fetched, _ = fetch_databases(lockfile_tree)

    renewed = [path.stat().st_mtime > old for path, old in zip(paths, before, strict=True)]
    assert renewed == [True, True, False]
    assert fetched[0].ecosystems == ("PyPI", "npm")


def test_a_tree_with_no_lockfile_gets_no_osv_scanner_fetch(
    process_fake: ProcessFake, tmp_path: Path, osv_cache: Path, trivy_cache: Path
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    _answer_tools(process_fake)

    fetched, failed = fetch_databases(empty)

    assert failed == []
    assert [(database.tool, database.ecosystems) for database in fetched] == [
        ("osv-scanner", ()),
        ("trivy", ()),
    ]
    assert {argv[0] for argv in _ran(process_fake)} == {"trivy"}
    assert [request.argv[0] for request in plan_database_fetches(empty)] == ["trivy", "trivy"]


def test_a_file_that_ends_in_lock_but_is_no_lockfile_is_not_named_to_osv_scanner(
    process_fake: ProcessFake, lockfile_tree: Path
) -> None:
    """osv-scanner stops with exit code 127 and prints no report for a file it cannot read."""
    (lockfile_tree / "rules.lock").write_text("{}\n", encoding="utf-8")

    plan = plan_database_fetches(lockfile_tree)

    assert str(lockfile_tree / "rules.lock") not in plan[0].argv


def test_a_failed_fetch_does_not_skip_the_other_tool(
    process_fake: ProcessFake, lockfile_tree: Path
) -> None:
    _answer_tools(
        process_fake,
        trivy=ProcessAnswer(returncode=1, stderr=f"downloading\n{_TRIVY_ERROR}\n"),
    )

    fetched, failed = fetch_databases(lockfile_tree)

    assert [database.tool for database in fetched] == ["osv-scanner"]
    assert [(error.message, error.exit_code) for error in failed] == [
        (f"trivy did not fetch its database (exit code 1): {_TRIVY_ERROR}", 1)
    ]


def test_an_osv_scanner_that_fails_gives_its_error_and_the_trivy_fetch_still_runs(
    process_fake: ProcessFake, lockfile_tree: Path
) -> None:
    process_fake.answer(
        _starts("osv-scanner"),
        ProcessAnswer(returncode=127, stderr="Starting walk\nunable to fetch OSV database\n"),
    )
    process_fake.answer(_starts("trivy"), ProcessAnswer())

    fetched, failed = fetch_databases(lockfile_tree)

    assert [database.tool for database in fetched] == ["trivy"]
    assert [error.message for error in failed] == [
        "osv-scanner did not fetch its database (exit code 127): unable to fetch OSV database"
    ]


def test_an_osv_scanner_report_that_is_not_json_is_a_failed_fetch(
    process_fake: ProcessFake, lockfile_tree: Path
) -> None:
    process_fake.answer(_starts("osv-scanner"), ProcessAnswer(returncode=0, stdout="not json"))
    process_fake.answer(_starts("trivy"), ProcessAnswer())

    _, failed = fetch_databases(lockfile_tree)

    assert [error.details["tool_name"] for error in failed] == ["osv-scanner"]
