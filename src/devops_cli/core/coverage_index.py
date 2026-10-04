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

Building this index requires the `ctrace` coverage core (`COVERAGE_CORE=ctrace`), because
under Python 3.14's default `sysmon` core, dynamic contexts are unsupported
(`no-sysmon-context`) and lines are disabled after the first hit, attributing coverage
almost entirely to whichever test ran first.

Coverage contexts record which test executed which line, so an index built from them has
full recall for code executed within each test's own context. Lines run during module import
have an empty context and are dropped, and code executed exclusively inside shared session
fixtures or memoized helpers is credited only to the first test that reached it.

This module builds, stores, and queries that index. It does not decide policy: a caller that
cannot get a confident answer must run everything, and `select_from_index` says so rather
than guessing.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from devops_cli.config.constants import (
    CONST_PYTHON_FILE_SUFFIX,
    CONST_SOURCE_ROOT_DIR,
    CONST_TEST_FILE_PREFIX,
    CONST_TESTS_ROOT_DIR,
)

# Bumped when the stored shape changes, so an index written by an older version is treated
# as absent rather than misread.
INDEX_FORMAT_VERSION = 2

# Changing any of these can alter the outcome of tests that never import the changed
# module, so they defeat the index entirely and force a full run.
_FULL_RUN_TRIGGERS = ("conftest.py", "pyproject.toml", "uv.lock", ".python-version")


def _is_test_file(path: str) -> bool:
    """Report whether a path points to an executable test module."""
    name = Path(path).name
    return name.startswith(CONST_TEST_FILE_PREFIX) and name.endswith(CONST_PYTHON_FILE_SUFFIX)


def _helper_import_pattern(helper_path: str) -> re.Pattern[str]:
    """Build a regex matching imports of a test helper module under tests/."""
    p = Path(helper_path)
    stem = p.stem
    rel_parts = list(p.parts)
    if rel_parts and rel_parts[0] == CONST_TESTS_ROOT_DIR:
        rel_parts = rel_parts[1:]
    rel_without_tests = ".".join(rel_parts)[: -len(p.suffix)] if rel_parts else stem
    dotted_full = (
        f"{CONST_TESTS_ROOT_DIR}.{rel_without_tests}"
        if rel_without_tests
        else f"{CONST_TESTS_ROOT_DIR}.{stem}"
    )
    package, _, leaf = dotted_full.rpartition(".")

    patterns = [
        rf"\b{re.escape(dotted_full)}\b",
        rf"from\s+{re.escape(package)}\s+import\s+\(?[^)\n]*\b{re.escape(leaf)}\b",
        rf"from\s+(?:{CONST_TESTS_ROOT_DIR}\.)?{re.escape(rel_without_tests)}\s+import\b",
        rf"import\s+(?:{CONST_TESTS_ROOT_DIR}\.)?{re.escape(rel_without_tests)}\b",
    ]
    return re.compile("|".join(patterns))


def _find_tests_importing_helper(
    helper_path: str, repo_root: Path, test_files: Iterable[str]
) -> set[str]:
    """Find test modules that import or reference a helper module under tests/."""
    if not helper_path.endswith(CONST_PYTHON_FILE_SUFFIX):
        return set()
    pattern = _helper_import_pattern(helper_path)
    matching: set[str] = set()
    for test_rel in test_files:
        test_abs = repo_root / test_rel
        try:
            content = test_abs.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if pattern.search(content):
            matching.add(test_rel)
    return matching


def _normalize_source_path(path: str, repo_root: Path) -> str | None:
    """Normalize a path to a repo-relative source path starting with CONST_SOURCE_ROOT_DIR."""
    candidate = Path(path)
    for root in (repo_root, repo_root.resolve()):
        try:
            rel = candidate.resolve().relative_to(root).as_posix()
            if rel.startswith(f"{CONST_SOURCE_ROOT_DIR}/"):
                return rel
        except ValueError, RuntimeError:
            pass
    posix_path = candidate.as_posix()
    if posix_path.startswith(f"{CONST_SOURCE_ROOT_DIR}/"):
        return posix_path
    marker = f"/{CONST_SOURCE_ROOT_DIR}/"
    idx = posix_path.rfind(marker)
    if idx != -1:
        return posix_path[idx + 1 :]
    return None


@dataclass
class CoverageIndex:
    """Which tests executed which source module, plus what the index was built from."""

    covering_tests: dict[str, list[str]] = field(default_factory=dict)
    test_files: list[str] = field(default_factory=list)
    source_hashes: dict[str, str] = field(default_factory=dict)
    built_at: float = 0.0
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
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "built_at": self.built_at,
        }


def filter_coverage_source_hashes(hashes: dict[str, str]) -> dict[str, str]:
    """Filter worktree blob hashes to files affecting coverage or test selection."""
    filtered: dict[str, str] = {}
    for path, sha in hashes.items():
        norm = path.replace("\\", "/")
        name = Path(norm).name
        if name in _FULL_RUN_TRIGGERS:
            filtered[norm] = sha
        elif (
            norm.startswith(f"{CONST_SOURCE_ROOT_DIR}/")
            or norm.startswith(f"{CONST_TESTS_ROOT_DIR}/")
        ) and norm.endswith(CONST_PYTHON_FILE_SUFFIX):
            filtered[norm] = sha
    return filtered


def compute_index_drift(
    index: CoverageIndex,
    current_hashes: dict[str, str],
) -> list[str]:
    """Return sorted list of files that were added, removed, or modified since build."""
    curr_filtered = filter_coverage_source_hashes(current_hashes)
    stored = index.source_hashes
    all_keys = set(stored.keys()) | set(curr_filtered.keys())
    return sorted(k for k in all_keys if stored.get(k) != curr_filtered.get(k))


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


def build_index_from_coverage(
    database: Path,
    repo_root: Path,
    source_hashes: dict[str, str] | None = None,
    built_at: float | None = None,
) -> CoverageIndex:
    """Read a coverage database written with `--cov-context=test` into a reverse index.

    A context looks like `tests/test_foo.py::test_case|run`; only the file part is kept,
    because pytest is invoked per file and a finer grain would not change what runs.
    """
    if not database.is_file():
        return CoverageIndex()

    covering: dict[str, set[str]] = {}
    tests: set[str] = set()

    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT DISTINCT f.path, substr(c.context, 1, instr(c.context || '::', '::') - 1) "
            "FROM line_bits lb "
            "JOIN file f ON f.id = lb.file_id "
            "JOIN context c ON c.id = lb.context_id "
            "WHERE c.context != ''"
        )
        path_cache: dict[str, str | None] = {}
        for path, test_file in rows:
            test_file_str = str(test_file)
            if not test_file_str.startswith(f"{CONST_TESTS_ROOT_DIR}/"):
                continue
            path_str = str(path)
            if path_str not in path_cache:
                path_cache[path_str] = _normalize_source_path(path_str, repo_root)
            source = path_cache[path_str]
            if source is None:
                continue
            covering.setdefault(source, set()).add(test_file_str)
            tests.add(test_file_str)
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
        source_hashes=dict(source_hashes or {}),
        built_at=float(built_at or 0.0),
    )


def save_index(index: CoverageIndex, destination: Path) -> None:
    """Write the index atomically where a later run can find it."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(index.to_dict(), indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", dir=destination.parent, delete=False, encoding="utf-8"
    ) as tf:
        tf.write(content)
        temp_name = tf.name
    os.replace(temp_name, destination)


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
    source_hashes = raw.get("source_hashes")
    built_at = raw.get("built_at")
    if not isinstance(covering, dict) or not isinstance(tests, list):
        return CoverageIndex()
    hashes_dict = (
        {str(k): str(v) for k, v in source_hashes.items()}
        if isinstance(source_hashes, dict)
        else {}
    )
    ts = float(built_at) if isinstance(built_at, int | float) else 0.0
    return CoverageIndex(
        covering_tests={str(k): [str(x) for x in v] for k, v in covering.items()},
        test_files=[str(x) for x in tests],
        source_hashes=hashes_dict,
        built_at=ts,
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

    Only an absent or format-version-mismatched index is unusable. Drift in source or test
    files since the build is handled by adding changed files to the selection set rather
    than invalidating the index.
    """
    if index.is_empty:
        return "no coverage index has been built"
    if index.version != INDEX_FORMAT_VERSION:
        return f"coverage index format version {index.version} is not supported"
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
    known_tests = set(index.test_files) | _current_test_files(repo_root)

    for raw in changed:
        path = str(raw).replace("\\", "/")
        if Path(path).name in _FULL_RUN_TRIGGERS:
            return IndexedSelection(
                full_run_reason=f"{path} can change the outcome of tests that never import it"
            )
        if path.startswith(f"{CONST_TESTS_ROOT_DIR}/"):
            if _is_test_file(path):
                if (repo_root / path).is_file():
                    selected.add(path)
            else:
                importing = _find_tests_importing_helper(path, repo_root, known_tests)
                if importing:
                    selected.update(importing)
                else:
                    unindexed.append(path)
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

    valid_selected = sorted(t for t in selected if (repo_root / t).is_file())
    return IndexedSelection(test_files=valid_selected, unindexed_sources=sorted(unindexed))


__all__ = [
    "INDEX_FORMAT_VERSION",
    "CoverageIndex",
    "IndexedSelection",
    "_find_tests_importing_helper",
    "_is_test_file",
    "_normalize_source_path",
    "build_index_from_coverage",
    "compute_index_drift",
    "filter_coverage_source_hashes",
    "load_index",
    "save_index",
    "select_from_index",
    "staleness_reason",
]
