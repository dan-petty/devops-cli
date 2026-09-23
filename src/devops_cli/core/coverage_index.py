"""A reverse index from source module to the tests that actually execute it.

`test_selection.py` picks tests by filename convention and by grepping test sources for an
import of the changed module. That finds tests naming a module directly and misses every
test reaching it through an import chain, which is most of them. Measured against per-test
coverage contexts over this repository's whole suite -- 387 source files, 317 test files:

    mean recall     65.0%
    median recall   66.7%
    10th percentile 11%
    zero covering tests selected for 21 files (5%)

The tail is what matters for a gate. A change to `core/cli.py`, the Typer subclass every
command is built on, is covered by 38 test files and the textual selector picks none of
them; `output/formatters/tables.py` misses 39, `ai/text_utils.py` 24. Narrowing a run on
that basis reports green having executed nothing that exercises the change.

Coverage contexts record which test executed which line, so an index built from them has
full recall by construction for every file it contains. This module builds, stores and
queries that index. It does not decide policy: a caller that cannot get a confident answer
must run everything, and `select_from_index` says so rather than guessing.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from devops_cli.config.constants import (
    CONST_SOURCE_ROOT_DIR,
    CONST_TESTS_ROOT_DIR,
)

# Bumped when the stored shape changes, so an index written by an older version is treated
# as absent rather than misread.
INDEX_FORMAT_VERSION = 1

# Changing any of these can alter the outcome of tests that never import the changed
# module, so they defeat the index entirely and force a full run.
_FULL_RUN_TRIGGERS = ("conftest.py", "pyproject.toml", "uv.lock", ".python-version")


@dataclass
class CoverageIndex:
    """Which tests executed which source module, plus what the index was built from."""

    covering_tests: dict[str, list[str]] = field(default_factory=dict)
    test_files: list[str] = field(default_factory=list)
    version: int = INDEX_FORMAT_VERSION

    @property
    def is_empty(self) -> bool:
        """Report whether the index carries no mapping at all."""
        return not self.covering_tests

    def to_dict(self) -> dict[str, object]:
        """Render the index for storage."""
        return {
            "version": self.version,
            "test_files": sorted(self.test_files),
            "covering_tests": {k: sorted(v) for k, v in sorted(self.covering_tests.items())},
        }


@dataclass
class IndexedSelection:
    """What the index could answer, and what it could not."""

    test_files: list[str] = field(default_factory=list)
    unindexed_sources: list[str] = field(default_factory=list)
    full_run_reason: str = ""

    @property
    def needs_full_run(self) -> bool:
        """Report whether the caller must run everything.

        An unindexed source is not "no tests cover it" -- it is "this index cannot say",
        and those are only the same answer if you are willing to ship untested changes.
        """
        return bool(self.full_run_reason or self.unindexed_sources)


def build_index_from_coverage(database: Path, repo_root: Path) -> CoverageIndex:
    """Read a coverage database written with `--cov-context=test` into a reverse index.

    A context looks like `tests/test_foo.py::test_case|run`; only the file part is kept,
    because pytest is invoked per file and a finer grain would not change what runs.
    """
    if not database.is_file():
        return CoverageIndex()

    source_marker = f"/{CONST_SOURCE_ROOT_DIR}/"
    covering: dict[str, set[str]] = {}
    tests: set[str] = set()

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT f.path, c.context FROM line_bits lb "
            "JOIN file f ON f.id = lb.file_id "
            "JOIN context c ON c.id = lb.context_id "
            "WHERE c.context != ''"
        )
        for path, context in rows:
            test_file = str(context).split("::")[0]
            if not test_file.startswith(f"{CONST_TESTS_ROOT_DIR}/"):
                continue
            marker = str(path).find(source_marker)
            if marker == -1:
                continue
            source = str(path)[marker + 1 :]
            covering.setdefault(source, set()).add(test_file)
            tests.add(test_file)
    except sqlite3.DatabaseError:
        return CoverageIndex()
    finally:
        connection.close()

    # `test_files` records the suite as it stood when the index was built, taken from the
    # filesystem rather than from the contexts. A test that executed no `src/` line -- one
    # that is fully skipped, or exercises nothing in the package -- produces no context,
    # and treating it as absent would make every index look stale the moment it was
    # written. Nine of this repository's 317 test files are in that position.
    return CoverageIndex(
        covering_tests={k: sorted(v) for k, v in covering.items()},
        test_files=sorted(_current_test_files(repo_root) | tests),
    )


def save_index(index: CoverageIndex, destination: Path) -> None:
    """Write the index where a later run can find it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(index.to_dict(), indent=2) + "\n", encoding="utf-8")


def load_index(source: Path) -> CoverageIndex:
    """Read a stored index, treating anything unreadable or stale-format as absent."""
    if not source.is_file():
        return CoverageIndex()
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return CoverageIndex()
    if not isinstance(raw, dict) or raw.get("version") != INDEX_FORMAT_VERSION:
        return CoverageIndex()

    covering = raw.get("covering_tests")
    tests = raw.get("test_files")
    if not isinstance(covering, dict) or not isinstance(tests, list):
        return CoverageIndex()
    return CoverageIndex(
        covering_tests={str(k): [str(x) for x in v] for k, v in covering.items()},
        test_files=[str(x) for x in tests],
    )


def _current_test_files(repo_root: Path) -> set[str]:
    """List the test modules present in the working tree."""
    tests_root = repo_root / CONST_TESTS_ROOT_DIR
    if not tests_root.is_dir():
        return set()
    return {
        str(path.relative_to(repo_root)) for path in tests_root.rglob("test_*.py") if path.is_file()
    }


def staleness_reason(index: CoverageIndex, repo_root: Path) -> str:
    """Explain why the index cannot be trusted, or return an empty string.

    A test added since the index was built is invisible to it, and that test may be the
    only one covering the change. Rather than rank that risk, any drift in the set of test
    files invalidates the index outright.
    """
    if index.is_empty:
        return "no coverage index has been built"
    present = _current_test_files(repo_root)
    missing = present - set(index.test_files)
    if missing:
        sample = ", ".join(sorted(missing)[:3])
        return f"{len(missing)} test file(s) added since the index was built: {sample}"
    return ""


def select_from_index(
    index: CoverageIndex,
    changed: Iterable[str],
    repo_root: Path,
) -> IndexedSelection:
    """Map changed sources to their covering tests, or explain why it cannot be done."""
    stale = staleness_reason(index, repo_root)
    if stale:
        return IndexedSelection(full_run_reason=stale)

    selected: set[str] = set()
    unindexed: list[str] = []
    for raw in changed:
        path = str(raw).replace("\\", "/")
        if Path(path).name in _FULL_RUN_TRIGGERS:
            return IndexedSelection(
                full_run_reason=f"{path} can change the outcome of tests that never import it"
            )
        if path.startswith(f"{CONST_TESTS_ROOT_DIR}/"):
            selected.add(path)
            continue
        if not path.startswith(f"{CONST_SOURCE_ROOT_DIR}/"):
            return IndexedSelection(
                full_run_reason=f"{path} is outside {CONST_SOURCE_ROOT_DIR}/ and its effect is unmapped"
            )
        covering = index.covering_tests.get(path)
        if covering is None:
            unindexed.append(path)
            continue
        selected.update(covering)

    return IndexedSelection(test_files=sorted(selected), unindexed_sources=sorted(unindexed))


__all__ = [
    "INDEX_FORMAT_VERSION",
    "CoverageIndex",
    "IndexedSelection",
    "build_index_from_coverage",
    "load_index",
    "save_index",
    "select_from_index",
    "staleness_reason",
]
