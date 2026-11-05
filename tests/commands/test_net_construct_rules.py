"""The `constructs` row of `devops ci` runs the scan, the rule tests and the gate checks (#1107, #1902).

The rule tests (`ast-grep test`), the scan of one violation of each rule in each tree, and the
checks of the committed files run in the row itself (#2164), so no test here starts ast-grep or
Ruff.
"""

from __future__ import annotations

from devops_cli.commands.ci import get_check_spec
from devops_cli.config.constants import CONST_AST_GREP_SCAN_ARGS
from tests.gate.construct_gate import CONST_BANNED_HAND_ROLLED_APIS


def test_ci_constructs_row_matches_constants() -> None:
    """The constructs row in devops ci runs the scan with CONST_AST_GREP_SCAN_ARGS."""
    spec = get_check_spec("constructs")
    assert spec.cmd == ["uv", "run", "ast-grep", *CONST_AST_GREP_SCAN_ARGS]
    assert len(CONST_BANNED_HAND_ROLLED_APIS) == 4


def test_the_constructs_row_runs_the_rule_tests_and_the_gate_check() -> None:
    """`ast-grep test` and the construct gate check join the row, in that order."""
    spec = get_check_spec("constructs")

    assert [cmd[2:4] if cmd[2] == "ast-grep" else cmd[2:3] for cmd in spec.also_cmds] == [
        ["ast-grep", "test"],
        ["python"],
    ]
    assert "construct_gate" in spec.also_cmds[1][-1]


def test_the_lint_row_runs_the_ruff_configuration_check() -> None:
    """The ruff configuration check joins the lint row."""
    spec = get_check_spec("lint")

    assert "ruff_config" in spec.also_cmds[0][-1]
