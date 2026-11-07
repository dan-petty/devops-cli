"""The adapters of the model rows import their job modules at module level, so the main thread of
the service imports pydantic_ai before its worker threads start (#2535, #2659).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from tests.support.paths import REPO_ROOT

pytestmark = pytest.mark.usefixtures("keyring_store")


@pytest.mark.parametrize(
    ("module", "adapter_name"),
    [
        ("devops_cli.roadmap.refine.refine", "_run_refine_adapter"),
        ("devops_cli.roadmap.stage.stage", "_run_stage_adapter"),
    ],
)
def test_the_model_job_imports_are_at_module_level_not_lazy_in_the_adapter(
    parsed_source_trees: dict[Path, ast.Module], module: str, adapter_name: str
) -> None:
    """The refine and stage adapters import their modules at module level, so the Service's main
    thread imports pydantic_ai before its worker threads start, and two workers never import it
    for the first time at once and deadlock on the Python 3.14 import lock (#2535, #2659)."""
    tree = parsed_source_trees[REPO_ROOT / "src" / "devops_cli" / "roadmap" / "run.py"]

    module_level = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and (node.module or "") == module
    ]
    adapter = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == adapter_name
    )
    local = [
        node
        for node in ast.walk(adapter)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(module)
    ]

    assert (len(module_level), local) == (1, [])


def test_the_alternatives_adapter_imports_the_job_at_module_level_not_lazily(
    parsed_source_trees: dict[Path, ast.Module],
) -> None:
    """The job imports pydantic_ai, so the Service's main thread imports it before its worker
    threads start, as it does for refine (#2535)."""
    tree = parsed_source_trees[REPO_ROOT / "src" / "devops_cli" / "roadmap" / "run.py"]
    wanted = "devops_cli.roadmap.alternatives"

    module_level = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and (node.module or "") == wanted
    ]
    local = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and (node.module or "") == wanted
        and node not in module_level
    ]

    assert (len(module_level), local) == (1, [])
