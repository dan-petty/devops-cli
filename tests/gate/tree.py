"""The checks of the Python files of the repository: the `test-tree` row of `devops ci` (#2164).

Each module of `tests/gate/tree_checks` holds functions named `check_*` that read the syntax
trees of the files under `src/` and `tests/`. The row parses each file once and runs every check
over the same trees, where each pytest worker parsed them again.
"""

from __future__ import annotations

import tests.gate.tree_checks as tree_checks
from tests.gate.runner import main as run_checks
from tests.support.trees import parse_repo_trees, parse_source_trees, parse_test_trees


def main(argv: list[str] | None = None) -> int:
    """Run the checks, and return 1 when one fails."""
    fixtures = {
        "parsed_source_trees": parse_source_trees,
        "parsed_test_trees": parse_test_trees,
        "parsed_repo_trees": parse_repo_trees,
    }
    return run_checks("test-tree", tree_checks, fixtures)
