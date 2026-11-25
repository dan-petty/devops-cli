"""Tests for `devops ci test --repeat`: shuffled repeat runs of selected test files."""

from __future__ import annotations

import random
import shlex
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import typer
from click.testing import CliRunner, Result

from devops_cli.commands import ci as ci_module
from devops_cli.commands.ci import get_check_specs
from devops_cli.config.defaults import (
    DEFAULT_CI_TEST_NARROWED_WORKERS,
    DEFAULT_CI_TEST_REPEAT_RUNS,
    DEFAULT_CI_TEST_SERIAL_MAX_TESTS,
)
from devops_cli.lang import MESSAGES
from devops_cli.roadmap.implement.implement_size import WORKERS_VARIABLE
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.session_spawns import RecordedSpawn, record_spawns

pytest_plugins = ("pytester",)
pytestmark = pytest.mark.usefixtures("refuse_nested_test_runs")

# Typer builds the `ci` group from its functions' signatures on every invoke; building it once
# keeps each CLI case to the command's own run.
CI = typer.main.get_command(ci_module.app)
runner = CliRunner()
UV_RUN_PYTEST = ["uv", "--preview-features", "malware-check,check-command", "run", "pytest"]
HEAD = (0, "deadbeef" + 32 * "0" + "\n")
# The scheduling that keeps the tests of one file on one xdist worker.
LOADFILE = ["--dist", "loadfile"]

SHARED_STATE_TESTS = """
SEEN: list[str] = []


def test_first() -> None:
    SEEN.append("first")


def test_second() -> None:
    assert SEEN == ["first"]
"""


def _flat(output: str) -> str:
    """The output with each run of whitespace, line wraps included, collapsed to one space."""
    return " ".join(output.split())


def _invoke(
    process_fake: ProcessFake, *args: str, head: tuple[int, str] = HEAD
) -> tuple[Result, list[tuple[list[str], Any]]]:
    """Run `devops ci test` with every process it starts recorded, answering `git rev-parse`.

    The commands that run to completion are the process fake's calls; the pytest runs that start
    in a session of their own follow them, as the command makes them in that order."""
    code, stdout = head
    process_fake.answer(("git", "rev-parse"), ProcessAnswer(returncode=code, stdout=stdout))
    spawned: list[tuple[list[str], Any]] = []

    async def record_in_session(spawn: RecordedSpawn) -> None:
        spawned.append((spawn.argv, spawn.kwargs.get("cwd")))

    with pytest.MonkeyPatch.context() as monkeypatch:
        record_spawns(monkeypatch, on_communicate=record_in_session)
        result = runner.invoke(CI, ["test", *args])
    ran = [
        (list(call.argv), call.cwd)
        for call in process_fake.calls
        if "--collect-only" not in call.argv
    ]
    return result, [*ran, *spawned]


@pytest.fixture
def ci_repeat_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checked tree holding one test file, as the root the CI command verifies from the
    current directory."""
    (tmp_path / ".git").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x() -> None: ...\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def global_rngs_restored() -> Iterator[None]:
    """Put back the global `random` and numpy RNG states, which pytest-randomly reseeds when it
    runs in this process, so the tests this worker runs next do not start from a fixed seed."""
    from numpy import random as np_random

    state, numpy_state = random.getstate(), np_random.get_state()
    yield
    random.setstate(state)
    np_random.set_state(numpy_state)


@pytest.mark.usefixtures("global_rngs_restored")
def test_repeat_stops_at_the_seed_that_breaks_order_dependent_tests(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two tests sharing module state pass in file order and fail under a reversing seed; the
    repeat stops at that run and prints its seed with the command that reproduces it."""
    # pytest-randomly 5.0.0 orders tests by crc32(f"{seed}::{nodeid}"). For these nodeids, seed 2
    # keeps file order and seed 3 reverses it; re-check the seeds if the pin or the path changes.
    # The inner runs load only xdist and, through -p randomly, pytest-randomly: autoloading every
    # installed plugin costs seconds and warns about pytest-asyncio's unset loop scope. --tb=no
    # skips the failure's source lookup, which scans this process's every imported module.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    pytester.makepyprojecttoml(
        "[tool.pytest.ini_options]\n"
        'addopts = "-p xdist -p no:randomly -p no:logfire -p no:pytest_logfire --tb=no"\n'
    )
    pytester.mkdir("tests")
    (pytester.path / "tests" / "test_shared.py").write_text(SHARED_STATE_TESTS, encoding="utf-8")
    (pytester.path / ".git").mkdir()
    monkeypatch.chdir(pytester.path)
    plain = pytester.runpytest("-n", "0", "tests/test_shared.py")
    seeds: list[str] = []

    async def run_inner_pytest(spawn: RecordedSpawn) -> int:
        argv = spawn.argv[spawn.argv.index("pytest") + 1 :]
        seeds.extend(arg for arg in argv if arg.startswith("--randomly-seed="))
        return int(pytester.runpytest(*argv).ret)

    record_spawns(monkeypatch, on_communicate=run_inner_pytest)
    result = runner.invoke(CI, ["test", "--repeat", "3", "--seed", "2", "tests/test_shared.py"])

    reproduce = "uv run pytest -n 0 -p randomly --randomly-seed=3 tests/test_shared.py"
    failure = MESSAGES.ci.repeat_failed.format(run=2, runs=3, seed=3, command=reproduce)
    assert (
        plain.parseoutcomes(),
        result.exit_code,
        seeds,
        failure in _flat(result.output),
    ) == ({"passed": 2}, 1, ["--randomly-seed=2", "--randomly-seed=3"], True)


def test_each_repeat_runs_the_targets_on_the_given_workers_with_the_next_seed(
    ci_repeat_project: Path, process_fake: ProcessFake
) -> None:
    """Run i of N runs the targets in the project root on the workers of -n with seed S+i,
    each file on one worker, keeping -v, -k and -x ahead of the shuffle options (#6564)."""
    result, calls = _invoke(
        process_fake, *"--repeat 3 --seed 10 -n 4 -v -k unit -x -- tests/test_x.py".split()
    )

    assert (result.exit_code, calls) == (
        0,
        [
            (
                [*UV_RUN_PYTEST, "-n", "4", "-v", "-k", "unit", "-x", *LOADFILE]
                + ["-p", "randomly", f"--randomly-seed={seed}", "tests/test_x.py"],
                ci_repeat_project,
            )
            for seed in (10, 11, 12)
        ],
    )


def test_the_repeat_runs_take_the_workers_of_a_narrowed_run_from_one_collection(
    ci_repeat_project: Path, process_fake: ProcessFake, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no -n, the repeat runs take the workers that a narrowed run of the same files takes:
    two modules collecting more than DEFAULT_CI_TEST_SERIAL_MAX_TESTS tests give the worker cap. One
    collection chooses the workers of all runs, so a large change runs each shuffled run on the
    CPUs of the runner, and not on one process (#6564, #5612)."""
    monkeypatch.delenv(WORKERS_VARIABLE, raising=False)
    (ci_repeat_project / "tests" / "test_y.py").write_text(
        "def test_y() -> None: ...\n", encoding="utf-8"
    )
    ids = "".join(
        f"tests/test_x.py::test_{n}\n" for n in range(DEFAULT_CI_TEST_SERIAL_MAX_TESTS + 1)
    )
    process_fake.answer(lambda call: "--collect-only" in call.argv, ProcessAnswer(stdout=ids))

    result, calls = _invoke(
        process_fake, "--repeat", "2", "--seed", "5", "tests/test_x.py", "tests/test_y.py"
    )

    workers = str(DEFAULT_CI_TEST_NARROWED_WORKERS)
    assert (
        result.exit_code,
        len([call for call in process_fake.calls if "--collect-only" in call.argv]),
        calls,
    ) == (
        0,
        1,
        [
            (
                [*UV_RUN_PYTEST, "-n", workers, *LOADFILE, "-p", "randomly"]
                + [f"--randomly-seed={seed}", "tests/test_x.py", "tests/test_y.py"],
                ci_repeat_project,
            )
            for seed in (5, 6)
        ],
    )


@pytest.mark.parametrize(
    ("workers", "scheduling"), [("4", LOADFILE), ("0", [])], ids=["workers", "one-process"]
)
def test_a_repeat_run_on_workers_keeps_each_file_on_one_worker(
    ci_repeat_project: Path, process_fake: ProcessFake, workers: str, scheduling: list[str]
) -> None:
    """A repeat run on workers gives `--dist loadfile` after addopts' `--dist worksteal`, so all
    tests of one file run on one worker in their shuffled order, and a test that leaves state
    behind meets the tests of its own file as on one process. A run on one process gives no
    `--dist` (#6564)."""
    result, calls = _invoke(
        process_fake, "--repeat", "1", "--seed", "3", "-n", workers, "tests/test_x.py"
    )

    assert (result.exit_code, calls) == (
        0,
        [
            (
                [*UV_RUN_PYTEST, "-n", workers, *scheduling, "-p", "randomly"]
                + ["--randomly-seed=3", "tests/test_x.py"],
                ci_repeat_project,
            )
        ],
    )


def test_a_named_run_starts_only_that_run_with_its_own_seed(
    ci_repeat_project: Path, process_fake: ProcessFake
) -> None:
    """--run K of --repeat N starts run K alone, with the seed that run K of the N runs gets, so
    CI can start each run of one pull request on a runner of its own (#6564)."""
    result, calls = _invoke(
        process_fake, *"--repeat 3 --run 2 --seed 10 -n 0 -- tests/test_x.py".split()
    )

    assert (result.exit_code, calls) == (
        0,
        [
            (
                [*UV_RUN_PYTEST, "-n", "0", "-p", "randomly", "--randomly-seed=11"]
                + ["tests/test_x.py"],
                ci_repeat_project,
            )
        ],
    )


@pytest.mark.parametrize("args", [("--repeat", "3", "--run", "4"), ("--run", "1")])
def test_a_run_above_the_repeat_count_is_refused_before_any_process(
    ci_repeat_project: Path, process_fake: ProcessFake, args: tuple[str, ...]
) -> None:
    """--run above --repeat, or --run with no --repeat, exits 2 with the reason and starts no
    process (#6564)."""
    result, calls = _invoke(process_fake, *args, "tests/test_x.py")

    runs = int(args[1]) if args[0] == "--repeat" else DEFAULT_CI_TEST_REPEAT_RUNS
    run = int(args[-1])
    assert (
        result.exit_code,
        calls,
        MESSAGES.ci.run_above_repeat.format(run=run, runs=runs) in _flat(result.output),
    ) == (2, [], True)


def test_the_first_seed_defaults_to_heads_commit_hash(
    ci_repeat_project: Path, process_fake: ProcessFake
) -> None:
    """Without --seed, the first seed is HEAD's leading eight hex digits read as an integer."""
    result, calls = _invoke(process_fake, "--repeat", "2", "tests/test_x.py")

    assert (result.exit_code, calls[0], [cmd[-2] for cmd, _cwd in calls[1:]]) == (
        0,
        (["git", "rev-parse", "HEAD"], ci_repeat_project),
        ["--randomly-seed=3735928559", "--randomly-seed=3735928560"],
    )


def test_an_unreadable_head_asks_for_a_seed(
    ci_repeat_project: Path, process_fake: ProcessFake
) -> None:
    """When HEAD cannot be read, the command names --seed and runs no tests."""
    result, calls = _invoke(process_fake, "--repeat", "2", "tests/test_x.py", head=(128, ""))

    assert (
        result.exit_code,
        [cmd for cmd, _cwd in calls],
        MESSAGES.ci.repeat_seed_unavailable in _flat(result.output),
        "--seed" in MESSAGES.ci.repeat_seed_unavailable,
    ) == (1, [["git", "rev-parse", "HEAD"]], True, True)


def test_the_gate_and_a_plain_run_stay_in_file_order(
    ci_repeat_project: Path, process_fake: ProcessFake
) -> None:
    """No gate check and no run without --repeat enables pytest-randomly; --repeat is off by
    default."""
    result, calls = _invoke(process_fake, "tests/test_x.py")

    assert (
        [spec.name for spec in get_check_specs() if "randomly" in shlex.join(spec.cmd)],
        result.exit_code,
        [cmd for cmd, _cwd in calls],
        DEFAULT_CI_TEST_REPEAT_RUNS,
    ) == ([], 0, [[*UV_RUN_PYTEST, "-n", "0", "tests/test_x.py"]], 0)


@pytest.mark.parametrize("paths", [(), ("tests/conftest.py",)], ids=["no-paths", "trigger-file"])
def test_repeat_refuses_to_shuffle_the_whole_suite(
    ci_repeat_project: Path, paths: tuple[str, ...], process_fake: ProcessFake
) -> None:
    """When nothing narrows the run to test files, --repeat exits 1 and starts no process."""
    (ci_repeat_project / "tests" / "conftest.py").write_text("", encoding="utf-8")

    result, calls = _invoke(process_fake, "--repeat", "2", *paths)

    assert (
        result.exit_code,
        calls,
        MESSAGES.ci.repeat_needs_targets in _flat(result.output),
    ) == (1, [], True)


def test_a_dry_run_plans_every_repeat_and_starts_no_process(
    ci_repeat_project: Path, process_fake: ProcessFake
) -> None:
    """--dry-run prints the planned command of each repeat run and runs none of them."""
    with pytest.MonkeyPatch.context() as monkeypatch:
        spawns = record_spawns(monkeypatch)
        result = runner.invoke(
            CI, ["test", "--repeat", "2", "--seed", "7", "--dry-run", "tests/test_x.py"]
        )

    planned = "uv --preview-features malware-check,check-command run pytest -n 0 -p randomly"
    assert (
        result.exit_code,
        process_fake.calls,
        spawns,
        f"{planned} --randomly-seed=7 tests/test_x.py" in _flat(result.output),
        f"{planned} --randomly-seed=8 tests/test_x.py" in _flat(result.output),
    ) == (0, [], [], True, True)
