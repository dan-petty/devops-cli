"""Tests for `devops ci --shard` and `--shards`: the test row runs one part of the suite (#3050).

The `Tests & Coverage` job of CI runs the test row in shards on separate runners, so each shard
takes the test files of one part of the suite, and a job that waits for all of them joins their
coverage data and checks the floor. A shard measures a part of the tree, so it checks no floor. A
shard passes the paths of its own files to pytest, so it collects no file of another shard (#2371).
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from devops_cli.ci.cache import resolve_ci_cache_path
from devops_cli.ci.fail_to_pass import parse_junit_xml
from devops_cli.commands.ci import app, get_check_spec
from devops_cli.config.constants import CONST_CI_TEST_DURATIONS_PATH
from devops_cli.core.test_selection import directory_modules, is_test_module, shard_test_files
from devops_cli.dry_run import set_dry_run
from tests.support.fakes.process import ProcessFake
from tests.support.paths import REPO_ROOT

runner = CliRunner()

_SPLIT_OPTIONS = ("--splits", "--group", "--splitting-algorithm")
_JUNIT_OPTION = "--junitxml="

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
    return words[words.index("1.") + 1 :]


def _report_path(row: list[str]) -> str | None:
    """The path of the JUnit XML report that the test row `row` writes, or None when it writes none."""
    return next(
        (word.removeprefix(_JUNIT_OPTION) for word in row if word.startswith(_JUNIT_OPTION)), None
    )


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


def test_a_shard_runs_its_own_test_files_and_checks_no_floor() -> None:
    """Shard 2 of 4 runs the files of its quarter, keeps the coverage data, prints no report and
    leaves the floor to the job that combines the data of all shards. The snapshots of the other
    shards are unused in this one, and syrupy would fail the run on them."""
    cmd = _planned_test_row("--shard", "2", "--shards", "4")

    own_files = shard_test_files(2, 4, REPO_ROOT)
    assert (
        cmd[-len(own_files) :],
        [option in cmd for option in _SPLIT_OPTIONS],
        "--cov=src" in cmd,
        "--cov-fail-under=0" in cmd,
        "--cov-report=" in cmd,
        "--cov-report=term-missing" in cmd,
        "--snapshot-warn-unused" in cmd,
    ) == (own_files, [False, False, False], True, True, True, False, True)


def test_a_shard_reports_each_test_id_and_the_reason_of_each_skip_and_failure(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The split by measured time (#4250) needs the time of each test of a shard, and the log of a
    shard must give the reason of each skip (#4673). The report options of the shard row, on a
    suite with a pass, a skip and a failure, write the three tests to the JUnit XML report and
    print the reason of the skip. The option `-r` of pytest replaces its default `fE`, so the row
    asks again for the failures and errors, and the failure stays in the summary."""
    # The inner run loads no installed plugin: autoloading each plugin costs seconds.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyprojecttoml('[tool.pytest.ini_options]\naddopts = "-p no:randomly --tb=no"\n')
    pytester.makepyfile(test_shard=_SHARD_SUITE)
    row = _planned_test_row("--shard", "2", "--shards", "4")
    report_path = _report_path(row)
    assert report_path is not None, "the shard row writes no JUnit XML report"

    result = pytester.runpytest(
        *[word for word in row if word.startswith(("-r", _JUNIT_OPTION))], "test_shard.py"
    )

    report = parse_junit_xml((pytester.path / report_path).read_text(encoding="utf-8"))
    output = _said(result.stdout.str())
    assert (
        sorted(f"{case.classname}::{case.name}" for case in report),
        re.search(r"SKIPPED \[1\] test_shard\.py:\d+: promtool is not installed", output)
        is not None,
        "FAILED test_shard.py::test_fails" in output,
    ) == (
        ["test_shard::test_fails", "test_shard::test_passes", "test_shard::test_skips"],
        True,
        True,
    )


def test_each_shard_job_uploads_the_report_of_its_row_with_its_coverage_data() -> None:
    """Each shard job of CI uploads the JUnit XML report that its test row writes, in the artifact
    that holds its coverage data, so that the split by measured time can read the time of each
    test of the suite from the artifacts of a run (#4250, #4673)."""
    workflow = yaml.safe_load((REPO_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8"))
    upload = next(
        step
        for step in workflow["jobs"]["test-shard"]["steps"]
        if step.get("uses", "").startswith("actions/upload-artifact@")
    )
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    coverage_data = pyproject["tool"]["coverage"]["run"]["data_file"]

    assert upload["with"]["path"].split() == [
        coverage_data,
        _report_path(_planned_test_row("--shard", "2", "--shards", "4")),
    ]


@pytest.mark.parametrize("shards", [2, 3, 4])
def test_the_shards_cover_every_test_module_once(shards: int) -> None:
    """Each test module is in exactly one shard, and no shard is empty."""
    every_module = directory_modules("tests", REPO_ROOT)
    lists = [shard_test_files(shard, shards, REPO_ROOT) for shard in range(1, shards + 1)]

    assert (
        sorted(module for files in lists for module in files),
        all(lists),
    ) == (every_module, True)


def test_the_split_is_the_same_in_every_call_and_in_any_order_of_asking() -> None:
    """Every runner computes its own shard, so the split must not depend on the call: two calls
    give one list, and asking for shard 4 first changes no list."""
    first = [shard_test_files(shard, 4, REPO_ROOT) for shard in (1, 2, 3, 4)]
    reversed_order = {shard: shard_test_files(shard, 4, REPO_ROOT) for shard in (4, 3, 2, 1)}

    assert first == [reversed_order[shard] for shard in (1, 2, 3, 4)]


def _tree(root: Path, lines: dict[str, int], durations: dict[str, float] | None = None) -> None:
    """Write test modules of `lines` lines each under `root`, and the recorded seconds of
    `durations` at the path that the split reads, when given."""
    for module, count in lines.items():
        path = root / module
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n" * count)
    if durations is not None:
        (root / CONST_CI_TEST_DURATIONS_PATH).write_text(json.dumps(durations), encoding="utf-8")


def test_a_short_module_with_a_long_recorded_time_is_alone_in_its_shard(tmp_path: Path) -> None:
    """A module of 10 lines that took 300 s weighs more than three modules of 500 lines that took
    10 s each, so it fills one shard and the three others share the second (#5247)."""
    long_modules = {f"tests/test_{name}.py": 500 for name in "abc"}
    _tree(
        tmp_path,
        {"tests/test_slow.py": 10, **long_modules},
        {"tests/test_slow.py": 300.0, **dict.fromkeys(long_modules, 10.0)},
    )

    assert [shard_test_files(shard, 2, tmp_path) for shard in (1, 2)] == [
        ["tests/test_slow.py"],
        ["tests/test_a.py", "tests/test_b.py", "tests/test_c.py"],
    ]


def test_a_module_without_a_recorded_time_weighs_its_lines_at_the_recorded_rate(
    tmp_path: Path,
) -> None:
    """The recorded modules hold 200 lines for 110 s, so a new module of 100 lines weighs 55 s:
    less than the module of 100 s and more than the module of 10 s, so it joins the light one."""
    _tree(
        tmp_path,
        {"tests/test_a.py": 100, "tests/test_b.py": 100, "tests/test_c.py": 100},
        {"tests/test_a.py": 100.0, "tests/test_b.py": 10.0},
    )

    assert [shard_test_files(shard, 2, tmp_path) for shard in (1, 2)] == [
        ["tests/test_a.py"],
        ["tests/test_b.py", "tests/test_c.py"],
    ]


def test_a_recorded_module_that_the_tree_no_longer_holds_is_ignored(tmp_path: Path) -> None:
    """The file still names a deleted module: the split gives it to no shard, and its seconds
    do not change the rate of the lines of a new module."""
    _tree(
        tmp_path,
        {"tests/test_a.py": 10, "tests/test_b.py": 10, "tests/test_c.py": 10},
        {"tests/test_gone.py": 9000.0, "tests/test_a.py": 30.0, "tests/test_b.py": 20.0},
    )

    assert [shard_test_files(shard, 2, tmp_path) for shard in (1, 2)] == [
        ["tests/test_a.py"],
        ["tests/test_b.py", "tests/test_c.py"],
    ]


def test_the_committed_durations_are_seconds_of_test_modules() -> None:
    """The committed file maps the path of a test module to the seconds it took, so a typing
    error fails here and not in the four shards of CI."""
    recorded = json.loads((REPO_ROOT / CONST_CI_TEST_DURATIONS_PATH).read_text(encoding="utf-8"))

    assert (
        bool(recorded),
        [path for path in recorded if not is_test_module(path)],
        [path for path, seconds in recorded.items() if not isinstance(seconds, (int, float))],
    ) == (True, [], [])


def test_the_split_deals_the_heaviest_file_to_the_lightest_shard(tmp_path: Path) -> None:
    """With no recorded seconds, files go heaviest first to the shard with the fewest lines so
    far, and a tie goes to the lower shard."""
    tests = tmp_path / "tests"
    tests.mkdir()
    for name, lines in {"test_a.py": 5, "test_b.py": 4, "test_c.py": 3, "test_d.py": 3}.items():
        (tests / name).write_text("x = 1\n" * lines)
    (tests / "helper.py").write_text("x = 1\n" * 99)

    assert [shard_test_files(shard, 2, tmp_path) for shard in (1, 2)] == [
        ["tests/test_a.py", "tests/test_d.py"],
        ["tests/test_b.py", "tests/test_c.py"],
    ]


def test_the_dry_run_of_a_shard_lists_its_files_and_starts_nothing() -> None:
    """The planned command of `--only test --shard 2 --shards 4` holds the files of shard 2 and
    none of the split options of the old plugin."""
    result = runner.invoke(app, ["--dry-run", "--only", "test", "--shard", "2", "--shards", "4"])

    said = _said(result.output)
    own_files = shard_test_files(2, 4, REPO_ROOT)
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
