"""Tests for `devops ci job-time`: the check that fails when the last runs of a CI job, read from
GitHub's Actions API, average more than the limit (#2699).

GitHub's API is the fake of the `github_api` fixture, so each case runs the real session, client
and command over answers that the test gives. The recorded runs and jobs are those of the
`Tests & Coverage` job on `main` on 2026-10-30.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import pytest

from devops_cli.ci.job_time import JobTimeReport, check_job_time
from devops_cli.config import defaults
from devops_cli.github.client import JobRunTime
from devops_cli.github.rate_limiter import get_github_rate_limiter
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import github_json, next_page, quota_headers
from tests.support.paths import FIXTURES

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence
    from pathlib import Path

    from tests.support.fakes.github import GitHubApiFake

_RECORDED = json.loads((FIXTURES / "github" / "ci_runs_main.json").read_text(encoding="utf-8"))
_REPO = "octocat/Hello-World"
_RUNS = (
    f"/repos/{_REPO}/actions/workflows/ci.yml/runs"
    "?branch=main&event=push&status=completed&per_page=100"
)
_JOB = "Tests & Coverage"
# The seconds the job took in each recorded run, from its start to its end, newest run first.
_RECORDED_SECONDS = [
    404.0,
    345.0,
    399.0,
    413.0,
    321.0,
    418.0,
    425.0,
    324.0,
    411.0,
    409.0,
    378.0,
    396.0,
]


def _jobs_path(run_id: int | str) -> str:
    return f"/repos/{_REPO}/actions/runs/{run_id}/jobs?per_page=100"


def _route_recorded_runs(api: GitHubApiFake) -> None:
    """Answer the recorded list of runs and the recorded jobs of each."""
    api.route("GET", _RUNS, github_json(_RECORDED["workflow_runs"]))
    for run_id, jobs in _RECORDED["run_jobs"].items():
        api.route("GET", _jobs_path(run_id), github_json(jobs))


def _said(result: Any) -> str:
    """What the command printed, with the line breaks the terminal width made taken out."""
    return " ".join(result.output.split())


def _job(name: str, started: str, completed: str, conclusion: str = "success") -> dict[str, Any]:
    return {
        "name": name,
        "status": "completed",
        "conclusion": conclusion,
        "started_at": started,
        "completed_at": completed,
    }


def _route_runs(api: GitHubApiFake, seconds: Sequence[float | None]) -> list[int]:
    """Route one completed run for each entry, newest first. An entry is the seconds the job took
    in that run, or None for a run that has no such job."""
    ids = list(range(100, 100 + len(seconds)))
    runs = [{"id": run_id, "head_branch": "main", "event": "push"} for run_id in ids]
    api.route("GET", _RUNS, github_json({"total_count": len(runs), "workflow_runs": runs}))
    for run_id, took in zip(ids, seconds, strict=True):
        jobs = [_job("Static Analysis", "2026-10-29T10:00:00Z", "2026-10-29T10:01:00Z")]
        if took is not None:
            end = f"2026-10-29T10:{int(took) // 60:02d}:{int(took) % 60:02d}Z"
            jobs.append(_job(_JOB, "2026-10-29T10:00:00Z", end))
        api.route("GET", _jobs_path(run_id), github_json({"total_count": len(jobs), "jobs": jobs}))
    return ids


_RELEASE_RUNS = (
    f"/repos/{_REPO}/actions/workflows/release.yml/runs"
    "?branch=main&event=push&status=completed&per_page=100"
)


# The jobs of release.yml on main since #6571, as runs 44977064803 (a release) and 44979901604 (no
# release) of 2026-11-22 give them. release.yml calls release-image.yml one time for each image,
# and GitHub names each job of a call `<Title> Image / <job>`. A run that makes no release skips
# the call, and GitHub shows it as one skipped job whose name it does not expand.
_IMAGE_STEP_JOBS = ("Build", "Verify", "Attest & Tag")
_RELEASE_IMAGE_JOBS = tuple(
    f"{title} Image / {step}" for title in ("MCP Server", "Runner") for step in _IMAGE_STEP_JOBS
)
_OTHER_RELEASE_JOBS = (
    "Upload Release Assets",
    "Build DevContainer Image",
    "Smoke-Test DevContainer Image",
    "Attest & Tag DevContainer Image",
    *(f"Service Image / {step}" for step in _IMAGE_STEP_JOBS),
)
_SKIPPED_RELEASE_JOBS = (
    "Upload Release Assets",
    "Smoke-Test DevContainer Image",
    "Attest & Tag DevContainer Image",
    "Build DevContainer Image",
    "${{ matrix.title }} Image",
)


def _ended_after(seconds: float) -> str:
    return f"2026-10-29T10:{int(seconds) // 60:02d}:{int(seconds) % 60:02d}Z"


def _release_jobs(seconds: Mapping[str, float]) -> list[dict[str, Any]]:
    """The jobs of a run that made a release. A release image job takes its seconds in `seconds`,
    or 300 s, and each other job takes 100 s."""
    jobs = [_job("Release Please", "2026-10-29T09:59:00Z", "2026-10-29T09:59:15Z")]
    jobs += [
        _job(name, "2026-10-29T10:00:00Z", _ended_after(100.0)) for name in _OTHER_RELEASE_JOBS
    ]
    jobs += [
        _job(name, "2026-10-29T10:00:00Z", _ended_after(seconds.get(name, 300.0)))
        for name in _RELEASE_IMAGE_JOBS
    ]
    return jobs


def _no_release_jobs() -> list[dict[str, Any]]:
    """The jobs of a run that made no release: GitHub gives a skipped job an end before its start."""
    skipped = [
        _job(name, "2026-10-29T10:00:01Z", "2026-10-29T10:00:00Z", "skipped")
        for name in _SKIPPED_RELEASE_JOBS
    ]
    return [_job("Release Please", "2026-10-29T09:59:00Z", "2026-10-29T09:59:15Z"), *skipped]


def _route_jobs(api: GitHubApiFake, run_id: int, jobs: list[dict[str, Any]]) -> None:
    api.route("GET", _jobs_path(run_id), github_json({"total_count": len(jobs), "jobs": jobs}))


def _route_release_runs(
    api: GitHubApiFake, seconds: Mapping[str, float] | None = None, count: int = 10
) -> list[int]:
    """Route completed push runs of release.yml on main, newest first: `count` runs that made a
    release, each one followed by a run that made none. The jobs of a release run are those of
    `_release_jobs(seconds)`. Returns the ids of the runs."""
    ids = list(range(200, 200 + 2 * count))
    runs = [{"id": run_id, "head_branch": "main", "event": "push"} for run_id in ids]
    api.route("GET", _RELEASE_RUNS, github_json({"total_count": len(runs), "workflow_runs": runs}))
    for n, run_id in enumerate(ids):
        _route_jobs(api, run_id, _release_jobs(seconds or {}) if n % 2 == 0 else _no_release_jobs())
    return ids


def _read(count: int = 10) -> list[JobRunTime]:
    return get_github_session().client.get_job_run_times(
        _REPO, workflow="ci.yml", branch="main", job=_JOB, count=count
    )


def test_the_job_seconds_of_the_recorded_runs_are_read_from_the_job_of_each_run(
    github_api: GitHubApiFake,
) -> None:
    """Each run holds many jobs, and only the named one counts, from its start to its end."""
    _route_recorded_runs(github_api)

    read = _read(count=12)

    assert [(run.run_id, run.seconds) for run in read] == [
        (int(run["id"]), seconds)
        for run, seconds in zip(
            _RECORDED["workflow_runs"]["workflow_runs"], _RECORDED_SECONDS, strict=True
        )
    ]


def test_the_read_stops_at_the_wanted_runs_and_asks_for_no_more_jobs(
    github_api: GitHubApiFake,
) -> None:
    """Ten runs are wanted, so the listing of jobs of the eleventh and twelfth run is never asked."""
    _route_recorded_runs(github_api)

    read = _read(count=10)

    runs = _RECORDED["workflow_runs"]["workflow_runs"]
    assert (len(read), github_api.requested) == (
        10,
        [f"GET https://api.github.com{_RUNS}"]
        + [f"GET https://api.github.com{_jobs_path(run['id'])}" for run in runs[:10]],
    )


def test_a_run_without_the_job_or_with_the_job_cancelled_is_left_out(
    github_api: GitHubApiFake,
) -> None:
    """A run that skipped the job has no time for it, and a cancelled job did not run to its end:
    neither counts toward the wanted runs."""
    ids = _route_runs(github_api, [300.0, None, 200.0, 100.0])
    github_api.route(
        "GET",
        _jobs_path(ids[2]),
        github_json(
            {
                "total_count": 1,
                "jobs": [_job(_JOB, "2026-10-29T10:00:00Z", "2026-10-29T10:09:00Z", "cancelled")],
            }
        ),
    )

    read = _read(count=3)

    assert [(run.run_id, run.seconds) for run in read] == [(ids[0], 300.0), (ids[3], 100.0)]


@pytest.mark.parametrize("conclusion", ["failure", "timed_out"])
def test_a_job_that_ran_to_an_end_counts_whatever_the_run_concluded(
    github_api: GitHubApiFake, conclusion: str
) -> None:
    """A run whose test job failed or timed out is a real sample, and so is a run that failed for
    another job, the guard itself among them. The listing holds every completed run, and the
    job's own conclusion decides (#2699)."""
    ids = _route_runs(github_api, [250.0] * 10)
    runs = [{"id": run_id, "conclusion": "failure"} for run_id in ids]
    github_api.route("GET", _RUNS, github_json({"total_count": 10, "workflow_runs": runs}))
    job = _job(_JOB, "2026-10-29T10:00:00Z", "2026-10-29T10:10:00Z", conclusion)
    github_api.route("GET", _jobs_path(ids[3]), github_json({"total_count": 1, "jobs": [job]}))

    read = _read(count=10)

    assert [run.seconds for run in read] == [250.0] * 3 + [600.0] + [250.0] * 6


def test_a_slow_failed_job_among_fast_runs_puts_the_mean_over_the_limit(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Nineteen runs of 250 s and one failed run of 600 s average 267.5 s with the failure counted,
    and over a limit of 260 s: the slow run is seen, not dropped for its conclusion."""
    ids = _route_runs(github_api, [250.0] * 20)
    job = _job(_JOB, "2026-10-29T10:00:00Z", "2026-10-29T10:10:00Z", "failure")
    github_api.route("GET", _jobs_path(ids[5]), github_json({"total_count": 1, "jobs": [job]}))

    result = cli("ci", "job-time", "--repo", _REPO, "--limit", "260")

    assert (result.exit_code, "took 268 s on average" in _said(result)) == (1, True)


def test_a_job_that_has_not_ended_is_left_out(github_api: GitHubApiFake) -> None:
    """A job that GitHub reports as successful but without an end has no time to read."""
    ids = _route_runs(github_api, [300.0, 200.0])
    running = {"name": _JOB, "conclusion": "success", "started_at": "2026-10-29T10:00:00Z"}
    github_api.route("GET", _jobs_path(ids[0]), github_json({"total_count": 1, "jobs": [running]}))

    assert [(run.run_id, run.seconds) for run in _read(count=2)] == [(ids[1], 200.0)]


def test_the_runs_are_read_page_by_page_until_enough_hold_the_job(
    github_api: GitHubApiFake,
) -> None:
    """The listing follows its next link, so runs on a second page count."""
    first = {"id": 1, "head_branch": "main", "event": "push"}
    second = {"id": 2, "head_branch": "main", "event": "push"}
    second_page = "/repositories/1/actions/workflows/5/runs?page=2"
    github_api.route(
        "GET",
        _RUNS,
        github_json({"total_count": 2, "workflow_runs": [first]}, headers=next_page(second_page)),
    )
    github_api.route("GET", second_page, github_json({"total_count": 2, "workflow_runs": [second]}))
    for run_id, end in ((1, "10:05:00"), (2, "10:03:00")):
        job = _job(_JOB, "2026-10-29T10:00:00Z", f"2026-10-29T{end}Z")
        github_api.route("GET", _jobs_path(run_id), github_json({"total_count": 1, "jobs": [job]}))

    assert [run.seconds for run in _read(count=2)] == [300.0, 180.0]


def test_an_answer_that_holds_no_runs_reads_as_none(github_api: GitHubApiFake) -> None:
    """A workflow with no completed run on the branch gives an empty read, not an error."""
    github_api.route("GET", _RUNS, github_json({"total_count": 0, "workflow_runs": []}))

    assert _read() == []


@pytest.mark.parametrize(
    ("seconds", "mean", "passes"),
    [
        pytest.param([300.0] * 10, 300.0, True, id="on-the-limit"),
        pytest.param([290.0, 310.0] * 5 + [], 300.0, True, id="mean-on-the-limit"),
        pytest.param([300.0] * 9 + [310.0], 301.0, False, id="over-the-limit"),
        pytest.param([250.0] * 9 + [400.0], 265.0, True, id="one-slow-run-among-fast-ones"),
    ],
)
def test_the_report_passes_when_the_mean_is_not_over_the_limit(
    seconds: list[float], mean: float, passes: bool
) -> None:
    """The mean is of the runs read, and the limit itself is inside."""
    report = JobTimeReport(
        job=_JOB,
        wanted=10,
        limit_seconds=300.0,
        runs=tuple(JobRunTime(run_id=i, seconds=s) for i, s in enumerate(seconds)),
    )

    assert (report.mean_seconds, report.passes) == (mean, passes)


def test_the_report_fails_when_fewer_runs_than_wanted_could_be_read() -> None:
    """A mean of three fast runs says nothing of ten, so a short read never passes."""
    report = JobTimeReport(
        job=_JOB,
        wanted=10,
        limit_seconds=300.0,
        runs=tuple(JobRunTime(run_id=i, seconds=100.0) for i in range(3)),
    )

    assert (report.mean_seconds, report.complete, report.passes) == (100.0, False, False)


def test_the_check_reads_the_runs_through_the_client(github_api: GitHubApiFake) -> None:
    """`check_job_time` is the client's read, with the wanted count and the limit kept."""
    _route_runs(github_api, [100.0, 200.0])

    report = check_job_time(
        get_github_session().client,
        _REPO,
        workflow="ci.yml",
        branch="main",
        job=_JOB,
        wanted=2,
        limit_seconds=300.0,
    )

    assert (report.mean_seconds, report.passes, report.wanted) == (150.0, True, 2)


def test_the_command_exits_0_and_names_the_mean_when_the_job_is_inside_the_limit(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Twenty runs of 100 s average 100 s, well inside the default limit of 360 s."""
    _route_runs(github_api, [100.0] * 20)
    _route_release_runs(github_api)

    result = cli("ci", "job-time", "--repo", _REPO)

    assert (
        result.exit_code,
        "took 100 s on average" in _said(result),
        "limit is 360 s" in _said(result),
    ) == (0, True, True)


@pytest.mark.parametrize(
    ("seconds", "exit_code"),
    [
        pytest.param(330.0, 0, id="over-the-target-inside-the-tolerance"),
        pytest.param(360.0, 0, id="on-the-limit"),
        pytest.param(361.0, 1, id="over-the-tolerance"),
    ],
)
def test_the_default_limit_is_the_target_of_300_s_and_60_s_of_tolerance(
    github_api: GitHubApiFake, cli: Callable[..., Any], seconds: float, exit_code: int
) -> None:
    """The owner allows 1 minute over the 5 minutes of AGENTS.md rule 5 for the variation of the
    runners (2026-10-23), so the alarm fails only above 360 s (#5247)."""
    _route_runs(github_api, [seconds] * 20)
    _route_release_runs(github_api)

    result = cli("ci", "job-time", "--repo", _REPO)

    assert (result.exit_code, "limit is 360 s" in _said(result)) == (exit_code, True)


def test_the_command_exits_1_and_names_the_mean_when_the_job_is_over_the_limit(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Twenty runs of 400 s average 400 s: the check fails and the output says by how much."""
    _route_runs(github_api, [400.0] * 20)
    _route_release_runs(github_api)

    result = cli("ci", "job-time", "--repo", _REPO)

    assert (
        result.exit_code,
        "took 400 s on average" in _said(result),
        "Over the limit" in _said(result),
    ) == (
        1,
        True,
        True,
    )


def test_the_command_takes_the_limit_and_the_count_from_its_options(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Two runs of 100 s and 200 s average 150 s: over a limit of 120 s, inside one of 150 s."""
    _route_runs(github_api, [100.0, 200.0])

    over = cli("ci", "job-time", "--repo", _REPO, "--runs", "2", "--limit", "120")
    inside = cli("ci", "job-time", "--repo", _REPO, "--runs", "2", "--limit", "150")

    assert (over.exit_code, inside.exit_code) == (1, 0)


def test_a_count_above_the_bound_of_a_read_is_a_usage_error_that_names_the_bound(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """A read stops after the jobs of `DEFAULT_CI_JOB_TIME_MAX_RUNS` runs, so it can never give
    more runs. A larger `--runs` exits 2, names the bound and sends no request (#6734)."""
    bound = defaults.DEFAULT_CI_JOB_TIME_MAX_RUNS

    result = cli("ci", "job-time", "--repo", _REPO, "--runs", str(bound + 1))

    assert (
        result.exit_code,
        (f"1<=x<={bound}" in _said(result) or f"less than or equal to {bound}" in _said(result)),
        github_api.requested,
    ) == (
        2,
        True,
        [],
    )


def test_the_command_exits_1_when_fewer_runs_than_wanted_exist(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Three runs of 100 s are inside the limit, and still no pass: twenty were asked for."""
    _route_runs(github_api, [100.0] * 3)
    _route_release_runs(github_api)

    result = cli("ci", "job-time", "--repo", _REPO)

    assert (result.exit_code, "Only 3 of the last 20 runs" in _said(result)) == (1, True)


def _route_sharded_run(
    api: GitHubApiFake,
    shards: list[tuple[str, str]],
    aggregate: tuple[str, str],
    *,
    extra: list[Any],
    run_id: int = 100,
) -> None:
    """Route one run whose check ran in shards: a job `Tests & Coverage (shard n of N)` from the
    start to the end of each of `shards`, the job `Tests & Coverage` from `aggregate[0]` to
    `aggregate[1]`, and the `extra` jobs."""
    runs = [{"id": run_id, "head_branch": "main", "event": "push"}]
    api.route("GET", _RUNS, github_json({"total_count": 1, "workflow_runs": runs}))
    total = len(shards)
    jobs = [
        _job(f"{_JOB} (shard {n} of {total})", start, end)
        for n, (start, end) in enumerate(shards, start=1)
    ]
    jobs.append(_job(_JOB, *aggregate))
    jobs.extend(extra)
    api.route("GET", _jobs_path(run_id), github_json({"total_count": len(jobs), "jobs": jobs}))


def _shards_ending_at_10_03(*starts: str) -> list[tuple[str, str]]:
    return [(start, "2026-10-29T10:03:00Z") for start in starts]


# The shard jobs and the join of `main` run 43018142394 of 2026-11-11. The account runs 20 jobs at
# one time, so the shards started over 412 s and the join started 208 s after the last shard ended.
_QUEUED_SHARDS = [
    ("2026-11-11T12:12:49Z", "2026-11-11T12:19:56Z"),
    ("2026-11-11T12:14:33Z", "2026-11-11T12:20:14Z"),
    ("2026-11-11T12:17:53Z", "2026-11-11T12:23:53Z"),
    ("2026-11-11T12:19:41Z", "2026-11-11T12:24:51Z"),
]
_QUEUED_JOIN = ("2026-11-11T12:28:19Z", "2026-11-11T12:29:04Z")


def test_a_run_with_shard_jobs_is_timed_by_its_slowest_shard_and_the_join(
    github_api: GitHubApiFake,
) -> None:
    """The shards run side by side and the job `Tests & Coverage` joins them after the last one,
    so the check ran for its slowest shard plus the join (#3050). The rest of the span, from the
    first start of a shard to the end of the join, is time in the queue and is kept apart (#4634)."""
    _route_sharded_run(
        github_api,
        _shards_ending_at_10_03(
            "2026-10-29T10:00:03Z", "2026-10-29T10:00:00Z", "2026-10-29T10:00:05Z"
        ),
        ("2026-10-29T10:03:10Z", "2026-10-29T10:04:10Z"),
        extra=[],
    )

    assert [(run.seconds, run.queue_seconds) for run in _read(count=1)] == [(240.0, 10.0)]


def test_the_time_a_run_waited_for_runners_is_not_counted(github_api: GitHubApiFake) -> None:
    """Run 43018142394 spans 975 s, but its slowest shard ran 427 s and the join 45 s: the check
    ran 472 s, and the other 503 s are time in the queue (#4634)."""
    _route_sharded_run(github_api, _QUEUED_SHARDS, _QUEUED_JOIN, extra=[], run_id=43018142394)

    assert [(run.run_id, run.seconds, run.queue_seconds) for run in _read(count=1)] == [
        (43018142394, 472.0, 503.0)
    ]


def test_a_shard_without_an_end_is_not_the_slowest_shard(github_api: GitHubApiFake) -> None:
    """A shard that GitHub gives with a start and no end has no run time, so the slowest shard is
    one that ended. Its start still opens the span of the run."""
    runs = [{"id": 100, "head_branch": "main", "event": "push"}]
    github_api.route("GET", _RUNS, github_json({"total_count": 1, "workflow_runs": runs}))
    jobs = [
        {
            "name": f"{_JOB} (shard 1 of 2)",
            "conclusion": "success",
            "started_at": "2026-10-29T10:00:00Z",
        },
        _job(f"{_JOB} (shard 2 of 2)", "2026-10-29T10:00:10Z", "2026-10-29T10:02:10Z"),
        _job(_JOB, "2026-10-29T10:03:00Z", "2026-10-29T10:04:00Z"),
    ]
    github_api.route("GET", _jobs_path(100), github_json({"total_count": 3, "jobs": jobs}))

    assert [(run.seconds, run.queue_seconds) for run in _read(count=1)] == [(180.0, 60.0)]


def test_a_job_with_a_longer_name_does_not_change_the_time_of_the_check(
    github_api: GitHubApiFake,
) -> None:
    """Only the job of the name and the jobs named `<name> (…)` belong to the check: a job named
    `Tests & Coverage Report` that started earlier and ran longer is not one of them."""
    _route_sharded_run(
        github_api,
        _shards_ending_at_10_03("2026-10-29T10:00:00Z"),
        ("2026-10-29T10:03:10Z", "2026-10-29T10:04:10Z"),
        extra=[_job(f"{_JOB} Report", "2026-10-29T09:00:00Z", "2026-10-29T09:30:00Z")],
    )

    assert [(run.seconds, run.queue_seconds) for run in _read(count=1)] == [(240.0, 10.0)]


@pytest.mark.parametrize(
    ("limit", "exit_code"),
    [
        pytest.param("480", 0, id="run-time-inside-the-limit"),
        pytest.param("460", 1, id="run-time-over-the-limit"),
    ],
)
def test_the_command_checks_the_run_time_and_prints_the_queue_time_on_its_own_line(
    github_api: GitHubApiFake, cli: Callable[..., Any], limit: str, exit_code: int
) -> None:
    """The limit applies to the 472 s that the check ran, not to the span of 975 s. The 503 s in
    the queue are shown on a line of their own, so a long queue is seen and does not fail the
    check (#4634)."""
    _route_sharded_run(github_api, _QUEUED_SHARDS, _QUEUED_JOIN, extra=[])

    result = cli("ci", "job-time", "--repo", _REPO, "--runs", "1", "--limit", limit)

    assert (
        result.exit_code,
        "took 472 s on average" in _said(result),
        "also waited 503 s on average" in _said(result),
    ) == (exit_code, True, True)


def test_a_run_whose_aggregate_job_was_cancelled_is_left_out_though_its_shards_ran(
    github_api: GitHubApiFake,
) -> None:
    """The shards began, and the job that ends the check did not run to its end: the run says
    nothing of the time of the check."""
    runs = [{"id": 100, "head_branch": "main", "event": "push"}]
    github_api.route("GET", _RUNS, github_json({"total_count": 1, "workflow_runs": runs}))
    jobs = [
        _job(f"{_JOB} (shard 1 of 1)", "2026-10-29T10:00:00Z", "2026-10-29T10:02:00Z"),
        _job(_JOB, "2026-10-29T10:02:10Z", "2026-10-29T10:02:20Z", "cancelled"),
    ]
    github_api.route("GET", _jobs_path(100), github_json({"total_count": 2, "jobs": jobs}))

    assert _read(count=1) == []


def test_a_dry_run_lists_the_requests_and_makes_none(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """A dry run reads nothing from GitHub: it lists the listing of runs and the jobs of each."""
    result = cli("ci", "job-time", "--repo", _REPO, "--dry-run")

    assert (
        result.exit_code,
        github_api.requested,
        "actions/workflows/ci.yml/runs" in result.output,
    ) == (
        0,
        [],
        True,
    )


_ALARM_SEARCH = "/search/issues?" + urlencode(
    {"q": f'"devops-ci-job-time" in:body is:issue repo:{_REPO}', "per_page": 100, "page": 1}
)
_ALARM_LINE = "<!-- devops-ci-job-time: Tests & Coverage of ci.yml on main -->"


def _route_alarm_search(api: GitHubApiFake, *issues: dict[str, Any]) -> None:
    """Answer the issue search for the alarm marker with `issues`."""
    get_github_rate_limiter().update_quota(
        "search", remaining=30, limit=30, reset_epoch=time.time() + 60.0
    )
    payload = {"total_count": len(issues), "incomplete_results": False, "items": list(issues)}
    api.route(
        "GET",
        _ALARM_SEARCH,
        github_json(payload, headers=quota_headers(29, resource="search", limit=30)),
    )


def _issue(number: int, state: str, body: str) -> dict[str, Any]:
    return {"number": number, "state": state, "state_reason": None, "body": body}


def _posted(api: GitHubApiFake) -> list[tuple[str, dict[str, Any]]]:
    """The path and the JSON body of each POST that the API received."""
    return [
        (request.url.path, json.loads(request.content))
        for request in api.sent
        if request.method == "POST"
    ]


def test_a_mean_over_the_limit_files_one_p0_issue_when_none_is_open(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """No open issue holds the alarm of the check, so the run files one with the priority P0 and
    the Status New, which refine reads, as intake gives a new item. Its body names the mean, the
    limit and each run, and ends with the line that finds it the next day (#5247)."""
    _route_runs(github_api, [400.0] * 20)
    _route_release_runs(github_api)
    _route_alarm_search(github_api, _issue(7, "closed", f"Fixed.\n{_ALARM_LINE}"))
    github_api.route("POST", f"/repos/{_REPO}/issues", github_json({"number": 42}, status=201))

    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    [(path, issue)] = _posted(github_api)
    assert (
        result.exit_code,
        path,
        issue["title"],
        issue["labels"],
        "took 400 s on average. The limit is 360 s." in issue["body"],
        "actions/runs/100) | 400 | 0 |" in issue["body"],
        issue["body"].endswith(f"{_ALARM_LINE}\n"),
        f"https://github.com/{_REPO}/issues/42" in _said(result),
    ) == (
        1,
        f"/repos/{_REPO}/issues",
        "fix(ci): Tests & Coverage averages 400 s, over the 360 s limit",
        ["type/bug", "scope/ci", "status/new", "priority/p0-critical"],
        True,
        True,
        True,
        True,
    )


def _patched(api: GitHubApiFake) -> list[tuple[str, dict[str, Any]]]:
    """The path and the JSON body of each PATCH that the API received."""
    return [
        (request.url.path, json.loads(request.content))
        for request in api.sent
        if request.method == "PATCH"
    ]


def _route_held_issue(api: GitHubApiFake, number: int, body: str) -> None:
    """Answer the read of the open alarm issue `number` with `body`, and accept a change of it."""
    api.route(
        "GET",
        f"/repos/{_REPO}/issues/{number}",
        github_json({**_issue(number, "open", body), "title": "Renamed by a person"}),
    )
    api.route("PATCH", f"/repos/{_REPO}/issues/{number}", github_json({"number": number}))


def _filed_body(api: GitHubApiFake, cli: Callable[..., Any], seconds: float) -> str:
    """The body of the alarm issue that a run over the limit files when no issue is open."""
    _route_runs(api, [seconds] * 20)
    _route_release_runs(api)
    _route_alarm_search(api)
    api.route("POST", f"/repos/{_REPO}/issues", github_json({"number": 42}, status=201))
    cli("ci", "job-time", "--repo", _REPO, "--file-issue")
    [(_, issue)] = _posted(api)
    api.sent.clear()
    return str(issue["body"])


def test_a_mean_over_the_limit_writes_the_report_into_the_open_issue_and_posts_no_comment(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Issue 12 holds the alarm of the check and is open, so the run writes its report into the
    body of the issue, as GitHub gives it now, and posts no comment and files no second issue. The
    text above the alarm line stays, also a line that the issue search does not hold yet. Issue 9
    holds the alarm of another check, and issue 13 holds the word in other text: neither counts
    (#6199)."""
    _route_runs(github_api, [400.0] * 20)
    _route_release_runs(github_api)
    other = "<!-- devops-ci-job-time: Service Image Tests of service-image-test.yml on main -->"
    held = f"Renamed by a person.\n{_ALARM_LINE}"
    _route_alarm_search(
        github_api,
        _issue(9, "open", other),
        _issue(13, "open", "The devops-ci-job-time alarm is noisy."),
        _issue(12, "open", held),
    )
    _route_held_issue(github_api, 12, f"{held}\nA note of a person from today.")

    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    [(path, change)] = _patched(github_api)
    assert (
        result.exit_code,
        _posted(github_api),
        path,
        change["body"].startswith(f"{held}\nA note of a person from today.\n"),
        "took 400 s on average" in change["body"],
        f"https://github.com/{_REPO}/issues/12" in _said(result),
    ) == (1, [], f"/repos/{_REPO}/issues/12", True, True, True)


def test_a_later_run_replaces_the_report_in_the_body_and_keeps_the_text_of_a_person(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The first run filed the issue. A person then wrote above and below the report. The next run
    over the limit replaces the report with its own mean and runs, and changes nothing else: the
    alarm line and the text of the person stay, and the body holds one report (#6199)."""
    filed = _filed_body(github_api, cli, 400.0)
    edited = f"A person's line above.\n\n{filed}A person's line below.\n"
    _route_runs(github_api, [500.0] * 20)
    _route_release_runs(github_api)
    _route_alarm_search(github_api, _issue(42, "open", edited))
    _route_held_issue(github_api, 42, edited)

    cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    [(_, change)] = _patched(github_api)
    body = change["body"]
    assert (
        _posted(github_api),
        body.startswith("A person's line above.\n\n"),
        body.endswith("A person's line below.\n"),
        body.count(_ALARM_LINE),
        body.count("| Run | Seconds | Queue seconds |"),
        "took 500 s on average" in body,
        "took 400 s on average" in body,
    ) == ([], True, True, 1, 1, True, False)


def test_a_later_run_with_the_same_report_writes_nothing(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The body already holds the report that the run makes, so the run sends no change and posts
    no comment (#6199)."""
    filed = _filed_body(github_api, cli, 400.0)
    _route_runs(github_api, [400.0] * 20)
    _route_release_runs(github_api)
    _route_alarm_search(github_api, _issue(42, "open", filed))
    _route_held_issue(github_api, 42, filed)

    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    assert (result.exit_code, _posted(github_api), _patched(github_api)) == (1, [], [])


@pytest.mark.parametrize(
    "seconds",
    [
        pytest.param([100.0] * 20, id="inside-the-limit"),
        pytest.param([400.0] * 3, id="short-read"),
    ],
)
def test_no_issue_is_searched_or_filed_without_a_full_read_over_the_limit(
    github_api: GitHubApiFake, cli: Callable[..., Any], seconds: list[float]
) -> None:
    """A mean inside the limit is no breach, and the mean of 3 of 20 runs says nothing yet, so
    the run searches no issue and writes nothing."""
    _route_runs(github_api, seconds)
    _route_release_runs(github_api)

    cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    assert (
        [line for line in github_api.requested if "search" in line],
        _posted(github_api),
    ) == ([], [])


def test_a_dry_run_with_the_issue_lists_the_search_and_both_writes_and_makes_none(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The plan lists the issue search, the read and the change of the body of the open issue,
    and the new issue, each with its condition. It lists no comment (#6199)."""
    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue", "--dry-run")

    said = _said(result)
    assert (
        result.exit_code,
        github_api.requested,
        "/search/issues" in said,
        f"GET /repos/{_REPO}/issues/<number>" in said,
        f"PATCH /repos/{_REPO}/issues/<number>" in said,
        "/comments" in said,
        f"POST /repos/{_REPO}/issues " in said,
    ) == (0, [], True, True, True, False, True)


def test_the_command_exits_1_and_asks_for_a_repository_when_the_checkout_has_no_origin(
    github_api: GitHubApiFake,
    cli: Callable[..., Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without `--repo` the command reads the origin of the checkout, and a directory that is no
    checkout has none: the command says so and makes no request."""
    monkeypatch.chdir(tmp_path)

    result = cli("ci", "job-time")

    assert (result.exit_code, "--repo" in _said(result), github_api.requested) == (1, True, [])


def test_the_default_checks_hold_the_test_job_and_the_six_release_image_jobs() -> None:
    """`JOB_TIME_CHECKS` holds seven checks: the test job of ci.yml over 20 runs, and each of the
    jobs Build, Verify and Attest & Tag of the two release images of release.yml over 10 runs, by
    the names of the Actions API, each at the 360 s limit. `job_time_checks` narrows to one check
    when an option is given."""
    from devops_cli.ci.job_time import JOB_TIME_CHECKS, JobTimeCheck, job_time_checks

    assert [(c.workflow, c.branch, c.job, c.runs, c.limit_seconds) for c in JOB_TIME_CHECKS] == [
        ("ci.yml", "main", "Tests & Coverage", 20, 360.0),
        ("release.yml", "main", "MCP Server Image / Build", 10, 360.0),
        ("release.yml", "main", "MCP Server Image / Verify", 10, 360.0),
        ("release.yml", "main", "MCP Server Image / Attest & Tag", 10, 360.0),
        ("release.yml", "main", "Runner Image / Build", 10, 360.0),
        ("release.yml", "main", "Runner Image / Verify", 10, 360.0),
        ("release.yml", "main", "Runner Image / Attest & Tag", 10, 360.0),
    ]
    assert job_time_checks() == JOB_TIME_CHECKS
    assert job_time_checks(job="Custom Job", runs=5, limit_seconds=180.0) == (
        JobTimeCheck(
            workflow="ci.yml", branch="main", job="Custom Job", runs=5, limit_seconds=180.0
        ),
    )


# The run times of the release image jobs of run 44977064803 of 2026-11-22.
_RELEASE_SECONDS = {
    "MCP Server Image / Build": 114.0,
    "MCP Server Image / Verify": 80.0,
    "MCP Server Image / Attest & Tag": 25.0,
    "Runner Image / Build": 210.0,
    "Runner Image / Verify": 156.0,
    "Runner Image / Attest & Tag": 23.0,
}


def test_the_command_reports_the_mean_of_each_release_image_job_of_the_api(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The jobs have the names that the Actions API gives, and the runs between two releases hold
    only skipped jobs and `${{ matrix.title }} Image`. With no option the command prints the mean
    of each of the six release image jobs, and of no Service Image job, and exits 0 (#6734)."""
    _route_runs(github_api, [200.0] * 20)
    _route_release_runs(github_api, _RELEASE_SECONDS)

    result = cli("ci", "job-time", "--repo", _REPO)

    said = _said(result)
    assert (
        result.exit_code,
        [
            job
            for job, seconds in _RELEASE_SECONDS.items()
            if f"The last 10 runs of {job} took {seconds:.0f} s on average" not in said
        ],
        "took 200 s on average" in said,
        "Service Image" in said,
    ) == (0, [], True, False)


def _release_reads(api: GitHubApiFake) -> list[str]:
    """The requests for the listing of the runs of release.yml and for the jobs of its runs."""
    return [line for line in api.requested if "release.yml" in line or "/actions/runs/2" in line]


def test_the_checks_of_one_workflow_ask_for_the_jobs_of_each_run_one_time(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The six release image checks share one read of release.yml: the runs are listed one time,
    and the jobs of each run are asked for one time, up to the tenth release run (#6734)."""
    _route_runs(github_api, [200.0] * 20)
    ids = _route_release_runs(github_api)

    cli("ci", "job-time", "--repo", _REPO)

    assert _release_reads(github_api) == [f"GET https://api.github.com{_RELEASE_RUNS}"] + [
        f"GET https://api.github.com{_jobs_path(run_id)}" for run_id in ids[:19]
    ]


def test_a_job_with_its_runs_takes_no_older_run_while_the_read_continues_for_another_job(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The third release run skipped `Runner Image / Attest & Tag`, as when Verify fails. So the
    read continues to the eleventh release run, which gives that job its tenth run, and stops
    there. `Runner Image / Build` took 900 s in that run, but it had its 10 runs before, so its
    mean covers only its newest 10 runs (#6734)."""
    build, attest = "Runner Image / Build", "Runner Image / Attest & Tag"
    _route_runs(github_api, [200.0] * 20)
    ids = _route_release_runs(github_api, {build: 200.0}, count=12)
    skipped = _job(attest, "2026-10-29T10:00:01Z", "2026-10-29T10:00:00Z", "skipped")
    _route_jobs(
        github_api,
        ids[4],
        [skipped if job["name"] == attest else job for job in _release_jobs({build: 200.0})],
    )
    _route_jobs(github_api, ids[20], _release_jobs({build: 900.0}))

    result = cli("ci", "job-time", "--repo", _REPO)

    said = _said(result)
    assert (
        result.exit_code,
        f"The last 10 runs of {build} took 200 s on average" in said,
        f"The last 10 runs of {attest} took 300 s on average" in said,
        _release_reads(github_api),
    ) == (
        0,
        True,
        True,
        [f"GET https://api.github.com{_RELEASE_RUNS}"]
        + [f"GET https://api.github.com{_jobs_path(run_id)}" for run_id in ids[:21]],
    )


def test_a_read_that_finds_no_release_image_job_stops_after_a_fixed_count_of_runs(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """No run of release.yml holds a release image job, as when a job is renamed. The read asks
    for the jobs of the first `DEFAULT_CI_JOB_TIME_MAX_RUNS` runs only, reads no second page of
    the listing, exits 1 and names the bound, so the daily job ends inside its timeout (#6734)."""
    bound = defaults.DEFAULT_CI_JOB_TIME_MAX_RUNS
    _route_runs(github_api, [200.0] * 20)
    ids = list(range(5000, 5000 + bound + 50))
    second_page = "/repositories/1/actions/workflows/7/runs?page=2"
    runs = [{"id": run_id, "head_branch": "main", "event": "push"} for run_id in ids]
    github_api.route(
        "GET",
        _RELEASE_RUNS,
        github_json(
            {"total_count": len(ids), "workflow_runs": runs[:bound]},
            headers=next_page(second_page),
        ),
    )
    github_api.route(
        "GET", second_page, github_json({"total_count": len(ids), "workflow_runs": runs[bound:]})
    )
    for run_id in ids:
        _route_jobs(github_api, run_id, _no_release_jobs())

    result = cli("ci", "job-time", "--repo", _REPO)

    said = _said(result)
    assert (
        result.exit_code,
        [line for line in github_api.requested if "/actions/runs/5" in line],
        [line for line in github_api.requested if second_page in line],
        "Only 0 of the last 10 runs of MCP Server Image / Build could be read" in said,
        f"after the jobs of {bound} runs" in said,
    ) == (
        1,
        [f"GET https://api.github.com{_jobs_path(run_id)}" for run_id in ids[:bound]],
        [],
        True,
        True,
    )


def test_the_command_files_one_p0_issue_for_a_release_image_job_over_the_limit(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """`Runner Image / Verify` averages 380 s over 10 release runs, over the 360 s limit: with
    --file-issue the command files one P0 issue for that job with the four labels, and exits 1."""
    _route_runs(github_api, [200.0] * 20)
    _route_release_runs(github_api, {"Runner Image / Verify": 380.0})
    _route_alarm_search(github_api)
    github_api.route("POST", f"/repos/{_REPO}/issues", github_json({"number": 99}, status=201))

    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    [(path, issue)] = _posted(github_api)
    assert (
        result.exit_code,
        path,
        issue["title"],
        issue["labels"],
        "took 380 s on average. The limit is 360 s." in issue["body"],
        f"https://github.com/{_REPO}/issues/99" in _said(result),
    ) == (
        1,
        f"/repos/{_REPO}/issues",
        "fix(ci): Runner Image / Verify averages 380 s, over the 360 s limit",
        ["type/bug", "scope/ci", "status/new", "priority/p0-critical"],
        True,
        True,
    )


def test_a_release_image_job_at_the_limit_makes_no_issue_request(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """`Runner Image / Build` takes 360 s in each of the 10 release runs: the mean is on the limit,
    so with --file-issue the command exits 0 and searches and files no issue."""
    _route_runs(github_api, [200.0] * 20)
    _route_release_runs(github_api, {"Runner Image / Build": 360.0})

    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    assert (
        result.exit_code,
        [line for line in github_api.requested if "search" in line],
        _posted(github_api),
    ) == (0, [], [])


def test_the_command_exits_1_when_fewer_release_runs_than_wanted_exist(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """The test job has 20 runs, but only 2 runs of release.yml made a release: the command exits 1,
    says that only 2 of the last 10 runs could be read, and with --file-issue makes no issue
    request."""
    _route_runs(github_api, [200.0] * 20)
    _route_release_runs(github_api, count=2)

    result = cli("ci", "job-time", "--repo", _REPO, "--file-issue")

    assert (
        result.exit_code,
        "Only 2 of the last 10 runs of MCP Server Image / Build could be read" in _said(result),
        [line for line in github_api.requested if "search" in line],
        _posted(github_api),
    ) == (1, True, [], [])


def test_an_option_narrows_the_run_to_one_check(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """An option such as --workflow, --job or --runs narrows the run to that one check and reads
    no other job."""
    _route_release_runs(github_api, {"Runner Image / Build": 200.0})

    result = cli(
        "ci",
        "job-time",
        "--repo",
        _REPO,
        "--workflow",
        "release.yml",
        "--job",
        "Runner Image / Build",
        "--runs",
        "5",
    )

    said = _said(result)
    assert (
        result.exit_code,
        "The last 5 runs of Runner Image / Build took 200 s on average" in said,
        "Tests & Coverage" in said,
        "Runner Image / Verify" in said,
        "MCP Server Image" in said,
    ) == (0, True, False, False, False)


def test_a_dry_run_lists_one_plan_for_each_read(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """A dry run with no option lists two plans: the read of the test job of ci.yml, and the one
    read of release.yml that serves the six release image jobs (#6734)."""
    result = cli("ci", "job-time", "--repo", _REPO, "--dry-run")

    said = _said(result)
    assert (
        result.exit_code,
        github_api.requested,
        said.count("actions/workflows/ci.yml/runs"),
        said.count("actions/workflows/release.yml/runs"),
        [job for job in _RELEASE_IMAGE_JOBS if job not in said],
    ) == (0, [], 1, 1, [])
