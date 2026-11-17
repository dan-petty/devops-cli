"""The paths of a plan against the files of the staged commit (#3010).

The model cannot list files, and the issue body it reads cites paths of an older commit. So a plan
can name a file that does not exist: 25 of the 37 plans of 2026-10-31 did. `path_problems` finds
each such path in the reply and in the change folder of a plan pull request: a group lists a new
file in the `creates` list of a reply, or marks it ` (new)` on its `Changes:` line in `tasks.md`. A
path is missing when the commit does not hold it and no group up to the group that names it creates
it. The groups are in order, so a group sees the `creates` of the groups before it and of itself.

A group names paths in four places: `reads`, `changes`, the code spans of its three tasks, and the
words of `verify`. The paths of a negative search are the paths of its fixed shape (#3263). Only
the code spans of a task count, as the implement step reads those and no other text
(`step_files`). A word is a path when its last name ends in a suffix that a tracked file
has, or when its first folder is a top-level name of the tree. A word with no folder is no path:
it is a search pattern or a fixture that a test writes at run time (`ruff.toml`), and the implement
step accepts a name that holds no file as a file it creates. A label such as `status/blocked`, a
dotted name, an option, a URL or a placeholder is no path either, and the check leaves it alone.
`reads` and `changes` list paths by definition, so the check keeps them strict.

A plan that changes a YAML manifest of `k8s/` also names every test that references it (#3972).
`record_test_references` reads that record from the search of the job, and
`missing_reference_problems` refuses the plan that leaves a test of the record out of `changes`: a
test builds the path of a manifest from the file name and the name of its folder, so a test
references the manifest when it holds both names. The implement job cannot edit a test outside its
`Changes:` list, so a plan that leaves the test out would loop.

A behavior group that changes a Python module under `src/` also names an existing test of that
module (#3414). `record_module_tests` reads the record from the tree and the search of the job: a
test belongs to a module when it imports the module, a package whose `__init__.py` imports it, or
another module that the plan changes and that imports it (#4467). `ast` and the import graph read
the imports, so a test that holds the name of the module in a string or a path is no test of it. `existing_test_problems` refuses the group that names none
of the tests of a module it changes, and names each such module of the group at once (#5068). A
test that the plan creates is no existing test, and a module with no test passes.

A plan that adds a parameter to a function also lists each file under `src/` that calls the
function (#3307). `changed_functions` reads a task clause that adds a parameter, an argument or a
keyword to a function (#4467), or that adds one code span in parameter shape, as `name` or
`name: Type = default` (#4529). `StagedTree.callers` reads the calls with `ast`, and a name that no
module defines with `def`, as a class or an enum, has no caller.
"""

from __future__ import annotations

import ast
import posixpath
import re
import shlex
from collections import defaultdict
from collections.abc import Callable, Collection, Iterable, Iterator, Mapping, Sequence
from enum import StrEnum
from fnmatch import fnmatchcase
from functools import partial
from glob import has_magic
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, Self

from devops_cli.config.constants import CONST_GIT_CLI
from devops_cli.core.import_graph import build_import_graph, module_name
from devops_cli.core.process import run_subprocess
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.clone_git import git
from devops_cli.roadmap.implement.implement_shell_policy import (
    NEGATIVE_SEARCH_WORD,
    read_negative_search,
)
from devops_cli.roadmap.step_files import code_spans

if TYPE_CHECKING:
    from devops_cli.roadmap.stage.stage_change import StageGroup

# The most files with the same name that a problem lists.
SAME_NAME_MAX: Final[int] = 5
# A location after a path: `::test_name` of a test, or `:12` and `:12-20` of a line.
_LOCATION: Final[re.Pattern[str]] = re.compile(r"(?:::.*|:\d+(?:-\d+)?)$")
# The characters of a path word. A quote, a `$`, a `<`, a `*` or a `:` makes a word no path.
_WORD: Final[re.Pattern[str]] = re.compile(r"[\w.@+-]+(?:/[\w.@+-]+)*/?")
_PARENT_DIRECTORY: Final[str] = ".."
# The folder the stage job writes: a group never changes or creates a path in it.
_CHANGES_DIRECTORY: Final[str] = "openspec/changes"
# The manifests that a plan changes, and the tests that reference them (#3972).
_MANIFEST_TOP: Final[str] = "k8s/"
_MANIFEST_SUFFIX: Final[str] = ".yaml"
_SOURCE_TOP: Final[str] = "src/"
_MODULE_SUFFIX: Final[str] = ".py"
_TESTS_TOP: Final[str] = "tests/"
# A module has a mirror in `tests/` when a folder holds it: the file name and one folder.
_MIRROR_MIN_PARTS: Final[int] = 2
# The name forms of a test module. A fixture under `tests/` holds the names of a manifest too, and
# it asserts on nothing, so the record names no fixture.
_TEST_MODULE_PATTERNS: Final[tuple[str, ...]] = ("test_*.py", "*_test.py")


class _Place(StrEnum):
    """Where a group names a path."""

    READS = "reads"
    CHANGES = "changes"
    TASK = "task"
    VERIFY = "verify"


def _folders_of(path: str) -> set[str]:
    """The folders above `path`, without the root."""
    return {str(parent) for parent in PurePosixPath(path).parents} - {"."}


def change_folder_paths(paths: Iterable[str]) -> list[str]:
    """The paths in `paths` that are the change folder or sit under it. A group never writes
    there: the stage job writes the change, and the groups are the steps after it (#3285)."""
    return [
        path
        for path in paths
        if path == _CHANGES_DIRECTORY or path.startswith(f"{_CHANGES_DIRECTORY}/")
    ]


class StagedTree:
    """The tracked files of a checkout, with what the check needs to know about them: the folders
    above them, their suffixes, their top-level names and the files of each name."""

    def __init__(
        self,
        files: Iterable[str],
        *,
        source: Path | None = None,
        reader: Callable[[str], str] | None = None,
    ) -> None:
        self._source = source
        self._reader = reader or (None if source is None else partial(_checkout_text, source))
        self._files = frozenset(files)
        self._folders = frozenset(folder for path in self._files for folder in _folders_of(path))
        self._suffixes = frozenset(PurePosixPath(path).suffix for path in self._files) - {""}
        self._tops = frozenset(path.partition("/")[0] for path in self._files)
        by_name: defaultdict[str, list[str]] = defaultdict(list)
        for path in sorted(self._files):
            by_name[PurePosixPath(path).name].append(path)
        self._by_name = dict(by_name)

    @classmethod
    def read(cls, source: Path, *, operation: str) -> Self:
        """The tracked files of the checkout at `source`: one `git ls-files`. A failed command
        raises `GitOperationError`, so the job never judges a plan on a tree it could not read."""
        listing = git(source, "ls-files", "-z", operation=operation)
        return cls((path for path in listing.split("\0") if path), source=source)

    @property
    def source(self) -> Path | None:
        """The source directory of the checkout, or None."""
        return self._source

    @property
    def files(self) -> frozenset[str]:
        """The files of the tree."""
        return self._files

    def with_files(self, paths: Iterable[str]) -> StagedTree:
        """A tree that also holds `paths`: the files that the job itself writes."""
        return StagedTree([*self._files, *paths], source=self._source, reader=self._reader)

    @property
    def reader(self) -> Callable[[str], str] | None:
        """The text of a tracked file: from the reader that the tree got, else from the checkout.
        None for a tree with neither, as the tree of a replay case."""
        return self._reader

    def callers(self, name: str) -> list[str]:
        """The files under `src/` that call the function `name`, as `name(...)` or
        `value.name(...)`, read with `ast`. `git grep -F -w` finds the files that hold the name as
        a word, so `scan_fix(` is no call of `_fix`. A name that no file under `src/` defines with
        `def` is no function, as a class or an enum is not, so it has no caller (#4467)."""
        if self._source is None or self._reader is None:
            return []
        proc = run_subprocess(
            [
                CONST_GIT_CLI,
                "-C",
                str(self._source),
                "grep",
                "-l",
                "-F",
                "-w",
                "-e",
                name,
                "--",
                "src",
            ],
            check=False,
            quiet=True,
        )
        if proc.returncode != 0:
            return []
        return calling_files({path: self._reader(path) for path in proc.stdout.splitlines()}, name)

    def has(self, path: str) -> bool:
        """Whether the tree holds the file or the folder `path`, or a file that a glob matches."""
        path = path.rstrip("/")
        if path in self._files or path in self._folders:
            return True
        return has_magic(path) and any(fnmatchcase(file, path) for file in self._files)

    def has_folder(self, path: str) -> bool:
        """Whether the tree holds the folder `path`."""
        return path.rstrip("/") in self._folders

    def same_name(self, path: str) -> list[str]:
        """The files of the tree with the file name of `path`, sorted, at most `SAME_NAME_MAX`."""
        return self._by_name.get(PurePosixPath(path).name, [])[:SAME_NAME_MAX]

    def as_path(self, word: str) -> str | None:
        """The path that `word` names, or None when the word is no path."""
        word = _LOCATION.sub("", word)
        if word.startswith("-") or not _WORD.fullmatch(word):
            return None
        path = posixpath.normpath(word)
        if "/" not in path or path.startswith(f"{_PARENT_DIRECTORY}/"):
            return None
        known = PurePosixPath(path).suffix in self._suffixes or path.partition("/")[0] in self._tops
        return path if known else None

    def paths_in(self, text: str) -> list[str]:
        """The paths among the words of `text`."""
        return [path for word in text.split() if (path := self.as_path(word)) is not None]

    def code_span_paths(self, text: str) -> list[str]:
        """The paths among the code spans of `text`, in order. Only a code span names a path: the
        other words of a text are prose that a check leaves alone."""
        return [path for span in code_spans(text) for path in self.paths_in(span)]


def _checkout_text(source: Path, path: str) -> str:
    """The text of the file `path` of the checkout at `source`."""
    return (source / path).read_text(encoding="utf-8")


def _parse(text: str) -> ast.Module:
    """The module of `text`; a file that `ast` cannot parse is an empty module, which defines,
    calls and imports nothing."""
    try:
        return ast.parse(text)
    except SyntaxError, ValueError:
        return ast.Module(body=[], type_ignores=[])


def _defines_function(node: ast.AST, name: str) -> bool:
    """Whether `node` defines the function or the method `name`."""
    return isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name


def _calls(node: ast.AST, name: str) -> bool:
    """Whether `node` calls `name`, as `name(...)` or `value.name(...)`."""
    if not isinstance(node, ast.Call):
        return False
    match node.func:
        case ast.Name(id=called) | ast.Attribute(attr=called):
            return called == name
    return False


def calling_files(modules: Mapping[str, str], name: str) -> list[str]:
    """The paths of `modules`, a map of path to text, that call the function `name`, sorted. A
    call is `name(...)` or `value.name(...)`; a definition, a string and a longer name are none.
    When no module defines a function or a method `name`, the name is no function, as a class or an
    enum is not, and no path calls it."""
    nodes = {path: list(ast.walk(_parse(text))) for path, text in modules.items()}
    if not any(_defines_function(node, name) for found in nodes.values() for node in found):
        return []
    return sorted(path for path, found in nodes.items() if any(_calls(n, name) for n in found))


def _keep_slash(path: str) -> str:
    """`path` in normal form, with the trailing slash kept: a path that ends in `/` is a folder,
    and `README.md/` matches nothing in git."""
    return posixpath.normpath(path) + ("/" if path.endswith("/") else "")


def _verify_paths(verify: str, tree: StagedTree) -> list[str]:
    """The paths that the `verify` command names. A negative search names its paths for sure: the
    reader of the step gives them, one-folder words such as `src/` included, which `as_path`
    leaves alone. A path that is no file of the commit and that no group creates would make the
    search find nothing, and the check pass. `.` is the whole tree. Any other command names the
    words that look like paths."""
    try:
        words = shlex.split(verify)
    except ValueError:
        return tree.paths_in(verify)
    if words[:1] == [NEGATIVE_SEARCH_WORD] and not isinstance(
        found := read_negative_search(words), str
    ):
        return [_keep_slash(path) for path in found.paths if posixpath.normpath(path) != "."]
    return tree.paths_in(verify)


def _named(group: StageGroup, tree: StagedTree) -> Iterator[tuple[_Place, str]]:
    """Each path that `group` names, with the place."""
    yield from ((_Place.READS, path) for path in group.reads)
    yield from ((_Place.CHANGES, path) for path in group.changes)
    for text in (group.test, group.implementation, group.documentation, group.process):
        yield from ((_Place.TASK, path) for path in tree.code_span_paths(text or ""))
    yield from ((_Place.VERIFY, path) for path in _verify_paths(group.verify or "", tree))


def same_name_hint(tree: StagedTree, path: str) -> str:
    """The sentence that names the files of `tree` with the file name of `path`, or that states
    that no file has the name."""
    texts = MESSAGES.roadmap
    if same := tree.same_name(path):
        return texts.stage_path_same_name.format(names=", ".join(f"`{name}`" for name in same))
    return texts.stage_path_no_same_name


def _problem(number: int, place: _Place, path: str, tree: StagedTree, later: int | None) -> str:
    """The sentence for a missing path; `later` is the group after `number` that creates it."""
    texts = MESSAGES.roadmap
    where = texts.stage_path_places[place]
    if later is not None:
        return texts.stage_problem_path_later.format(
            group=number, path=path, place=where, later=later
        )
    hint = same_name_hint(tree, path)
    return texts.stage_problem_path.format(group=number, path=path, place=where, hint=hint)


def _first_creators(groups: Sequence[StageGroup]) -> dict[str, int]:
    """For each path, and each folder above it, that a group lists in `creates`: the number of
    the first group that does."""
    first: dict[str, int] = {}
    for number, group in enumerate(groups, start=1):
        for path in group.creates:
            for created in (path, *_folders_of(path)):
                first.setdefault(created, number)
    return first


# One clause of a task that adds something to one or more names: `Add the keyword `probes` to
# `check_proposal``, `add an argument to `a` and `b``. Outside a code span the clause holds no `.`,
# `:` or `;`, so a match never runs into the next sentence (#4467).
_ADD_TO: Final[re.Pattern[str]] = re.compile(
    r"\badd\s+(?P<what>(?:`[^`]*`|[^`.:;])+?)\s+to\s+"
    r"(?P<names>`[A-Za-z_]\w*`(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)`[A-Za-z_]\w*`)*)",
    re.IGNORECASE,
)
_NAME_SPAN: Final[re.Pattern[str]] = re.compile(r"`([A-Za-z_]\w*)`")
# The words of a clause that adds a parameter. A field, a member, a property or a method of a class
# is no parameter of a function.
_PARAMETER_WORD: Final[re.Pattern[str]] = re.compile(
    r"\b(?:parameter|argument|keyword)s?\b", re.IGNORECASE
)
# The added part of a clause that is one code span, alone or after `the` (#4529).
_ONE_SPAN: Final[re.Pattern[str]] = re.compile(r"(?:the\s+)?`([^`]+)`", re.IGNORECASE)


def _is_parameter_span(what: str) -> bool:
    """Whether `what`, the added part of a clause, is one code span that `ast` reads as the
    parameters of a `def`, as `name` or `name: Type = default`, and none of them is a constant in
    capitals. A decorator, an option and `UPPER = value` are no parameter (#4529)."""
    span = _ONE_SPAN.fullmatch(what)
    if span is None:
        return False
    match _parse(f"def _({span[1]}): pass").body:
        case [ast.FunctionDef(args=arguments)]:
            names = [
                arg.arg
                for arg in (
                    *arguments.posonlyargs,
                    *arguments.args,
                    arguments.vararg,
                    *arguments.kwonlyargs,
                    arguments.kwarg,
                )
                if arg is not None
            ]
            return bool(names) and not any(name.isupper() for name in names)
    return False


def changed_functions(groups: Sequence[StageGroup]) -> list[str]:
    """The names that task texts of `groups` add a parameter to: each name of a clause
    `add ... to `name`` whose added part says parameter, argument or keyword (#4467), or is one
    code span in parameter shape (#4529). The caller search drops a name that no module defines
    with `def`, as a class or an enum."""
    functions: list[str] = []
    for group in groups:
        for text in (group.test, group.implementation, group.documentation, group.process):
            for match in _ADD_TO.finditer(text or ""):
                what = match["what"]
                if _PARAMETER_WORD.search(what) is None and not _is_parameter_span(what):
                    continue
                functions.extend(_NAME_SPAN.findall(match["names"]))
    return list(dict.fromkeys(functions))


def caller_problems(groups: Sequence[StageGroup], tree: StagedTree) -> list[str]:
    """One sentence for each file calling a changed function that `groups` omit from `changes`."""
    if tree.source is None:
        return []
    functions = changed_functions(groups)
    if not functions:
        return []
    all_changes = {path for group in groups for path in group.changes}
    problems: list[str] = []
    for function in functions:
        for caller in tree.callers(function):
            if caller not in all_changes:
                problems.append(
                    MESSAGES.roadmap.stage_problem_missing_caller.format(
                        function=function, path=caller
                    )
                )
    return problems


def _manifest(path: str) -> PurePosixPath | None:
    """The manifest that `path` names, or None when it is no YAML manifest of `k8s/`."""
    manifest = PurePosixPath(path)
    if path.startswith(_MANIFEST_TOP) and manifest.suffix == _MANIFEST_SUFFIX:
        return manifest
    return None


def _is_test_module(path: str) -> bool:
    """Whether `path` is a test module under `tests/`."""
    name = PurePosixPath(path).name
    return path.startswith(_TESTS_TOP) and any(
        fnmatchcase(name, pattern) for pattern in _TEST_MODULE_PATTERNS
    )


def record_test_references(
    groups: Sequence[StageGroup], search: Callable[[str], Sequence[str]]
) -> dict[str, tuple[str, ...]]:
    """The tests under `tests/` that reference each YAML manifest of `k8s/` that `groups` change,
    keyed by the manifest path. A test references a manifest when it holds the file name of the
    manifest and the name of its folder: a test builds the path from its parts, so it holds no
    full-path string (#3972). `search` gives the files that hold a literal, as `git grep` does, and
    it runs once for each literal, so a manifest of a name that another manifest shares costs no
    second search."""
    found: dict[str, frozenset[str]] = {}

    def holders(literal: str) -> frozenset[str]:
        if literal not in found:
            found[literal] = frozenset(search(literal))
        return found[literal]

    references: dict[str, tuple[str, ...]] = {}
    for path in sorted({path for group in groups for path in group.changes}):
        manifest = _manifest(path)
        if manifest is None:
            continue
        tests = {test for test in holders(manifest.name) if _is_test_module(test)} & holders(
            manifest.parent.name
        )
        if tests:
            references[path] = tuple(sorted(tests))
    return references


def missing_reference_problems(
    groups: Sequence[StageGroup], references: Mapping[str, Sequence[str]]
) -> list[str]:
    """One sentence for each test of `references` that no group lists in `changes`, for a manifest
    that a group changes. A plan that leaves out a test of its manifest cannot edit it, and the
    implement job stops (#3972)."""
    changed = {path for group in groups for path in group.changes}
    texts = MESSAGES.roadmap
    return [
        texts.stage_problem_missing_perimeter_test.format(path=manifest, test=test)
        for manifest, tests in references.items()
        if manifest in changed
        for test in tests
        if test not in changed
    ]


def _is_source_module(path: str) -> bool:
    """Whether `path` is a Python module under `src/`."""
    return path.startswith(_SOURCE_TOP) and PurePosixPath(path).suffix == _MODULE_SUFFIX


def _dotted_name(path: str) -> str:
    """The dotted import name of the Python module `path` under `src/`; a package's
    `__init__.py` names the package."""
    return module_name(Path(path), Path(_SOURCE_TOP))


def _package_init(package: str) -> str:
    """The path of the `__init__.py` of the package `package` under `src/`."""
    return f"{_SOURCE_TOP}{package.replace('.', '/')}/__init__.py"


def _exporters(
    dotted: str, tree: StagedTree, read: Callable[[str], str], known: frozenset[str]
) -> set[str]:
    """`dotted` and each package above it whose `__init__.py` imports it, or imports a package
    that does: `from devops_cli.lang import MESSAGES` imports `devops_cli.lang.en.messages`."""
    parts = dotted.split(".")
    packages = [".".join(parts[:end]) for end in range(len(parts) - 1, 0, -1)]
    inits = {
        Path(init): _parse(read(init))
        for package in packages
        if (init := _package_init(package)) in tree.files
    }
    edges = build_import_graph(inits, root=Path(_SOURCE_TOP), known=known).edges
    exporters = {dotted}
    for package in packages:
        if edges.get(package, set()) & exporters:
            exporters.add(package)
    return exporters


def _importing_tests(
    exporters: Collection[str],
    read: Callable[[str], str],
    search: Callable[[str], Sequence[str]],
    known: frozenset[str],
) -> dict[str, frozenset[str]]:
    """The test modules that import one of `exporters`, at any depth of the test, each with the
    names of `exporters` that it imports. A test that imports `a.b.c` holds the words `a.b` and `c`
    in each import form, so `search` finds the candidates and `ast` reads their imports."""
    candidates: set[str] = set()
    for name in exporters:
        parent, _, leaf = name.rpartition(".")
        holders = set(search(name)) if not parent else set(search(parent)) & set(search(leaf))
        candidates |= {path for path in holders if _is_test_module(path)}
    trees = {Path(path): _parse(read(path)) for path in sorted(candidates)}
    edges = build_import_graph(trees, root=Path(), function_bodies=True, known=known).edges
    names = set(exporters)
    imported = {path: frozenset(edges[_test_name(path)] & names) for path in candidates}
    return {path: used for path, used in imported.items() if used}


def _test_name(path: str) -> str:
    """The dotted name of the test module `path`, from the root of the tree."""
    return module_name(Path(path), Path())


def _module_imports(path: str, read: Callable[[str], str], known: frozenset[str]) -> set[str]:
    """The modules that the module `path` under `src/` imports, at any depth of the module."""
    module = {Path(path): _parse(read(path))}
    edges = build_import_graph(module, root=Path(_SOURCE_TOP), function_bodies=True, known=known)
    return edges.edges[_dotted_name(path)]


def _mirror_of(module: str) -> tuple[str, str] | None:
    """The mirror test and the mirror folder of the module `module` under `src/`:
    `src/devops_cli/lang/en/messages.py` mirrors to `tests/lang/en/test_messages.py` in
    `tests/lang/en/`. A module at the top of the package has no mirror folder and no mirror test."""
    _package, *folders = PurePosixPath(module).relative_to(_SOURCE_TOP).parts
    if len(folders) < _MIRROR_MIN_PARTS:
        return None
    mirror = PurePosixPath(_TESTS_TOP, *folders)
    return str(mirror.with_name(f"test_{mirror.name}")), f"{mirror.parent}/"


def _nearest_first(module: str, direct: Mapping[str, frozenset[str]]) -> list[str]:
    """The tests of `direct`, which import the module `module` or a package that exports it,
    nearest first: the mirror test, a test that imports the module by its own name, a test in the
    mirror folder, then the rest. Tests of equal closeness keep path order."""
    mirror, folder = _mirror_of(module) or ("", "")
    dotted = _dotted_name(module)

    def closeness(test: str) -> tuple[bool, bool, bool, str]:
        return (
            test != mirror,
            dotted not in direct[test],
            not (folder and test.startswith(folder)),
            test,
        )

    return sorted(direct, key=closeness)


def record_module_tests(
    groups: Sequence[StageGroup], tree: StagedTree, search: Callable[[str], Sequence[str]]
) -> dict[str, tuple[str, ...]]:
    """The tests under `tests/` of each existing Python module under `src/` that a behavior group
    changes, keyed by the module path (#3414). A test belongs to a module when it imports the
    module, or a package whose `__init__.py` imports it, at any depth of the test (#4467):
    `tests/roadmap/implement/test_roadmap_implement_step.py` imports
    `devops_cli.roadmap.step_files`. A test of another module that the plan changes, and that
    imports the module, runs it too: a group that changes `follow.py` and the messages that it shows
    names the test of `follow.py`, and that test comes after each test that imports `follow.py`.
    The tests of a module come nearest first (#4519): the mirror test, a test that imports the
    module by its own name, a test in the mirror folder, then the rest, each group in path order,
    so the problem of the gate names the test that the reader of the module expects. A test that holds the name in a string or a path, as
    `tests/commands/test_new.py` holds `src/devops_cli/lang/en/messages.py`, is no test of the
    module. `search` gives the files that hold a literal as a word, as `git grep -F -w` does, and
    it runs once for each literal. A tree that cannot read its files records nothing, so the gate
    judges no module."""
    read = tree.reader
    if read is None:
        return {}
    found: dict[str, tuple[str, ...]] = {}

    def holders(literal: str) -> tuple[str, ...]:
        if literal not in found:
            found[literal] = tuple(search(literal))
        return found[literal]

    known = frozenset(_dotted_name(path) for path in tree.files if _is_source_module(path))
    changed = sorted(
        path
        for path in {path for group in groups if group.kind == "behavior" for path in group.changes}
        if _is_source_module(path) and path in tree.files
    )
    exporters = {path: _exporters(_dotted_name(path), tree, read, known) for path in changed}
    direct = {path: _importing_tests(exporters[path], read, holders, known) for path in changed}
    imports = {path: _module_imports(path, read, known) for path in changed}
    modules: dict[str, tuple[str, ...]] = {}
    for path in changed:
        users = [other for other in changed if imports[other] & exporters[path]]
        own = _nearest_first(path, direct[path])
        users_only = {test for other in users for test in direct[other]}.difference(own)
        if tests := (*own, *sorted(users_only)):
            modules[path] = tests
    return modules


def _unnamed_module_tests(
    group: StageGroup,
    named: set[str],
    created: set[str],
    module_tests: Mapping[str, Sequence[str]],
) -> list[tuple[str, str]]:
    """Each module that `group` changes whose test it names nowhere, with the test to name, in the
    order of `changes` (#5068). A test that an earlier module asks for counts as named, so a later
    module that the test also runs asks for no second test, and a repair that names every test of
    the list passes the group in one round."""
    asked = set(named)
    missing: list[tuple[str, str]] = []
    for path in group.changes:
        tests = [test for test in module_tests.get(path, ()) if test not in created]
        if tests and not any(test in asked for test in tests):
            missing.append((path, tests[0]))
            asked.add(tests[0])
    return missing


def existing_test_problems(
    groups: Sequence[StageGroup],
    tree: StagedTree,
    module_tests: Mapping[str, Sequence[str]],
) -> list[str]:
    """One sentence for each module that a behavior group changes and whose existing test the group
    names nowhere (#3414), so that one repair names every test (#5068). A group names a test when
    it lists it in `reads`, in `changes`, in a task code span or in `verify`: a group reads a test
    that pins a module it changes and must not edit it. A test that a group lists in `creates` is
    no existing test. A module with no test of `module_tests` passes, so a caller that recorded
    none judges nothing."""
    created = {path for group in groups for path in group.creates}
    texts = MESSAGES.roadmap
    problems: list[str] = []
    for number, group in enumerate(groups, start=1):
        if group.kind != "behavior":
            continue
        named = {path for _place, path in _named(group, tree)}
        problems.extend(
            texts.stage_problem_missing_module_test.format(group=number, path=path, test=test)
            for path, test in _unnamed_module_tests(group, named, created, module_tests)
        )
    return problems


def path_problems(
    groups: Sequence[StageGroup],
    tree: StagedTree,
    references: Mapping[str, Sequence[str]] | None = None,
    *,
    change: str = "",
) -> list[str]:
    """One sentence for each path, named in `groups`, that `tree` lacks and that no group up to
    the one that names it creates. A path is named once, at its first place. When a later group
    creates the path, the sentence names that group too. `references` is the record of the tests
    that each changed manifest reaches; None means the caller recorded no reference, so the check
    judges no test of a manifest."""
    creators = _first_creators(groups)
    created: set[str] = set()
    reported: set[str] = set()
    problems: list[str] = []
    own_folder = posixpath.normpath(f"{_CHANGES_DIRECTORY}/{change}") if change else None
    for number, group in enumerate(groups, start=1):
        for path in group.creates:
            created |= {path, *_folders_of(path)}
        # A group never writes the change folder or a file under it (#3285): the check holds even
        # for a path the tree holds or a group lists in `creates`, which outrank the next checks.
        for written in change_folder_paths([*group.changes, *group.creates]):
            if written in reported:
                continue
            if own_folder and (written == own_folder or written.startswith(f"{own_folder}/")):
                continue
            reported.add(written)
            problems.append(MESSAGES.roadmap.stage_bad_change_path.format(path=written))
        for place, named in _named(group, tree):
            path = named.rstrip("/")
            if own_folder and (path == own_folder or path.startswith(f"{own_folder}/")):
                continue
            exists = tree.has_folder(path) if named.endswith("/") else tree.has(path)
            if path in reported or path in created or exists:
                continue
            reported.add(path)
            problems.append(_problem(number, place, path, tree, creators.get(path)))
    problems.extend(caller_problems(groups, tree))
    if references is not None:
        problems.extend(missing_reference_problems(groups, references))
    return problems


def _is_own_change(path: str, own_folder: str) -> bool:
    norm = posixpath.normpath(path)
    return norm == own_folder or norm.startswith(f"{own_folder}/")


def own_change_problems(groups: Sequence[StageGroup], change: str = "") -> list[str]:
    """The problems when a group's changes or tasks name paths of the plan's own change folder."""
    if not change:
        return []
    own_folder = posixpath.normpath(f"{_CHANGES_DIRECTORY}/{change}")
    problems: list[str] = []
    seen_changes: set[str] = set()
    seen_tasks: set[tuple[int, str]] = set()

    for number, group in enumerate(groups, start=1):
        for path in group.changes:
            if path not in seen_changes and _is_own_change(path, own_folder):
                seen_changes.add(path)
                problems.append(
                    MESSAGES.roadmap.stage_own_change_changes.format(path=path, change=change)
                )
        for text in (group.test, group.implementation, group.documentation, group.process):
            for span in code_spans(text or ""):
                key = (number, span)
                if key not in seen_tasks and _is_own_change(span, own_folder):
                    seen_tasks.add(key)
                    problems.append(
                        MESSAGES.roadmap.stage_own_change_task.format(group=number, path=span)
                    )
    return problems
