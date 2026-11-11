"""The fixtures `project` and `tree` each have one definition in the test modules (#2173)."""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

from tests.support.paths import REPO_ROOT

# The fixture names that two test modules must not both define (#2173).
_SHARED_FIXTURE_NAMES = ("project", "tree")


def _is_fixture_def(node: ast.FunctionDef) -> bool:
    """`node` has a `fixture` or `pytest.fixture` decorator, called or not."""
    return any(
        (isinstance(d, ast.Name) and d.id == "fixture")
        or (isinstance(d, ast.Attribute) and d.attr == "fixture")
        or (
            isinstance(d, ast.Call)
            and isinstance(d.func, (ast.Name, ast.Attribute))
            and (
                getattr(d.func, "id", None) == "fixture"
                or getattr(d.func, "attr", None) == "fixture"
            )
        )
        for d in node.decorator_list
    )


def _fixture_definitions(trees: Mapping[Path, ast.Module], root: Path) -> dict[str, list[str]]:
    """For each name of `_SHARED_FIXTURE_NAMES`, the path of each module that defines a fixture
    of that name. Support modules and conftests are not test modules, so they are not read."""
    found: dict[str, list[str]] = {name: [] for name in _SHARED_FIXTURE_NAMES}
    for path, tree in sorted(trees.items()):
        relative = path.relative_to(root)
        if "support" in relative.parts or path.name == "conftest.py":
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name in found and _is_fixture_def(node):
                found[node.name].append(relative.as_posix())
    return found


def check_project_and_tree_fixtures_are_distinct(
    parsed_test_trees: dict[Path, ast.Module],
) -> None:
    """No two test modules define a fixture named `project`, and no two define a fixture named
    `tree` (#2173)."""
    for name, paths in _fixture_definitions(parsed_test_trees, REPO_ROOT).items():
        assert len(paths) <= 1, f"Multiple {name!r} fixtures found: {paths}"


def check_a_second_project_or_tree_fixture_is_named_with_its_paths() -> None:
    """Two test modules that define a `project` fixture are both named, and a `tree` fixture in a
    support module or a conftest is not read (#2173)."""
    root = Path("/repo")
    sources = {
        "tests/a/test_a.py": "@pytest.fixture\ndef project(): ...\n",
        "tests/b/test_b.py": "@fixture(scope='module')\ndef project(): ...\n",
        "tests/c/test_c.py": "def tree(): ...\n",
        "tests/support/trees.py": "@pytest.fixture\ndef tree(): ...\n",
        "tests/conftest.py": "@pytest.fixture\ndef tree(): ...\n",
    }
    trees = {root / path: ast.parse(text) for path, text in sources.items()}

    assert _fixture_definitions(trees, root) == {
        "project": ["tests/a/test_a.py", "tests/b/test_b.py"],
        "tree": [],
    }
