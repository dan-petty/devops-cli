"""Tests for `devops ci --shard` and `--shards`: the test row runs one part of the suite (#3050).

The `Tests & Coverage` job of CI runs the test row in shards on separate runners, and a job that
waits for all of them joins their coverage data and checks the floor. A shard measures a part of
the tree, so it checks no floor. pytest-split chooses the tests of a shard (#7500).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from devops_cli.ci.cache import resolve_ci_cache_path
from devops_cli.commands.ci import app, get_check_spec
from devops_cli.config.constants import CONST_TESTS_ROOT_DIR
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.process import ProcessFake

runner = CliRunner()

_SPLIT_OPTIONS = ("--splits", "--group", "--splitting-algorithm")

# One test of each outcome whose reason the log of a shard must give.
_SHARD_SUITE = """
import pytest


def test_passes() -> None:
    assert True


@pytest.mark.skip(reason="promtool is not installed")
def test_skips() -> None:
    pass


def test_fails() -> None:
    assert False
"""


def _said(output: str) -> str:
    """The output with the line breaks of the terminal width taken out."""
    return " ".join(output.split())


def _planned_test_row(*options: str) -> list[str]:
    """The words of the command that the plan of `devops ci --dry-run --only test` gives."""
    result = runner.invoke(app, ["--dry-run", "--only", "test", *options])
    set_dry_run(False)
    words = _said(result.output).split()
    row = words[words.index("1.") + 1 :]
    # The plan shows the gate-row environment before the command; a recorded call holds the command
    # alone (#4881).
    return row[1:] if row[:1] == ["UV_MALWARE_CHECK=0"] else row


def _split_words(row: list[str]) -> list[str]:
    """The split options of the test row `row`, each followed by its value, in the order of
    `_SPLIT_OPTIONS`; an option that the row does not hold gives no word."""
    return [
        word
        for option in _SPLIT_OPTIONS
        if option in row
        for word in (option, row[row.index(option) + 1])
    ]


def test_the_unsharded_test_row_has_no_split_option_and_prints_the_term_report() -> None:
    """With no shard, the row is the row of every run before sharding existed."""
    cmd = get_check_spec("test").cmd

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
    assert _planned_test_row("--shard", "1", "--shards", "1") == _planned_test_row()


def test_a_shard_runs_its_pytest_split_group_and_checks_no_floor() -> None:
    """Shard 2 of 4 asks pytest-split for group 2 of 4 with the `least_duration` algorithm, and
    passes no test path, so pytest collects `testpaths`. The shard keeps the coverage data, prints
    no report and leaves the floor to the job that combines the data of all shards. The snapshots
    of the other shards are unused in this one, and syrupy would fail the run on them."""
    cmd = _planned_test_row("--shard", "2", "--shards", "4")

    assert (
        _split_words(cmd),
        [word for word in cmd if word.startswith(f"{CONST_TESTS_ROOT_DIR}/")],
        "--cov=src" in cmd,
        "--cov-fail-under=0" in cmd,
        "--cov-report=" in cmd,
        "--cov-report=term-missing" in cmd,
        "--snapshot-warn-unused" in cmd,
    ) == (
        ["--splits", "4", "--group", "2", "--splitting-algorithm", "least_duration"],
        [],
        True,
        True,
        True,
        False,
        True,
    )


def test_the_shard_rows_give_each_test_to_exactly_one_shard(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The split options of the rows of shards 1 and 2 of 2, run with pytest-split on six tests,
    select each test in exactly one shard. The tree holds no `.test_durations`, as the repository
    holds none, so each test weighs the same and the shards take the tests in turn."""
    # The inner run loads no installed plugin but pytest-split: autoloading each plugin costs
    # seconds.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyprojecttoml(
        '[tool.pytest.ini_options]\naddopts = "-p pytest_split.plugin -p no:randomly"\n'
    )
    names = [f"test_split.py::test_{number}" for number in range(6)]
    pytester.makepyfile(
        test_split="".join(f"def test_{number}() -> None:\n    pass\n\n\n" for number in range(6))
    )

    selected = [
        [
            line
            for line in pytester.runpytest(
                *_split_words(_planned_test_row("--shard", str(shard), "--shards", "2")),
                "--collect-only",
                "-q",
            ).stdout.lines
            if line.startswith("test_split.py::")
        ]
        for shard in (1, 2)
    ]

    assert selected == [names[0::2], names[1::2]]


def test_a_shard_gives_the_reason_of_each_skip_and_names_each_failure(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The log of a shard must give the reason of each skip (#4673). The report options of the
    shard row, on a suite with a pass, a skip and a failure, print the reason of the skip. The
    option `-r` of pytest replaces its default `fE`, so the row asks again for the failures and
    errors, and the failure stays in the summary."""
    # The inner run loads no installed plugin: autoloading each plugin costs seconds.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyprojecttoml('[tool.pytest.ini_options]\naddopts = "-p no:randomly --tb=no"\n')
    pytester.makepyfile(test_shard=_SHARD_SUITE)
    row = _planned_test_row("--shard", "2", "--shards", "4")

    result = pytester.runpytest(*[word for word in row if word.startswith("-r")], "test_shard.py")

    output = _said(result.stdout.str())
    assert (
        re.search(r"SKIPPED \[1\] test_shard\.py:\d+: promtool is not installed", output)
        is not None,
        "FAILED test_shard.py::test_fails" in output,
        "--junitxml" in " ".join(row),
    ) == (True, True, False)


def test_the_dry_run_of_a_shard_lists_its_group_and_starts_nothing() -> None:
    """The planned command of `--only test --shard 2 --shards 4` names group 2 of 4."""
    result = runner.invoke(app, ["--dry-run", "--only", "test", "--shard", "2", "--shards", "4"])

    said = _said(result.output)
    assert (
        result.exit_code,
        "--splits 4 --group 2 --splitting-algorithm least_duration" in said,
    ) == (0, True)


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
    options: list[str], process_fake: ProcessFake
) -> None:
    """A shard above the total, a shard with a total of 1, and a number under 1 exit 2."""
    result = runner.invoke(app, ["--only", "test", "--check", "--no-cache", *options])

    assert (result.exit_code, process_fake.calls) == (2, [])


def _test_row_runs(process_fake: ProcessFake) -> list[list[str]]:
    """The pytest commands of the test row: every pytest command but that of the `bwrap` row."""
    return [
        list(call.argv)
        for call in process_fake.calls
        if "pytest" in call.argv and "bwrap" not in call.argv
    ]


def test_a_sharded_run_uses_the_sharded_row_and_leaves_the_gate_cache_alone(
    ci_root: Path, ci_head: ProcessFake
) -> None:
    """A shard proves a part of the suite, so it neither trusts nor records a cached verdict, even
    when `--only` does not narrow it. The row it runs is the sharded one."""
    sharded_options = ["--shard", "3", "--shards", "4"]
    planned = _planned_test_row(*sharded_options)

    first = runner.invoke(app, ["--check", *sharded_options])
    recorded = resolve_ci_cache_path(ci_root).is_file()
    ran_first = _test_row_runs(ci_head)

    runner.invoke(app, ["--check"])
    ci_head.calls.clear()
    second = runner.invoke(app, ["--check", *sharded_options])
    ran_second = _test_row_runs(ci_head)

    assert (first.exit_code, second.exit_code, recorded, ran_first, ran_second) == (
        0,
        0,
        False,
        [planned],
        [planned],
    )


def test_a_shard_changes_the_test_row_and_no_other_row() -> None:
    """The other rows of the table are the rows of an unsharded run."""

    def planned_rows(*options: str) -> list[str]:
        result = runner.invoke(app, ["--dry-run", *options])
        set_dry_run(False)
        return re.split(r" (?=\d+\. )", _said(result.output))[1:]

    unsharded = planned_rows()
    sharded = planned_rows("--shard", "2", "--shards", "4")

    def without_test_row(rows: list[str]) -> list[str]:
        return [row.split(". ", 1)[1] for row in rows if " pytest " not in row]

    assert (len(sharded), without_test_row(sharded), sharded != unsharded) == (
        len(unsharded),
        without_test_row(unsharded),
        True,
    )


def test_a_shard_test_row_stops_before_the_job_limit() -> None:
    """The test row of a shard has its own 900 s bound inside the 20-minute job (#4683)."""
    from devops_cli.commands.ci import _with_test_shard
    from devops_cli.config.defaults import DEFAULT_CI_TEST_SHARD_TIMEOUT_SECONDS

    spec = get_check_spec("test")
    (sharded,) = _with_test_shard([spec], shard=2, shards=4)

    assert (spec.timeout_seconds, sharded.timeout_seconds) == (
        None,
        DEFAULT_CI_TEST_SHARD_TIMEOUT_SECONDS,
    )
