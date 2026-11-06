"""Tests for `devops ci --shard` and `--shards`: the test row runs one part of the suite (#3050).

The `Tests & Coverage` job of CI runs the test row in shards on separate runners, so each shard
takes the test files of one part of the suite, and a job that waits for all of them joins their
coverage data and checks the floor. A shard measures a part of the tree, so it checks no floor. A
shard passes the paths of its own files to pytest, so it collects no file of another shard (#2371).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from devops_cli.commands import ci as ci_module
from devops_cli.commands.ci import (
    CheckResult,
    _directory_modules,
    _resolve_pytest_cmd,
    _shard_test_files,
    app,
    get_check_specs,
)
from tests.support.paths import REPO_ROOT

runner = CliRunner()

_SPLIT_OPTIONS = ("--splits", "--group", "--splitting-algorithm")


def _said(output: str) -> str:
    """The output with the line breaks of the terminal width taken out."""
    return " ".join(output.split())


def test_the_unsharded_test_row_has_no_split_option_and_prints_the_term_report() -> None:
    """With no shard, the row is the row of every run before sharding existed."""
    cmd = _resolve_pytest_cmd()

    assert (
        "--splits" in cmd,
        "--group" in cmd,
        "--cov-fail-under=0" in cmd,
        "--cov-report=term-missing" in cmd,
        "--cov-report=" in cmd,
        "--snapshot-warn-unused" in cmd,
    ) == (False, False, False, True, False, False)


def test_one_shard_of_one_is_the_unsharded_row() -> None:
    """A total of 1 splits nothing, so `--shard 1 --shards 1` runs the whole suite."""
    assert _resolve_pytest_cmd(shard=1, shards=1) == _resolve_pytest_cmd()


def test_a_shard_runs_its_own_test_files_and_checks_no_floor() -> None:
    """Shard 2 of 4 runs the files of its quarter, keeps the coverage data, prints no report and
    leaves the floor to the job that combines the data of all shards. The snapshots of the other
    shards are unused in this one, and syrupy would fail the run on them."""
    cmd = _resolve_pytest_cmd(shard=2, shards=4)

    own_files = _shard_test_files(2, 4, REPO_ROOT)
    assert (
        cmd[-len(own_files) :],
        [option in cmd for option in _SPLIT_OPTIONS],
        "--cov=src" in cmd,
        "--cov-fail-under=0" in cmd,
        "--cov-report=" in cmd,
        "--cov-report=term-missing" in cmd,
        "--snapshot-warn-unused" in cmd,
    ) == (own_files, [False, False, False], True, True, True, False, True)


@pytest.mark.parametrize("shards", [2, 3, 4])
def test_the_shards_cover_every_test_module_once(shards: int) -> None:
    """Each test module is in exactly one shard, and no shard is empty."""
    every_module = _directory_modules("tests", REPO_ROOT)
    lists = [_shard_test_files(shard, shards, REPO_ROOT) for shard in range(1, shards + 1)]

    assert (
        sorted(module for files in lists for module in files),
        all(lists),
    ) == (every_module, True)


def test_the_split_is_the_same_in_every_call_and_in_any_order_of_asking() -> None:
    """Every runner computes its own shard, so the split must not depend on the call: two calls
    give one list, and asking for shard 4 first changes no list."""
    first = [_shard_test_files(shard, 4, REPO_ROOT) for shard in (1, 2, 3, 4)]
    reversed_order = {shard: _shard_test_files(shard, 4, REPO_ROOT) for shard in (4, 3, 2, 1)}

    assert first == [reversed_order[shard] for shard in (1, 2, 3, 4)]


def test_the_split_deals_the_heaviest_file_to_the_lightest_shard(tmp_path: Path) -> None:
    """Files go heaviest first to the shard with the fewest lines so far, and a tie goes to the
    lower shard. Lines of the files stand for the cost, so no stored data can go out of date."""
    tests = tmp_path / "tests"
    tests.mkdir()
    for name, lines in {"test_a.py": 5, "test_b.py": 4, "test_c.py": 3, "test_d.py": 3}.items():
        (tests / name).write_text("x = 1\n" * lines)
    (tests / "helper.py").write_text("x = 1\n" * 99)

    assert [_shard_test_files(shard, 2, tmp_path) for shard in (1, 2)] == [
        ["tests/test_a.py", "tests/test_d.py"],
        ["tests/test_b.py", "tests/test_c.py"],
    ]


def test_the_dry_run_of_a_shard_lists_its_files_and_starts_nothing() -> None:
    """The planned command of `--only test --shard 2 --shards 4` holds the files of shard 2 and
    none of the split options of the old plugin."""
    result = runner.invoke(app, ["--dry-run", "--only", "test", "--shard", "2", "--shards", "4"])

    said = _said(result.output)
    own_files = _shard_test_files(2, 4, REPO_ROOT)
    assert (
        result.exit_code,
        all(path in said for path in own_files),
        any(option in said for option in _SPLIT_OPTIONS),
    ) == (0, True, False)


def test_the_dry_run_of_an_unsharded_run_lists_no_split() -> None:
    """Without the options the planned command holds no split option and no test file."""
    result = runner.invoke(app, ["--dry-run", "--only", "test"])

    said = _said(result.output)
    assert (
        result.exit_code,
        "--splits" in said,
        "tests/commands/test_ci_shard.py" in said,
        "--cov-report=term-missing" in said,
    ) == (0, False, False, True)


@pytest.mark.parametrize(
    "options",
    [
        ["--shard", "5", "--shards", "4"],
        ["--shard", "2"],
        ["--shard", "0", "--shards", "4"],
        ["--shards", "0"],
    ],
    ids=["shard above total", "shard with no total", "shard zero", "total zero"],
)
def test_a_shard_outside_the_total_is_refused_before_any_check_starts(
    options: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A shard above the total, a shard with a total of 1, and a number under 1 exit 2."""
    started: list[Any] = []

    async def record_start(*args: Any, **kwargs: Any) -> list[CheckResult]:
        started.append(kwargs)
        return []

    monkeypatch.setattr(ci_module, "_run_all_checks_async", record_start)

    result = runner.invoke(app, ["--only", "test", "--check", "--no-cache", *options])

    assert (result.exit_code, started) == (2, [])


def test_a_sharded_run_uses_the_sharded_row_and_leaves_the_gate_cache_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A shard proves a part of the suite, so it neither trusts nor records a cached verdict, even
    when `--only` does not narrow it. The row it runs is the sharded one."""
    seen: dict[str, Any] = {"read": False, "written": False, "specs": []}

    def read_cache(*args: Any, **kwargs: Any) -> bool:
        seen["read"] = True
        return False

    def write_cache(*args: Any, **kwargs: Any) -> None:
        seen["written"] = True

    async def run_checks(*args: Any, **kwargs: Any) -> list[CheckResult]:
        seen["specs"] = kwargs["specs"]
        return [CheckResult(name="test", display_title="Tests", passed=True, duration_seconds=0.01)]

    monkeypatch.setattr(ci_module, "_try_fast_cached_ci", read_cache)
    monkeypatch.setattr(ci_module, "_try_save_ci_cache", write_cache)
    monkeypatch.setattr(ci_module, "_run_all_checks_async", run_checks)
    monkeypatch.setattr(ci_module, "_clean_coverage_artifacts", lambda **kwargs: None)

    result = runner.invoke(app, ["--check", "--no-cache", "--shard", "3", "--shards", "4"])

    test_row = next(spec for spec in seen["specs"] if spec.name == "test")
    assert (result.exit_code, seen["read"], seen["written"], test_row.cmd) == (
        0,
        False,
        False,
        _resolve_pytest_cmd(shard=3, shards=4),
    )


def test_a_shard_changes_the_test_row_and_no_other_row() -> None:
    """The other rows of the table are the rows of an unsharded run."""
    sharded = ci_module._with_test_shard(get_check_specs(), shard=2, shards=4)

    assert [(spec.name, spec.cmd) for spec in sharded if spec.name != "test"] == [
        (spec.name, spec.cmd) for spec in get_check_specs() if spec.name != "test"
    ]
