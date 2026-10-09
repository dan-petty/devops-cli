"""Unit tests for Architecture Spec verification (devops ai spec)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ai.spec.verifier import verify_architecture_spec
from devops_cli.commands.ai import app

runner = CliRunner()


def test_verify_architecture_spec_dry_run() -> None:
    report = verify_architecture_spec(dry_run=True)
    assert report.total_rules >= 1
    assert report.passed_rules >= 1
    assert report.failed_rules == 0


def test_verify_architecture_spec_live(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    good_file = src / "good.py"
    good_file.write_text("def valid_func():\n    return 42\n")

    report = verify_architecture_spec(target_dir=tmp_path)
    assert report.failed_rules == 0
    assert report.passed_rules >= 1


def test_verify_architecture_spec_violations(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    bad_file = src / "bad.py"
    deep_code = (
        "import telnetlib\n"
        "from cgi import parse\n"
        "def deep_nesting():\n"
        "    if 1:\n"
        "        if 2:\n"
        "            if 3:\n"
        "                if 4:\n"
        "                    if 5:\n"
        "                        if 6:\n"
        "                            return True\n"
    )
    bad_file.write_text(deep_code)

    report = verify_architecture_spec(target_dir=tmp_path)
    assert report.failed_rules >= 1
    assert any(r.rule_type == "max_indentation" and not r.passed for r in report.rule_results)
    assert any(r.rule_type == "forbidden_import" and not r.passed for r in report.rule_results)


_DEEP_IN_EXCEPT = """
def handled():
    try:
        return 0
    except ValueError:
        if 1:
            if 2:
                if 3:
                    if 4:
                        return 1
"""

_FOUR_IFS_IN_TRY = """
def guarded():
    try:
        if 1:
            if 2:
                if 3:
                    if 4:
                        return 1
    except ValueError:
        return 0
"""


@pytest.mark.parametrize(
    ("source", "indentation"),
    [
        pytest.param(
            _DEEP_IN_EXCEPT,
            [(False, "src/mod.py:handled", "Function depth 6 exceeds limit 5.")],
            id="an-except-handler-opens-a-level",
        ),
        pytest.param(
            _FOUR_IFS_IN_TRY,
            [(True, "src/mod.py", "Compliant with <6 indentation levels.")],
            id="a-try-body-opens-none",
        ),
    ],
)
def test_the_indentation_rule_counts_nesting_as_the_commit_hook_does(
    tmp_path: Path, source: str, indentation: list[tuple[bool, str, str]]
) -> None:
    """An `except` block opens a level and a `try` body does not, as in `core.code_metrics`."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "mod.py").write_text(source, encoding="utf-8")

    report = verify_architecture_spec(target_dir=tmp_path)

    assert [
        (rule.passed, rule.target_path, rule.details)
        for rule in report.rule_results
        if rule.rule_type == "max_indentation"
    ] == indentation


def test_cli_ai_spec_dry_run() -> None:
    result = runner.invoke(app, ["spec", "--dry-run"])
    assert result.exit_code == 0
    assert "DRY_RUN" in result.stdout


def test_cli_ai_spec_live(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "test.py").write_text("def fn(): return 1\n")
    result = runner.invoke(app, ["spec", "--target", str(tmp_path)])
    assert result.exit_code == 0
    assert "Architecture specification verified" in result.stdout
