"""No new test reads a committed manifest or config file (#6060).

A test checks the source code of the project. No test asserts a value of a manifest or of a
config file, such as a version, a digest, a model, a limit or a key: an update of the value, often
by Renovate, then fails a test although no code changed. The schema and policy tools of CI check
the form of these files (docs/TESTING.md, "Which change gets a test").

The check finds each test that reads such a file: a path built from `REPO_ROOT` (or the `K8S`,
`TREE` and `APPLICATIONS` of `tests.support.k8s_tree`) whose first part is a config location, a
relative `Path` of a config location, or a string of a config path in a module that reads the
repository. A module-level name, helper or fixture that reads one taints each test that uses it.
`config_reads.toml` holds, for each module, the count of its tests that still read one: the cases
the owner has to decide, and the tests of code that take a committed file as input and assert no
value of it. The counts only fall: a module above or below its count fails the check.
"""

from __future__ import annotations

import ast
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Final, TypeGuard

from tests.support.paths import REPO_ROOT

# The top-level paths of the repository that hold manifests and config, and the prefixes of the
# ones that come in families (`Dockerfile.x`, `.trivyignore-x`).
CONFIG_ROOTS: Final[frozenset[str]] = frozenset(
    {
        ".bandit",
        ".claude",
        ".devcontainer",
        ".devops",
        ".gh-dash.yml",
        ".github",
        ".mcp.json",
        ".node-version",
        ".pre-commit-config.yaml",
        ".python-version",
        ".tuicrignore",
        ".vale.ini",
        "config.example.yaml",
        "docker",
        "k8s",
        "kilo.jsonc",
        "pyproject.toml",
        "release-please-config.json",
        "tf",
        "uv.lock",
    }
)
CONFIG_ROOT_PREFIXES: Final[tuple[str, ...]] = ("Dockerfile", ".trivyignore")
# The names that stand for the repository root, and those that stand for its `k8s` folder.
_REPO_NAMES: Final[frozenset[str]] = frozenset({"REPO_ROOT"})
# The names of `tests.support.k8s_tree` that stand for the `k8s` folder of the repository.
_K8S_NAMES: Final[frozenset[str]] = frozenset({"K8S", "TREE", "APPLICATIONS"})
_K8S_TREE_MODULE: Final[str] = "tests.support.k8s_tree"
_PATH_TYPES: Final[frozenset[str]] = frozenset({"Path", "PurePosixPath", "PurePath"})
ALLOW_LIST: Final[Path] = REPO_ROOT / "tests" / "gate" / "tree_checks" / "config_reads.toml"
_SKIPPED_PARTS: Final[frozenset[str]] = frozenset({"support", "fixtures", "golden", "gate"})


def is_config_path(text: str) -> bool:
    """`text`, a path relative to the repository root, names a manifest or a config file. A
    Markdown file is a document, not config."""
    path = text.strip().removeprefix("./")
    first = path.split("/", 1)[0]
    return not path.endswith(".md") and (
        first in CONFIG_ROOTS or first.startswith(CONFIG_ROOT_PREFIXES)
    )


def _literal_path(node: ast.expr, k8s_names: frozenset[str]) -> str | None:
    """The path that `node` builds from a repository name, with `*` for a part that is not a
    string literal, or None when `node` builds no such path."""
    parts: list[ast.expr] = []
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        parts.append(node.right)
        node = node.left
    parts.reverse()
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "joinpath"
    ):
        parts = [*node.args, *parts]
        node = node.func.value
    if not isinstance(node, ast.Name):
        return None
    texts = [
        part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "*"
        for part in parts
    ]
    if node.id in k8s_names:
        return "/".join(["k8s", *texts])
    if node.id not in _REPO_NAMES or not texts or texts[0] == "*":
        return None
    return "/".join(texts)


def _path_readers(tree: ast.Module) -> frozenset[str]:
    """The module-level functions that build a path under the repository root from a parameter,
    such as `def _data(path): return REPO_ROOT / path`."""
    readers = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        params = {a.arg for a in [*node.args.args, *node.args.kwonlyargs]}
        if any(
            isinstance(first, ast.Name) and first.id in params
            for first in map(_first_repository_part, ast.walk(node))
        ):
            readers.add(node.name)
    return frozenset(readers)


def _first_repository_part(node: ast.AST) -> ast.expr | None:
    """The first part after `REPO_ROOT` of a path that `node` builds, or None."""
    first: ast.expr | None = None
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        first, node = node.right, node.left
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "joinpath"
        and node.args
    ):
        first, node = node.args[0], node.func.value
    return first if isinstance(node, ast.Name) and node.id in _REPO_NAMES else None


def _is_config_literal(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (is_config_path(node.value))
    )


def _is_read_site(node: ast.AST, readers: frozenset[str], k8s_names: frozenset[str]) -> bool:
    """`node` builds the path of a committed config file, passes one to a path reader of the
    module, or names a reader of `k8s/`."""
    if isinstance(node, ast.BinOp) or (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "joinpath"
    ):
        path = _literal_path(node, k8s_names)
        return path is not None and is_config_path(path)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.args:
        if node.func.id in readers:
            return _is_config_literal(node.args[0])
        if node.func.id in _PATH_TYPES and _is_config_literal(node.args[0]):
            text = str(getattr(node.args[0], "value", ""))
            return "/" in text.strip("/")
    return isinstance(node, ast.Name) and node.id in k8s_names


def _top_level_names(node: ast.stmt) -> list[str]:
    """The names a module-level statement binds."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return [node.name]
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign):
        targets = node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        targets = [node.target]
    return [n.id for t in targets for n in ast.walk(t) if isinstance(n, ast.Name)]


def _uses(node: ast.AST) -> set[str]:
    """The names `node` loads, and the parameters of each function in it (fixtures by name)."""
    used = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
    for n in ast.walk(node):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            used.update(a.arg for a in [*n.args.args, *n.args.kwonlyargs])
    return used


def _is_test(node: ast.stmt) -> TypeGuard[ast.FunctionDef | ast.AsyncFunctionDef]:
    return isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
        "test"
    )


def _tests(tree: ast.Module) -> Iterable[tuple[str, ast.AST]]:
    """Each test function of a module, by its pytest name without the file."""
    for node in tree.body:
        if _is_test(node):
            yield node.name, node
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            yield from (
                (f"{node.name}::{member.name}", member) for member in node.body if _is_test(member)
            )


def config_reading_tests(tree: ast.Module) -> list[str]:
    """The tests of a module that read a committed manifest or config file, directly or through
    a module-level name, helper or fixture of the module."""
    readers = _path_readers(tree)
    k8s_names = frozenset(
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == _K8S_TREE_MODULE
        for alias in node.names
        if alias.name in _K8S_NAMES
    )
    statements = {
        name: statement for statement in tree.body for name in _top_level_names(statement)
    }
    tainted = {
        name
        for name, statement in statements.items()
        if not name.startswith("test")
        and any(_is_read_site(n, readers, k8s_names) for n in ast.walk(statement))
    }
    changed = True
    while changed:
        changed = False
        for name, statement in statements.items():
            if name not in tainted and not name.startswith("test") and _uses(statement) & tainted:
                tainted.add(name)
                changed = True
    found = []
    for name, test in _tests(tree):
        direct = any(_is_read_site(n, readers, k8s_names) for n in ast.walk(test))
        if direct or _uses(test) & tainted:
            found.append(name)
    return found


def config_reads(trees: Mapping[Path, ast.Module], root: Path) -> set[str]:
    """`path::test` for each test under `tests/` that reads a committed config file. Support,
    fixture, golden and gate modules and conftests are no test modules."""
    return {
        f"{path.relative_to(root).as_posix()}::{name}"
        for path, tree in trees.items()
        if path.name.startswith("test_")
        and not _SKIPPED_PARTS & set(path.relative_to(root).parts[1:-1])
        for name in config_reading_tests(tree)
    }


def allowed_reads(path: Path = ALLOW_LIST) -> dict[str, int]:
    """The count of tests that `config_reads.toml` lets each module hold that read a committed
    config file."""
    return dict(tomllib.loads(path.read_text(encoding="utf-8"))["modules"])


def read_counts(reads: Iterable[str]) -> dict[str, int]:
    """The count of tests of each module among `reads`, which are `path::test` names."""
    return dict(Counter(read.split("::", 1)[0] for read in reads))


def count_problems(found: Mapping[str, int], allowed: Mapping[str, int]) -> list[str]:
    """Each module whose count of tests that read config differs from its entry: a higher count
    is a new test, and a lower count is an entry to lower (the list only falls)."""
    return [
        f"{module}: {found.get(module, 0)} tests read config, the list allows "
        f"{allowed.get(module, 0)}"
        for module in sorted(found.keys() | allowed.keys())
        if found.get(module, 0) != allowed.get(module, 0)
    ]


def check_no_new_test_reads_a_committed_manifest_or_config_file(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """Each module holds exactly the count of tests that read a committed config file that
    `config_reads.toml` names for it, so no new test reads one and the list only falls (#6060)."""
    found = read_counts(config_reads(parsed_test_trees, REPO_ROOT))
    problems = count_problems(found, allowed_reads())
    assert problems == [], (
        f"{problems}. A test checks project source code with input that it builds; CI's schema "
        "and policy tools check the form of manifests and config, and no test asserts a value of "
        "them (docs/TESTING.md, 'Which change gets a test'). When a test that read config goes, "
        f"lower its count in {ALLOW_LIST.name}."
    )


def check_a_new_read_and_a_removed_read_both_change_the_count() -> None:
    """A module above its entry and a module below it are both named (#6060)."""
    found = read_counts(
        ["tests/a/test_a.py::test_1", "tests/a/test_a.py::test_2", "tests/b/test_b.py::test_1"]
    )

    assert count_problems(found, {"tests/a/test_a.py": 1, "tests/c/test_c.py": 1}) == [
        "tests/a/test_a.py: 2 tests read config, the list allows 1",
        "tests/b/test_b.py: 1 tests read config, the list allows 0",
        "tests/c/test_c.py: 0 tests read config, the list allows 1",
    ]


def check_a_test_that_reads_a_config_file_through_a_helper_is_found() -> None:
    """A read through a constant, a helper or a fixture of the module counts, a path that a test
    builds under `tmp_path` does not, and a support module is no test module (#6060)."""
    root = Path("/repo")
    sources = {
        "tests/a/test_direct.py": (
            "from tests.support.paths import REPO_ROOT\n"
            "def test_pin():\n"
            "    assert (REPO_ROOT / 'k8s' / 'app.yaml').read_text()\n"
        ),
        "tests/a/test_helper.py": (
            "import pytest\n"
            "from tests.support.paths import REPO_ROOT\n"
            "MANIFEST = REPO_ROOT.joinpath('.github', 'renovate.json')\n"
            "def _load():\n"
            "    return MANIFEST.read_text()\n"
            "@pytest.fixture\n"
            "def doc():\n"
            "    return _load()\n"
            "def test_by_fixture(doc):\n"
            "    assert doc\n"
            "def test_by_helper():\n"
            "    assert _load()\n"
            "def test_none(tmp_path):\n"
            "    assert not (tmp_path / 'k8s').exists()\n"
        ),
        "tests/a/test_literal.py": (
            "from pathlib import Path\n"
            "from tests.support.paths import REPO_ROOT\n"
            "def _data(path):\n"
            "    return (REPO_ROOT / path).read_text()\n"
            "def test_template():\n"
            "    assert _data('k8s/devops/configmap.example.yaml')\n"
            "def test_docs():\n"
            "    assert (REPO_ROOT / 'docs' / 'TESTING.md').read_text()\n"
            "class TestManifests:\n"
            "    def test_workflow(self):\n"
            "        assert Path('.github/workflows/ci.yml').read_text()\n"
        ),
        "tests/a/test_tree.py": (
            "from tests.support.k8s_tree import TREE\n"
            "def test_values():\n"
            "    assert TREE.path('llm')\n"
        ),
        "tests/support/reader.py": (
            "from tests.support.paths import REPO_ROOT\n"
            "def test_like():\n"
            "    return REPO_ROOT / 'k8s'\n"
        ),
    }
    trees = {root / path: ast.parse(text) for path, text in sources.items()}

    assert sorted(config_reads(trees, root)) == [
        "tests/a/test_direct.py::test_pin",
        "tests/a/test_helper.py::test_by_fixture",
        "tests/a/test_helper.py::test_by_helper",
        "tests/a/test_literal.py::TestManifests::test_workflow",
        "tests/a/test_literal.py::test_template",
        "tests/a/test_tree.py::test_values",
    ]
