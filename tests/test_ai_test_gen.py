"""Tests for unit test scaffold generator and devops ai test-gen CLI (#856)."""

from __future__ import annotations

import ast

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import ai_test_gen
from devops_cli.ai.test_gen import synthesize_unit_tests
from devops_cli.commands.ai import app as ai_app

pytest_plugins = ["pytester"]

runner = CliRunner()


def _test_function_bodies(code: str) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    tree = ast.parse(code)
    return [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


def test_test_gen_emits_failing_scaffolds_without_presence_assertions(
    pytester: pytest.Pytester,
) -> None:
    """Verify generated scaffolds parse, contain pytest.fail without presence checks, and fail in pytester (#856)."""
    sample = pytester.makepyfile(
        math_ops=(
            "def multiply(x: int, y: int) -> int:\n"
            "    return x + y\n\n"
            "def divide(x: int, y: int) -> float:\n"
            "    return x / y\n"
        )
    )

    suite = synthesize_unit_tests(sample)
    test_fns = _test_function_bodies(suite.test_code)
    has_assert = any(isinstance(child, ast.Assert) for fn in test_fns for child in ast.walk(fn))
    all_end_with_pytest_fail = all(
        f'pytest.fail("expected behaviour of {fn_name} not written")' in suite.test_code
        or f"pytest.fail('expected behaviour of {fn_name} not written')" in suite.test_code
        for fn_name in ("multiply", "divide")
    )

    pytester.makepyfile(test_math_ops=suite.test_code)
    run_result = pytester.runpytest_inprocess(
        "-o", "addopts=", "-p", "no:cacheprovider", "-p", "no:asyncio"
    )
    outcomes = run_result.parseoutcomes()

    suite_filt = synthesize_unit_tests(sample, function_filter="multiply")
    empty_sample = pytester.path / "empty.py"
    empty_sample.write_text("", encoding="utf-8")
    suite_empty = synthesize_unit_tests(empty_sample)
    empty_fns = _test_function_bodies(suite_empty.test_code)

    bad_sample = pytester.path / "bad.py"
    bad_sample.write_text("def (invalid python", encoding="utf-8")
    suite_bad = synthesize_unit_tests(bad_sample)

    res_cli = runner.invoke(ai_app, ["test-gen", str(sample)])
    res_dry = runner.invoke(ai_app, ["test-gen", str(sample), "--dry-run"])
    mcp_doc = ai_test_gen.__doc__ or ""

    assert (
        suite.test_count,
        len(test_fns),
        has_assert,
        "hasattr" in suite.test_code,
        "is not None" in suite.test_code,
        all_end_with_pytest_fail,
        outcomes.get("failed"),
        outcomes.get("passed", 0),
        suite.validation_status,
        suite.to_dict()["validation_status"],
        suite_filt.test_count,
        len(empty_fns),
        "pytest.fail" in suite_empty.test_code,
        "is not None" in suite_empty.test_code,
        suite_bad.test_count,
        res_cli.exit_code,
        "scaffold" in res_cli.output.lower(),
        "Synthesized" in res_cli.output,
        res_dry.exit_code,
        "Synthesized" in res_dry.output,
        "scaffold" in mcp_doc.lower(),
        "Synthesize" in mcp_doc,
    ) == (
        2,
        2,
        False,
        False,
        False,
        True,
        2,
        0,
        "UNEXECUTED",
        "UNEXECUTED",
        1,
        1,
        True,
        False,
        1,
        0,
        True,
        False,
        0,
        False,
        True,
        False,
    )
