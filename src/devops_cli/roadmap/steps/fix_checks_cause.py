"""The files whose failure the change of a branch causes (#6116).

The scope check of the step `fix-checks` stopped a round when the log of the failed check named no
path of the plan. A plan does not list every file that its change breaks, so the check stopped
rounds that the model could repair. On pull request #6114 the plan added an argument to a function,
and two tests in a file that the plan does not list called the function without it.

A file that the log names is in the repair scope when the change of the branch causes its failure:

- the file uses a name whose definition the branch changes: a caller of a changed function, class
  or method. The names come from the abstract syntax trees of the changed Python files at the
  branch point and at the head (`ast`, no model);
- the file is a test that imports a module that the branch changes;
- the file is a snapshot test whose snapshot differs, and the branch changes a source module: a
  changed command or tool changes its snapshot. Tier 1 writes the snapshot again first;
- the branch changes the file itself.

The agent phase rebases a branch that is behind the default branch first (#6639), so the change
of the branch is read from the tip of the default branch. A file that no rule takes, and a log
that names no file of the checkout (an expired ignore, for example), stop the round with a reason
that names each file and why.

The log is the evidence: the test IDs of the pytest summary (`FAILED <path>::<test>`), and the
locations of the errors of ruff and mypy (`<path>:<line>: error:`).
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final

from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.clone_git import default_branch, git
from devops_cli.roadmap.implement.implement_fix_scope import RepairScope

# The operation that a failed git call of the step names.
_OPERATION: Final[str] = "roadmap.fix_checks"
_PATH: Final[str] = r"[\w.-]+(?:/[\w.-]+)*"
# A test of the pytest summary: `FAILED tests/x.py::test_y - ...`, `ERROR tests/x.py::...` and
# `ERROR collecting tests/x.py`. A line of `gh run view --log-failed` starts with the job, the step
# and the time.
_FAILED_TEST: Final = re.compile(
    rf"(?<![\w-])(?:FAILED|ERROR)\s+(?:collecting\s+)?(?P<path>{_PATH}\.pyi?)(?=::|\s|$)",
    re.MULTILINE,
)
# The location of an error of mypy (`path:3: error:`) or ruff (`path:3:8: F401`, or `--> path:3:8`
# in the full form).
_LOCATED_ERROR: Final = re.compile(
    rf"(?<![\w./-])(?P<path>{_PATH}\.\w+):\d+:(?:\d+:)?\s+(?:error:|[A-Z]+\d+\b)"
    rf"|-->\s+(?P<arrow>{_PATH}\.\w+):\d+:\d+"
)
# A failed test of syrupy: its assertion message compares the received value with the snapshot.
_SNAPSHOT_FAILURE: Final = re.compile(
    rf"(?<![\w-])FAILED\s+(?P<path>{_PATH}\.py)::\S+\s+-\s+assert\s+\[\+ received\]\s+==\s+"
    r"\[- snapshot\]"
)
_TEST_DIRECTORIES: Final = frozenset({"tests", "test"})
_SOURCE_ROOT: Final[str] = "src"
_PACKAGE_INIT: Final[str] = "__init__"
_SHOWN_NAMES: Final[int] = 3
OUTSIDE_PLAN: Final[str] = "Failed check log is outside plan scope"


@dataclass(frozen=True)
class BranchChange:
    """What a branch changes after its branch point on the default branch: `paths`, and the names
    of the definitions that it changes in its Python files."""

    paths: frozenset[str] = frozenset()
    names: frozenset[str] = frozenset()

    @property
    def modules(self) -> frozenset[str]:
        """The dotted names of the Python modules that the branch changes, tests left out."""
        return frozenset(
            name for path in self.paths if not is_test(path) and (name := module_name(path))
        )


@dataclass(frozen=True)
class FileCause:
    """A file that the log of a failed check names, and why it is in the repair scope or not."""

    path: str
    reason: str


@dataclass(frozen=True)
class ScopeVerdict:
    """The answer of the scope check of a round (#6116). `in_scope` when the log names a path of
    the plan or a file whose failure the change causes. `caused` holds those files, which the model
    fix may change too. `outside` holds the other files that the log names, with the reason."""

    in_scope: bool
    caused: tuple[FileCause, ...] = ()
    outside: tuple[FileCause, ...] = ()

    @property
    def extra_paths(self) -> tuple[str, ...]:
        """The files outside the plan that the model fix may change."""
        return tuple(cause.path for cause in self.caused)

    def stop_reason(self) -> str:
        """Why the round stops: each file that the log names, with the reason, or that the log
        names no file of the checkout."""
        if not self.outside:
            return (
                f"{OUTSIDE_PLAN}: the log names no path of the plan and no file whose failure "
                "the change causes"
            )
        return f"{OUTSIDE_PLAN}: " + "; ".join(
            f"`{cause.path}`: {cause.reason}" for cause in self.outside
        )


def is_test(path: str) -> bool:
    """Whether `path` is a test file: a file under a test directory, or a `test_*.py`,
    `*_test.py` or `conftest.py` file."""
    pure = PurePosixPath(path)
    return (
        bool(_TEST_DIRECTORIES.intersection(pure.parts[:-1]))
        or pure.name.startswith("test_")
        or pure.name.endswith("_test.py")
        or pure.name == "conftest.py"
    )


def module_name(path: str) -> str | None:
    """The dotted name of the Python module at `path`, with the `src/` root left out: the name of
    the package for its `__init__.py`. None for a file that is not Python."""
    pure = PurePosixPath(path)
    if pure.suffix not in {".py", ".pyi"}:
        return None
    parts = list(pure.with_suffix("").parts)
    if parts and parts[0] == _SOURCE_ROOT:
        parts = parts[1:]
    if parts and parts[-1] == _PACKAGE_INIT:
        parts = parts[:-1]
    return ".".join(parts) or None


def _parsed(text: str | None) -> ast.Module | None:
    if not text:
        return None
    try:
        return ast.parse(text)
    except SyntaxError, ValueError, RecursionError:
        return None


def _definitions(text: str | None) -> dict[str, str]:
    """The functions and classes of the module `text`, and the methods of its classes, by name,
    each with the dump of its tree. A dump has no line numbers, so a move is no change."""
    tree = _parsed(text)
    if tree is None:
        return {}
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            found[node.name] = ast.dump(node)
        if isinstance(node, ast.ClassDef):
            for member in node.body:
                if isinstance(member, ast.FunctionDef | ast.AsyncFunctionDef):
                    found[f"{node.name}.{member.name}"] = ast.dump(member)
    return found


def changed_definitions(base: str | None, head: str | None) -> frozenset[str]:
    """The names of the functions, classes and methods that the module text `head` adds, removes
    or changes against `base`. A changed method also changes its class. A special method, such as
    `__init__`, gives only the name of its class."""
    before, after = _definitions(base), _definitions(head)
    changed = (key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
    names = (key.rpartition(".")[2] for key in changed)
    return frozenset(name for name in names if not (name.startswith("__") and name.endswith("__")))


def _unique(paths: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(paths))


def failed_paths(log: str) -> tuple[str, ...]:
    """The files that the log names as failed, in their order: the files of the failed tests, and
    the locations of the errors of ruff and mypy."""
    tests = (match["path"] for match in _FAILED_TEST.finditer(log))
    located = (match["path"] or match["arrow"] for match in _LOCATED_ERROR.finditer(log))
    return _unique((*tests, *located))


def snapshot_tests(log: str) -> tuple[str, ...]:
    """The test files whose snapshot test failed because the snapshot differs (syrupy)."""
    return _unique(match["path"] for match in _SNAPSHOT_FAILURE.finditer(log))


def _imports(tree: ast.Module) -> frozenset[str]:
    """Each module that `tree` imports, at any place, as a dotted name: for `from a import b`, both
    `a` and `a.b`. A relative import is left out."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return frozenset(names)


def _used_names(text: str, tree: ast.Module | None) -> frozenset[str]:
    """The names that the file uses: the names, the attributes and the imported names of its tree,
    or each word of a file that is not Python."""
    if tree is None:
        return frozenset(re.findall(r"\w+", text))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.rpartition(".")[2])
    return frozenset(names)


def _shown(names: Iterable[str]) -> str:
    listed = sorted(names)
    text = ", ".join(f"`{name}`" for name in listed[:_SHOWN_NAMES])
    return text + (f" and {len(listed) - _SHOWN_NAMES} more" if len(listed) > _SHOWN_NAMES else "")


def _cause(path: str, text: str, change: BranchChange, snapshots: frozenset[str]) -> str | None:
    """Why the change of the branch causes the failure in the file `path` with the text `text`, or
    None when it does not."""
    if path in change.paths:
        return "the branch changes it"
    tree = _parsed(text) if path.endswith((".py", ".pyi")) else None
    if used := _used_names(text, tree) & change.names:
        return f"it uses the changed name {_shown(used)}"
    if tree is not None and is_test(path):
        imported = {
            module
            for module in change.modules
            for name in _imports(tree)
            if name == module or name.startswith(f"{module}.")
        }
        if imported:
            return f"it is a test of the changed module {_shown(imported)}"
    if path in snapshots and change.modules:
        return f"its snapshot differs, and the branch changes {_shown(change.modules)}"
    return None


def judge_scope(
    log: str,
    scope: RepairScope,
    change: Callable[[], BranchChange],
    read: Callable[[str], str | None],
) -> ScopeVerdict:
    """The scope verdict of the log of a failed check (#6116). `scope` is the repair scope of the
    plan. `change` gives the change of the branch, and runs only when the log names a file outside
    the plan. `read` gives the text of a file of the checkout, or None when the checkout has no such
    file."""
    named = scope.names(log)
    plan = set(scope.paths)
    texts = {
        path: text
        for path in failed_paths(log)
        if path not in plan
        and not path.startswith(f"{scope.folder}/")
        and (text := read(path)) is not None
    }
    if not texts:
        return ScopeVerdict(in_scope=named)
    branch = change()
    snapshots = frozenset(snapshot_tests(log))
    caused: list[FileCause] = []
    outside: list[FileCause] = []
    for path, text in texts.items():
        if reason := _cause(path, text, branch, snapshots):
            caused.append(FileCause(path, reason))
        else:
            outside.append(FileCause(path, "the change of the branch does not cause its failure"))
    return ScopeVerdict(
        in_scope=named or bool(caused), caused=tuple(caused), outside=tuple(outside)
    )


def _names(listed: str) -> frozenset[str]:
    return frozenset(name for name in listed.split("\0") if name)


def _text_at(worktree: Path, revision: str, path: str) -> str | None:
    """The text of `path` at `revision`, or None when the revision has no such file."""
    try:
        return git(worktree, "show", f"{revision}:{path}", operation=_OPERATION)
    except GitOperationError:
        return None


def read_branch_change(worktree: Path) -> BranchChange:
    """The change of the branch checked out at `worktree`, from its branch point on the default
    branch of `origin` to `HEAD`. The text of a changed Python file at the head is the text in the
    checkout."""
    main = f"origin/{default_branch(worktree, operation=_OPERATION)}"
    point = git(worktree, "merge-base", main, "HEAD", operation=_OPERATION)
    diff = ("diff", "--name-only", "--no-renames", "-z")
    paths = _names(git(worktree, *diff, point, "HEAD", operation=_OPERATION))
    names: set[str] = set()
    for path in sorted(paths):
        if not path.endswith((".py", ".pyi")):
            continue
        head = worktree / path
        text = head.read_text(encoding="utf-8") if head.is_file() else None
        names.update(changed_definitions(_text_at(worktree, point, path), text))
    return BranchChange(paths=paths, names=frozenset(names))


def checkout_reader(worktree: Path) -> Callable[[str], str | None]:
    """The text of a tracked file of the checkout at `worktree`, or None when git tracks no such
    file. A file that git does not track, such as one under `.venv`, is no file of the change."""

    def read(path: str) -> str | None:
        file = worktree / path
        if not file.is_file():
            return None
        listed = git(worktree, "ls-files", "-z", "--", path, operation=_OPERATION)
        if path not in _names(listed):
            return None
        return file.read_text(encoding="utf-8", errors="replace")

    return read
