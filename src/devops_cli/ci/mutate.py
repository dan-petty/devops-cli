"""Which functions `devops ci mutate` hands to mutmut, and what mutmut found in them (#853).

mutmut 3.8 mutates the functions defined at a module's top level and those directly in the body
of a top-level class, except a function carrying any decorator but one bare `staticmethod` or
`classmethod`, and `__new__`, `__getattribute__` and `__setattr__`. It names each function by its
module and a mangled name, and each mutant by that name, `__mutmut_` and a number. `mutmut run`
takes globs over those names, and `mutmut results --all true` prints one `<mutant>: <status>` line
for every mutant.
"""

from __future__ import annotations

import ast
import fnmatch
from collections import Counter
from collections.abc import Iterator, Sequence
from pathlib import Path, PurePosixPath

from pydantic import BaseModel, ConfigDict

from devops_cli.config.constants import (
    CONST_GIT_NAME_STATUS_CHANGE_TYPES,
    CONST_MUTMUT_CLASS_SEPARATOR,
    CONST_MUTMUT_COUNTED_STATUSES,
    CONST_MUTMUT_FUNCTION_PREFIX,
    CONST_MUTMUT_METHOD_PREFIX,
    CONST_MUTMUT_MUTABLE_DECORATORS,
    CONST_MUTMUT_MUTANT_INFIX,
    CONST_MUTMUT_NEVER_MUTATED_NAMES,
    CONST_MUTMUT_SURVIVING_STATUSES,
    CONST_PYTHON_FILE_SUFFIX,
    CONST_SOURCE_ROOT_DIR,
)
from devops_cli.core.process import run_subprocess
from devops_cli.exceptions import GitOperationError
from devops_cli.git.operations import list_changed_files, read_file_at_revision, resolve_merge_base
from devops_cli.lang import MESSAGES

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef
# A function's class, None at module level, and its name.
FunctionKey = tuple[str | None, str]

_DELETED = CONST_GIT_NAME_STATUS_CHANGE_TYPES["D"]


def mutmut_module(path: str) -> str:
    """The module mutmut names a source file by: its path under `src`, without `__init__`."""
    parts = PurePosixPath(path).relative_to(CONST_SOURCE_ROOT_DIR).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


class MutationTarget(BaseModel):
    """A function mutmut mutates: where it is defined, and the names mutmut gives it."""

    model_config = ConfigDict(frozen=True)

    path: str
    line: int
    class_name: str | None
    name: str

    @property
    def qualname(self) -> str:
        """The function's name, after its class's for a method."""
        return f"{self.class_name}.{self.name}" if self.class_name else self.name

    @property
    def mangled(self) -> str:
        """mutmut's name for the function within its module."""
        if self.class_name is None:
            return f"{CONST_MUTMUT_FUNCTION_PREFIX}{self.name}"
        return f"{CONST_MUTMUT_METHOD_PREFIX}{self.class_name}{CONST_MUTMUT_CLASS_SEPARATOR}{self.name}"

    @property
    def mutant_pattern(self) -> str:
        """The pattern matching the function's own mutants, and no other function's."""
        return f"{mutmut_module(self.path)}.{self.mangled}{CONST_MUTMUT_MUTANT_INFIX}*"

    @property
    def run_globs(self) -> tuple[str, str]:
        """The globs `mutmut run` takes for the function: its mutants, then its test stats entry.

        mutmut runs the tests of the stats entries the globs match before it mutates, and every
        test when they match none; no mutant's name is a stats entry. The stats glob starts with
        `*` because mutmut reads a name without one as a mutant's.
        """
        return self.mutant_pattern, f"*{mutmut_module(self.path)}.{self.mangled}"


class MutationReport(BaseModel):
    """What `mutmut results` says of the targets' mutants: how many have each counted status,
    and each mutant no test killed, with its target."""

    model_config = ConfigDict(frozen=True)

    counts: dict[str, int]
    survivors: tuple[tuple[str, MutationTarget], ...]


def _is_mutable(function: FunctionNode) -> bool:
    """mutmut leaves a function with a name it never mutates alone, and a decorated function
    unless one bare decorator allows it."""
    if function.name in CONST_MUTMUT_NEVER_MUTATED_NAMES:
        return False
    match function.decorator_list:
        case []:
            return True
        case [ast.Name(id=decorator)]:
            return decorator in CONST_MUTMUT_MUTABLE_DECORATORS
        case _:
            return False


def _keyed_functions(module: ast.Module) -> Iterator[tuple[FunctionKey, FunctionNode]]:
    """The module's top-level functions and its top-level classes' methods, in source order."""
    for node in module.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield (None, node.name), node
        elif isinstance(node, ast.ClassDef):
            yield from (
                ((node.name, method.name), method)
                for method in node.body
                if isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef)
            )


def mutable_functions(text: str) -> dict[FunctionKey, FunctionNode]:
    """The functions mutmut mutates in a module's text, keyed by class and name."""
    return {key: node for key, node in _keyed_functions(ast.parse(text)) if _is_mutable(node)}


def changed_functions(base_text: str, head_text: str) -> dict[FunctionKey, FunctionNode]:
    """The mutable functions of `head_text` that `base_text` lacks or defines differently.

    Syntax trees are compared, so moving or reformatting a function does not change it, and an
    empty base text selects every function.
    """
    base = {key: ast.dump(node) for key, node in mutable_functions(base_text).items()}
    return {
        key: node
        for key, node in mutable_functions(head_text).items()
        if base.get(key) != ast.dump(node)
    }


def _changed_since(root: Path, base: str) -> dict[str, str]:
    """Each file the working tree changed since its merge base with `base`, and its text there.

    A file added since, untracked ones that git does not ignore included, has an empty text
    there, so all of its functions count as changed. A `base` naming no commit is an error:
    git would find no merge base and diff nothing.
    """
    if (merge_base := resolve_merge_base(root, base)) is None:
        raise GitOperationError(MESSAGES.ci.mutate_base_refused.format(base=base))
    verify = ["git", "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}"]
    if run_subprocess(verify, cwd=root, quiet=True).returncode != 0:
        raise GitOperationError(MESSAGES.ci.mutate_base_missing.format(base=base))
    changed = {
        change.path: read_file_at_revision(root, merge_base, change.base_path) or ""
        for change in list_changed_files(root, merge_base)
        if change.change_type != _DELETED
    }
    untracked = ["git", "ls-files", "--others", "--exclude-standard", "-z", "--"]
    listed = run_subprocess([*untracked, CONST_SOURCE_ROOT_DIR], cwd=root, quiet=True).stdout
    return changed | dict.fromkeys(filter(None, listed.split("\0")), "")


def _python_files(path: Path) -> list[Path]:
    """The file `path` names, or the Python files under the directory it names."""
    if path.is_dir():
        return sorted(path.rglob(f"*{CONST_PYTHON_FILE_SUFFIX}"))
    return [path] if path.is_file() else []


def _named_sources(root: Path, wanted: Sequence[PurePosixPath]) -> dict[str, str]:
    """Each Python file the paths name or hold, with an empty base text: all of its functions."""
    return {
        file.relative_to(root).as_posix(): ""
        for path in wanted
        for file in _python_files(root / path)
    }


def _is_mutated_source(path: PurePosixPath) -> bool:
    """Whether mutmut mutates the file: a Python module under `src`."""
    return path.suffix == CONST_PYTHON_FILE_SUFFIX and path.is_relative_to(CONST_SOURCE_ROOT_DIR)


def _targets(root: Path, path: str, base_text: str) -> list[MutationTarget]:
    head_text = (root / path).read_text(encoding="utf-8")
    return [
        MutationTarget(path=path, line=node.lineno, class_name=class_name, name=name)
        for (class_name, name), node in changed_functions(base_text, head_text).items()
    ]


def select_targets(
    root: Path, paths: Sequence[Path], *, changed: bool, base: str
) -> list[MutationTarget]:
    """The functions to mutate under `src`.

    With `changed`, those the working tree changed since its merge base with `base`, kept to
    `paths` when any are given; otherwise every function in the files `paths` name or hold.
    """
    root = root.resolve()
    wanted = [
        PurePosixPath(path.relative_to(root).as_posix())
        for path in (given.resolve() for given in paths)
        if path.is_relative_to(root)
    ]
    sources = _changed_since(root, base) if changed else _named_sources(root, wanted)
    return [
        target
        for path, base_text in sources.items()
        if _is_mutated_source(PurePosixPath(path))
        and (not paths or any(PurePosixPath(path).is_relative_to(each) for each in wanted))
        for target in _targets(root, path, base_text)
    ]


def _result(line: str) -> tuple[str, str]:
    """A `mutmut results` line's mutant name and status."""
    name, _, status = line.strip().rpartition(": ")
    return name, status


def tally(results_text: str, targets: Sequence[MutationTarget]) -> MutationReport:
    """Read `mutmut results --all true` output for the targets' mutants."""
    status_by_mutant = dict(map(_result, results_text.splitlines()))
    mutants = [
        (name, status_by_mutant[name], target)
        for target in targets
        for name in fnmatch.filter(status_by_mutant, target.mutant_pattern)
    ]
    statuses = Counter(status for _, status, _ in mutants)
    return MutationReport(
        counts={status: statuses[status] for status in CONST_MUTMUT_COUNTED_STATUSES},
        survivors=tuple(
            (name, target)
            for name, status, target in mutants
            if status in CONST_MUTMUT_SURVIVING_STATUSES
        ),
    )
