"""The rows of `devops ci` that run the checks of `tests/gate` (#2164)."""

from __future__ import annotations

import importlib

import pytest

from devops_cli.commands.ci import get_check_spec, get_check_specs

_GATE_ROWS = {
    "k8s": "k8s",
    "test-tree": "tree",
    "startup-imports": "startup_imports",
    "swallowed-failures": "swallowed_failures",
    "domain": "configured_domain",
    "roadmap-stage-eval-commits": "roadmap_stage_eval_commits",
}


@pytest.mark.parametrize(("row", "module"), sorted(_GATE_ROWS.items()))
def test_a_gate_row_runs_the_main_of_its_module(row: str, module: str) -> None:
    """The row starts `tests.gate.<module>.main` in the interpreter of the project, and the module has it."""
    spec = get_check_spec(row)

    assert (spec.cmd[:4], f"tests.gate.{module} import main" in spec.cmd[4], spec.also_cmds) == (
        ["uv", "run", "python", "-c"],
        True,
        [],
    )
    assert callable(importlib.import_module(f"tests.gate.{module}").main)


def test_the_gate_rows_have_a_title_that_names_what_they_check() -> None:
    """Each row has its own title, so the summary of `devops ci` tells them apart."""
    titles = [get_check_spec(row).display_title for row in _GATE_ROWS]

    assert (len(set(titles)), all(titles)) == (len(_GATE_ROWS), True)


def test_the_gate_rows_come_last_in_the_table_in_this_order() -> None:
    """The rows are in the table of `devops ci`, after the rows that were there."""
    names = [spec.name for spec in get_check_specs()]

    assert names[-len(_GATE_ROWS) :] == list(_GATE_ROWS)
