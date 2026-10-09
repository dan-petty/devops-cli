"""Tests for `devops ci test --repeat`: shuffled, serial repeat runs of selected test files."""

from __future__ import annotations

import random
import shlex
import subprocess
import tomllib
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import typer
import yaml
from click.testing import CliRunner, Result
from numpy import random as np_random

from devops_cli.commands import ci as ci_module
from devops_cli.commands.ci import get_check_specs
from devops_cli.config.defaults import DEFAULT_CI_TEST_REPEAT_RUNS
from devops_cli.lang import MESSAGES

pytest_plugins = ("pytester",)

# Typer builds the `ci` group from its functions' signatures on every invoke; building it once
# keeps each CLI case to the command's own run.
CI = typer.main.get_command(ci_module.app)
runner = CliRunner()
REPO_ROOT = Path(__file__).resolve().parents[1]
UV_RUN_PYTEST = ["uv", "--preview-features", "malware-check,check-command", "run", "pytest"]
HEAD = (0, "deadbeef" + 32 * "0" + "\n")

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


def _invoke(*args: str, head: tuple[int, str] = HEAD) -> tuple[Result, list[tuple[list[str], Any]]]:
    """Run `devops ci test` with every process it starts recorded, answering `git rev-parse`."""
    calls: list[tuple[list[str], Any]] = []

    def record(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((cmd, kwargs.get("cwd")))
        code, stdout = head if cmd[:2] == ["git", "rev-parse"] else (0, "")
        return subprocess.CompletedProcess(cmd, code, stdout, "")

    with patch.object(ci_module, "run_subprocess", record):
        result = runner.invoke(CI, ["test", *args])
    return result, calls


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A checked tree holding one test file, as the root the CI command verifies."""
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x() -> None: ...\n", encoding="utf-8")
    monkeypatch.setattr(ci_module, "_get_project_root", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def global_rngs_restored() -> Iterator[None]:
    """Put back the global `random` and numpy RNG states, which pytest-randomly reseeds when it
    runs in this process, so the tests this worker runs next do not start from a fixed seed."""
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
    monkeypatch.setattr(ci_module, "_get_project_root", lambda: pytester.path)
    plain = pytester.runpytest("-n", "0", "tests/test_shared.py")
    seeds: list[str] = []

    def run_inner_pytest(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        argv = cmd[cmd.index("pytest") + 1 :]
        seeds.extend(arg for arg in argv if arg.startswith("--randomly-seed="))
        return subprocess.CompletedProcess(cmd, int(pytester.runpytest(*argv).ret))

    with patch.object(ci_module, "run_subprocess", run_inner_pytest):
        result = runner.invoke(CI, ["test", "--repeat", "3", "--seed", "2", "tests/test_shared.py"])

    reproduce = "uv run pytest -n 0 -p randomly --randomly-seed=3 tests/test_shared.py"
    failure = MESSAGES.ci.repeat_failed.format(run=2, runs=3, seed=3, command=reproduce)
    assert (
        plain.parseoutcomes(),
        result.exit_code,
        seeds,
        failure in _flat(result.output),
    ) == ({"passed": 2}, 1, ["--randomly-seed=2", "--randomly-seed=3"], True)


def test_each_repeat_runs_the_targets_serially_with_the_next_seed(project: Path) -> None:
    """Run i of N runs the targets in the project root on one process (-n gives way to -n 0)
    with seed S+i, keeping -v, -k and -x ahead of the shuffle options."""
    result, calls = _invoke(*"--repeat 3 --seed 10 -n 4 -v -k unit -x -- tests/test_x.py".split())

    assert (result.exit_code, calls) == (
        0,
        [
            (
                [*UV_RUN_PYTEST, "-n", "0", "-v", "-k", "unit", "-x", "-p", "randomly"]
                + [f"--randomly-seed={seed}", "tests/test_x.py"],
                project,
            )
            for seed in (10, 11, 12)
        ],
    )


def test_the_first_seed_defaults_to_heads_commit_hash(project: Path) -> None:
    """Without --seed, the first seed is HEAD's leading eight hex digits read as an integer."""
    result, calls = _invoke("--repeat", "2", "tests/test_x.py")

    assert (result.exit_code, calls[0], [cmd[-2] for cmd, _cwd in calls[1:]]) == (
        0,
        (["git", "rev-parse", "HEAD"], project),
        ["--randomly-seed=3735928559", "--randomly-seed=3735928560"],
    )


def test_an_unreadable_head_asks_for_a_seed(project: Path) -> None:
    """When HEAD cannot be read, the command names --seed and runs no tests."""
    result, calls = _invoke("--repeat", "2", "tests/test_x.py", head=(128, ""))

    assert (
        result.exit_code,
        [cmd for cmd, _cwd in calls],
        MESSAGES.ci.repeat_seed_unavailable in _flat(result.output),
        "--seed" in MESSAGES.ci.repeat_seed_unavailable,
    ) == (1, [["git", "rev-parse", "HEAD"]], True, True)


def test_the_gate_and_a_plain_run_stay_in_file_order(project: Path) -> None:
    """No gate check and no run without --repeat enables pytest-randomly; --repeat is off by
    default."""
    result, calls = _invoke("tests/test_x.py")

    assert (
        [spec.name for spec in get_check_specs() if "randomly" in shlex.join(spec.cmd)],
        result.exit_code,
        [cmd for cmd, _cwd in calls],
        DEFAULT_CI_TEST_REPEAT_RUNS,
    ) == ([], 0, [[*UV_RUN_PYTEST, "tests/test_x.py"]], 0)


@pytest.mark.parametrize("paths", [(), ("tests/conftest.py",)], ids=["no-paths", "trigger-file"])
def test_repeat_refuses_to_shuffle_the_whole_suite(project: Path, paths: tuple[str, ...]) -> None:
    """When nothing narrows the run to test files, --repeat exits 1 and starts no process."""
    (project / "tests" / "conftest.py").write_text("", encoding="utf-8")

    result, calls = _invoke("--repeat", "2", *paths)

    assert (
        result.exit_code,
        calls,
        MESSAGES.ci.repeat_needs_targets in _flat(result.output),
    ) == (1, [], True)


def test_pytest_randomly_is_installed_and_blocked_by_default() -> None:
    """The dev group pins pytest-randomly and addopts blocks it, so ordinary runs keep file order."""
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    addopts = shlex.split(pyproject["tool"]["pytest"]["ini_options"]["addopts"])

    assert (
        ("-p", "no:randomly") in pairwise(addopts),
        "pytest-randomly==5.0.0" in pyproject["dependency-groups"]["dev"],
    ) == (True, True)


def test_the_changed_test_job_reruns_added_or_modified_test_files() -> None:
    """ci.yml's advisory pull-request job lists changed test files and repeats them shuffled,
    skipping its toolchain and run steps when no test file changed."""
    workflow = yaml.safe_load(
        (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )
    job = workflow["jobs"]["changed-tests"]
    steps = {step["name"]: step for step in job["steps"]}
    detect = steps["Detect Changed Test Files"]
    toolchain = steps["Set up uv toolchain"]
    rerun = steps["Run Changed Tests in Shuffled Order"]
    changed = "steps.changed_tests.outputs.changed == 'true'"

    assert (
        (job["name"], job["if"], job["permissions"], "needs" in job),
        (detect["id"], detect["env"]["BASE_REF"]),
        ("--diff-filter=AMR" in detect["run"], ":(glob)tests/**/test_*.py" in detect["run"]),
        (toolchain.get("if"), rerun.get("if")),
        (toolchain["with"]["cache-suffix"], toolchain["with"]["tooling-cache-paths"].split()),
        "devops ci test --repeat 3" in rerun["run"],
        [step["name"] for step in job["steps"] if "${{" in step.get("run", "")],
    ) == (
        (
            "Changed-Test Independence",
            "github.event_name == 'pull_request'",
            {"contents": "read"},
            False,
        ),
        ("changed_tests", "${{ github.base_ref }}"),
        (True, True),
        (changed, changed),
        ("changed-tests", [".pytest_cache"]),
        True,
        [],
    )


def test_a_dry_run_plans_every_repeat_and_starts_no_process(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--dry-run prints the planned command of each repeat run and runs none of them."""
    started: list[list[str]] = []

    def record(cmd: list[str], *_args: Any, **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        started.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("subprocess.run", record)

    result = runner.invoke(
        CI, ["test", "--repeat", "2", "--seed", "7", "--dry-run", "tests/test_x.py"]
    )

    planned = "uv --preview-features malware-check,check-command run pytest -n 0 -p randomly"
    assert (
        result.exit_code,
        started,
        f"{planned} --randomly-seed=7 tests/test_x.py" in _flat(result.output),
        f"{planned} --randomly-seed=8 tests/test_x.py" in _flat(result.output),
    ) == (0, [], True, True)
