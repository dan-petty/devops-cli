"""The table of edges that `devops new test` reads names real seams and real shared fixtures
(#3204)."""

from __future__ import annotations

import ast
import importlib.util

from devops_cli.scaffold.edges import EDGE_FIXTURES, edge_fixtures
from tests.support.paths import TESTS_ROOT
from tests.support.trees import parse_python_file


def _shared_fixtures() -> set[str]:
    """The names of the pytest fixtures that `tests/support/` defines."""
    names: set[str] = set()
    for path in (TESTS_ROOT / "support").rglob("*.py"):
        for node in ast.walk(parse_python_file(path)):
            if isinstance(node, ast.FunctionDef) and any(
                ast.unparse(decorator).startswith("pytest.fixture")
                for decorator in node.decorator_list
            ):
                names.add(node.name)
    return names


def test_each_seam_of_the_table_is_a_module() -> None:
    """A renamed or deleted seam module leaves no stale row."""
    missing = [seam for seam, _ in EDGE_FIXTURES if importlib.util.find_spec(seam) is None]

    assert missing == []


def test_each_fixture_of_the_table_is_a_shared_fixture() -> None:
    """A generated test never asks for a fixture that does not exist."""
    unknown = sorted({fixture for _, fixture in EDGE_FIXTURES} - _shared_fixtures())

    assert unknown == []


def test_a_module_reaches_the_edges_whose_seams_it_imports() -> None:
    """A plain import, a from-import and a submodule import of a seam each reach its edge, and a
    module that imports no seam reaches none."""
    source = (
        "import devops_cli.http.entry\n"
        "from devops_cli.roadmap.stores import store\n"
        "from devops_cli.github.session import get_github_session\n"
        "import json\n"
    )

    assert (edge_fixtures(source), edge_fixtures("import json\n")) == (
        ["github_api", "web", "roadmap_store"],
        [],
    )
