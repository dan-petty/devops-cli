"""Tests for `devops ci job-time`: the check that fails when the last runs of a CI job, read from
GitHub's Actions API, average more than the limit (#2699).

GitHub's API is the fake of the `github_api` fixture, so each case runs the real session, client
and command over answers that the test gives. The recorded runs and jobs are those of the
`Tests & Coverage` job on `main` on 2026-10-30.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest
import yaml

from devops_cli.ci.job_time import JobTimeReport, check_job_time
from devops_cli.github.client import JobRunTime
from devops_cli.github.session import get_github_session
from tests.support.fakes.github import github_json, next_page
from tests.support.paths import FIXTURES, REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Callable
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


def _route_runs(api: GitHubApiFake, seconds: list[float | None]) -> list[int]:
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
    """Twenty runs of 100 s average 100 s, well inside the default limit of 300 s."""
    _route_runs(github_api, [100.0] * 20)

    result = cli("ci", "job-time", "--repo", _REPO)

    assert (
        result.exit_code,
        "took 100 s on average" in _said(result),
        "limit is 300 s" in _said(result),
    ) == (0, True, True)


def test_the_command_exits_1_and_names_the_mean_when_the_job_is_over_the_limit(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Twenty runs of 400 s average 400 s: the check fails and the output says by how much."""
    _route_runs(github_api, [400.0] * 20)

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


def test_the_command_exits_1_when_fewer_runs_than_wanted_exist(
    github_api: GitHubApiFake, cli: Callable[..., Any]
) -> None:
    """Three runs of 100 s are inside the limit, and still no pass: twenty were asked for."""
    _route_runs(github_api, [100.0] * 3)

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


def test_the_workflow_runs_the_check_on_the_schedule_and_by_hand_and_no_job_waits_for_it() -> None:
    """The job reads main's history, which no run of a push or a pull request changes. It runs on
    the daily schedule and on a manual run only, so no push run of main turns red for the mean of
    other runs (#4634). It reads with a token that can read the Actions runs and nothing else, and
    is the `needs` of no other job."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))
    job = workflow["jobs"]["job-time"]
    waiting = [
        name for name, other in workflow["jobs"].items() if "job-time" in other.get("needs", [])
    ]

    assert (
        job["if"],
        job["permissions"],
        [step["run"] for step in job["steps"] if "devops ci job-time" in step.get("run", "")],
        waiting,
    ) == (
        "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'",
        {"contents": "read", "actions": "read"},
        ['uv run devops ci job-time --repo "$GITHUB_REPOSITORY"'],
        [],
    )


def test_a_push_to_main_does_not_cancel_the_schedule_run() -> None:
    """The concurrency group of `ci.yml` holds the event, so the schedule run, which holds the
    check, and a push run of the same ref are in two groups (#4634). The group of a push holds its
    commit, so a merge cancels no push run of main, and each run ends and gives its test time to
    the check (#4639)."""
    workflow = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8"))

    assert workflow["concurrency"] == {
        "group": "ci-${{ github.workflow }}-${{ github.event_name }}-"
        "${{ github.event_name == 'push' && github.sha || github.ref }}",
        "cancel-in-progress": True,
    }


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
