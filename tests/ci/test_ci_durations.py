"""Tests for `devops ci durations`: the recorded seconds of each test module, which balance the
test shards of CI (#5247).

GitHub's API is the fake of the `github_api` fixture, and `gh run download` is the process fake,
which writes the JUnit reports that the test gives into the folder of the download.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.ci import fail_to_pass
from devops_cli.ci.durations import mean_durations, module_of, module_seconds, write_durations
from devops_cli.config.constants import CONST_CI_TEST_DURATIONS_PATH
from devops_cli.core.test_selection import recorded_durations
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

if TYPE_CHECKING:
    from collections.abc import Callable

    from tests.support.fakes.github import GitHubApiFake

_REPO = "octocat/Hello-World"
_RUNS = (
    f"/repos/{_REPO}/actions/workflows/ci.yml/runs"
    "?branch=main&event=push&status=completed&per_page=100"
)
_JOB = "Tests & Coverage"
_MODULES = frozenset({"tests/a/test_x.py", "tests/test_y.py"})


def _case(classname: str, seconds: float) -> fail_to_pass.TestCaseOutcome:
    return fail_to_pass.TestCaseOutcome(
        classname=classname, name="test_it", status="passed", seconds=seconds
    )


@pytest.mark.parametrize(
    ("classname", "module"),
    [
        pytest.param("tests.a.test_x", "tests/a/test_x.py", id="function"),
        pytest.param("tests.a.test_x.TestCase", "tests/a/test_x.py", id="class"),
        pytest.param("tests.a.test_x.TestCase.TestInner", "tests/a/test_x.py", id="nested-class"),
        pytest.param("tests.test_gone", None, id="deleted-module"),
    ],
)
def test_the_classname_of_a_test_names_its_module(classname: str, module: str | None) -> None:
    """Pytest writes the module path with dots, then the class of the test when it has one."""
    assert module_of(classname, _MODULES) == module


def test_the_seconds_of_the_tests_of_a_module_add_up() -> None:
    """Two tests of one module took 2.5 s and 1.5 s, so the module took 4 s. A test of a module
    that the tree no longer holds counts nowhere."""
    outcomes = [
        _case("tests.a.test_x", 2.5),
        _case("tests.a.test_x.TestCase", 1.5),
        _case("tests.test_y", 0.25),
        _case("tests.test_gone", 99.0),
    ]

    assert module_seconds(outcomes, _MODULES) == {"tests/a/test_x.py": 4.0, "tests/test_y.py": 0.25}


def test_the_mean_of_a_module_covers_only_the_runs_that_ran_it() -> None:
    """A module that one of two runs ran keeps the time of that run, and the means are in tenths
    of a second, in the order of the paths."""
    runs = [{"tests/test_y.py": 10.04, "tests/a/test_x.py": 3.0}, {"tests/test_y.py": 20.0}]

    assert list(mean_durations(runs).items()) == [
        ("tests/a/test_x.py", 3.0),
        ("tests/test_y.py", 15.0),
    ]


def test_the_written_record_is_what_the_split_reads(tmp_path: Path) -> None:
    """The record holds one module a line in the order of the paths, and the split reads the
    same seconds back."""
    (tmp_path / "tests").mkdir()
    durations = {"tests/test_y.py": 1.5, "tests/a/test_x.py": 20.0}

    path = write_durations(tmp_path, durations)

    assert (
        path.read_text(encoding="utf-8"),
        recorded_durations(tmp_path),
    ) == (
        '{\n  "tests/a/test_x.py": 20.0,\n  "tests/test_y.py": 1.5\n}\n',
        durations,
    )


def _report(*cases: tuple[str, float]) -> str:
    """A JUnit XML report as pytest writes it, with one test of each class name and time."""
    rows = "".join(
        f'<testcase classname="{classname}" name="test_{n}" time="{seconds}" />'
        for n, (classname, seconds) in enumerate(cases)
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?><testsuites name="pytest tests">'
        f'<testsuite name="pytest" tests="{len(cases)}">{rows}</testsuite></testsuites>'
    )


def _route_runs(api: GitHubApiFake, artifacts: dict[int, list[dict[str, Any]]]) -> None:
    """One completed run for each entry of `artifacts`, newest first, whose check ran to an end,
    with those artifacts."""
    runs = [{"id": run_id} for run_id in artifacts]
    api.route("GET", _RUNS, github_json({"total_count": len(runs), "workflow_runs": runs}))
    job = {
        "name": _JOB,
        "conclusion": "success",
        "started_at": "2026-11-13T04:54:05Z",
        "completed_at": "2026-11-13T04:59:35Z",
    }
    for run_id, listed in artifacts.items():
        api.route(
            "GET",
            f"/repos/{_REPO}/actions/runs/{run_id}/jobs?per_page=100",
            github_json({"total_count": 1, "jobs": [job]}),
        )
        api.route(
            "GET",
            f"/repos/{_REPO}/actions/runs/{run_id}/artifacts?per_page=100",
            github_json({"total_count": len(listed), "artifacts": listed}),
        )


def _artifact(name: str, *, expired: bool = False) -> dict[str, Any]:
    return {"name": name, "expired": expired}


def _serve_downloads(process_fake: ProcessFake, reports: dict[str, dict[str, str]]) -> None:
    """Answer `gh run download <run_id> ... --dir <dir>` by writing the report of each artifact
    of `reports[run_id]` into `<dir>/<artifact>/junit.xml`, as gh unpacks a pattern."""

    def download(call: ProcessCall) -> ProcessAnswer:
        argv = list(call.argv)
        folder = Path(argv[argv.index("--dir") + 1])
        for artifact, text in reports[argv[3]].items():
            (folder / artifact).mkdir(parents=True)
            (folder / artifact / "junit.xml").write_text(text, encoding="utf-8")
        return ProcessAnswer()

    process_fake.answer(("gh", "run", "download"), download)


def _checkout(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A checkout at `root` with the modules of `_MODULES`, as the current directory."""
    (root / ".git").mkdir()
    (root / "pyproject.toml").write_text("[project]\nname = 'sample'\n", encoding="utf-8")
    for module in _MODULES:
        (root / module).parent.mkdir(parents=True, exist_ok=True)
        (root / module).write_text("def test_it() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(root)


def test_the_command_writes_the_mean_seconds_of_the_shard_reports_of_each_run(
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run 2 holds two shard reports and run 1 one: the record holds the mean of each module over
    the runs that ran it. Run 3 holds no shard artifact that GitHub still keeps, so gh downloads
    nothing of it."""
    _checkout(tmp_path, monkeypatch)
    _route_runs(
        github_api,
        {
            3: [_artifact("coverage-shard-1", expired=True), _artifact("service-image")],
            2: [_artifact("coverage-shard-1"), _artifact("coverage-shard-2")],
            1: [_artifact("coverage-shard-1")],
        },
    )
    _serve_downloads(
        process_fake,
        {
            "2": {
                "coverage-shard-1": _report(("tests.a.test_x", 3.0), ("tests.a.test_x", 1.0)),
                "coverage-shard-2": _report(("tests.test_y", 10.0)),
            },
            "1": {"coverage-shard-1": _report(("tests.test_y", 20.0), ("tests.test_gone", 5.0))},
        },
    )

    result = cli("ci", "durations", "--repo", _REPO, "--runs", "3")

    downloads = [
        call.argv[3] for call in process_fake.calls if call.argv[1:3] == ("run", "download")
    ]
    assert (
        result.exit_code,
        json.loads((tmp_path / CONST_CI_TEST_DURATIONS_PATH).read_text(encoding="utf-8")),
        downloads,
        "2 test modules from 2 runs" in " ".join(result.output.split()),
    ) == (0, {"tests/a/test_x.py": 4.0, "tests/test_y.py": 15.0}, ["2", "1"], True)


def test_the_command_exits_1_and_writes_nothing_when_no_run_holds_a_report(
    github_api: GitHubApiFake,
    process_fake: ProcessFake,
    cli: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub keeps the artifacts of a run for 7 days: with none left, no record is written."""
    _checkout(tmp_path, monkeypatch)
    _route_runs(github_api, {1: [_artifact("coverage-shard-1", expired=True)]})

    result = cli("ci", "durations", "--repo", _REPO, "--runs", "1")

    assert (
        result.exit_code,
        (tmp_path / CONST_CI_TEST_DURATIONS_PATH).exists(),
        process_fake.calls,
    ) == (1, False, [])


def test_a_dry_run_lists_the_reads_and_the_download_and_makes_none(
    github_api: GitHubApiFake, process_fake: ProcessFake, cli: Callable[..., Any]
) -> None:
    """The plan names the listing of runs, the jobs and artifacts of each run, and the download."""
    result = cli("ci", "durations", "--repo", _REPO, "--dry-run")

    said = " ".join(result.output.split())
    assert (
        result.exit_code,
        github_api.requested,
        process_fake.calls,
        "actions/workflows/ci.yml/runs" in said,
        "/artifacts" in said,
        "gh run download" in said,
    ) == (0, [], [], True, True, True)
