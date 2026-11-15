"""The run of the trials of a Harbor task (#3104): the argv of the harbor run, the reward and the
cost of each trial, and the report of the run under the data directory."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from devops_cli.exceptions.roadmap import ImplementEvalError
from devops_cli.roadmap.implement.implement_eval import load_case
from tests.support.fakes.process import ProcessAnswer, ProcessFake
from tests.support.roadmap_eval import write_fixture

TASK_TIMEOUT_SECONDS = 600
# The Coder harness of the Service, as Harbor loads a custom agent by its import path.
CODER_AGENT = "pydantic_ai_harness.coder:Coder"
TRIALS = 5
COSTS = (0.5, 1.0, 1.5, 2.0)


def _task(tmp_path: Path) -> Path:
    """The task folder of the sample fixture, as the export writes it."""
    from devops_cli.roadmap.implement.implement_eval_harbor import export_task

    return export_task(
        load_case(write_fixture(tmp_path / "fixture")),
        tmp_path / "tasks" / "sample",
        timeout_seconds=TASK_TIMEOUT_SECONDS,
    )


def _trial(job: Path, name: str, *, reward: float | None, cost: float | None) -> Path:
    """Write the result of one trial of the job, as the pinned Harbor version writes it."""
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    folder = job / name
    folder.mkdir(parents=True)
    result = {
        "verifier_result": None if reward is None else {"rewards": {run.REWARD_KEY: reward}},
        "agent_result": None if cost is None else {"cost_usd": cost},
    }
    (folder / run.TRIAL_RESULT_FILE).write_text(json.dumps(result), encoding="utf-8")
    return folder


def test_five_trials_of_one_task(tmp_path: Path, process_fake: ProcessFake) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    task = _task(tmp_path)
    out = tmp_path / "run"
    argv = [
        "harbor",
        "run",
        "--path",
        str(task),
        "--n-attempts",
        str(TRIALS),
        "--agent",
        CODER_AGENT,
        "--model",
        run.DEFAULT_MODEL,
        "--env",
        run.DEFAULT_PROVIDER,
        "--jobs-dir",
        str(out),
        "--job-name",
        run.JOB_NAME,
        "--yes",
    ]

    assert (
        run.harbor_argv(task, TRIALS, CODER_AGENT, run.DEFAULT_MODEL, run.DEFAULT_PROVIDER, out)
        == argv
    )
    _trial(out / run.JOB_NAME, "sample__aaaaaaa", reward=1.0, cost=COSTS[0])
    process_fake.answer("harbor", ProcessAnswer(returncode=0))

    report = run.run_trials(task, TRIALS, CODER_AGENT, run.DEFAULT_MODEL, run.DEFAULT_PROVIDER, out)

    assert [call.argv for call in process_fake.calls] == [tuple(argv)]
    assert process_fake.calls[0].timeout == (TRIALS + 1) * 3 * TASK_TIMEOUT_SECONDS
    assert report.trial_count == 1


def test_four_trials_three_of_them_pass(tmp_path: Path, process_fake: ProcessFake) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    task = _task(tmp_path)
    out = tmp_path / "run"
    job = out / run.JOB_NAME
    for index, (reward, cost) in enumerate(zip((1.0, 0.0, 1.0, 1.0), COSTS, strict=True)):
        _trial(job, f"sample__{index:07d}", reward=reward, cost=cost)
    process_fake.answer("harbor", ProcessAnswer(returncode=0))

    report = run.run_trials(
        task, len(COSTS), run.DEFAULT_AGENT, run.DEFAULT_MODEL, run.DEFAULT_PROVIDER, out
    )

    assert report.pass_rate == 0.75
    assert report.trial_count == 4
    assert report.total_cost_usd == sum(COSTS)
    assert report.rewards == (1.0, 0.0, 1.0, 1.0)
    written = json.loads((out / run.REPORT_FILE).read_text(encoding="utf-8"))
    assert written == {
        "pass_rate": 0.75,
        "trial_count": 4,
        "total_cost_usd": sum(COSTS),
        "rewards": [1.0, 0.0, 1.0, 1.0],
    }


def test_the_reward_and_the_cost_of_each_trial_are_read(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    job = tmp_path / "job"
    _trial(job, "sample__bbbbbbb", reward=0.0, cost=COSTS[1])

    assert run.read_trials(job) == (run.HarborTrial(reward=0.0, cost_usd=COSTS[1]),)


def test_a_trial_with_no_reward_is_refused(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    job = tmp_path / "job"
    _trial(job, "sample__aaaaaaa", reward=None, cost=COSTS[0])

    with pytest.raises(ImplementEvalError) as raised:
        run.read_trials(job)

    assert raised.value.exit_code == 1
    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    assert "sample__aaaaaaa" in str(raised.value)
    assert "reward" in str(raised.value)


def test_a_trial_with_no_cost_is_refused(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    job = tmp_path / "job"
    _trial(job, "sample__aaaaaaa", reward=1.0, cost=None)

    with pytest.raises(ImplementEvalError) as raised:
        run.read_trials(job)

    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    assert "cost" in str(raised.value)


def test_a_job_with_no_trial_is_refused(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    job = tmp_path / "job"
    job.mkdir()

    with pytest.raises(ImplementEvalError) as raised:
        run.read_trials(job)

    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    assert "job" in str(raised.value)


def test_a_failed_harbor_run_is_refused(tmp_path: Path, process_fake: ProcessFake) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    task = _task(tmp_path)
    out = tmp_path / "run"
    process_fake.answer("harbor", ProcessAnswer(returncode=2, stderr="Cannot connect to Docker\n"))

    with pytest.raises(ImplementEvalError) as raised:
        run.run_trials(task, 1, run.DEFAULT_AGENT, run.DEFAULT_MODEL, run.DEFAULT_PROVIDER, out)

    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    assert "Cannot connect to Docker" in str(raised.value)
    assert not (out / run.REPORT_FILE).exists()


def test_a_task_with_no_time_limit_is_refused(tmp_path: Path) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    task = tmp_path / "task"
    task.mkdir()

    with pytest.raises(ImplementEvalError) as raised:
        run.run_trials(
            task, 1, run.DEFAULT_AGENT, run.DEFAULT_MODEL, run.DEFAULT_PROVIDER, tmp_path / "run"
        )

    assert raised.value.error_code == "ROADMAP_EVAL_REFUSED"
    assert "task.toml" in str(raised.value)


def test_the_report_folder_lies_under_the_data_directory(isolate_data_dir: Path) -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    assert run.report_directory() == isolate_data_dir / "eval" / "harbor"


def test_the_run_folder_lies_under_the_report_folder() -> None:
    from devops_cli.roadmap.implement import implement_eval_harbor_run as run

    folder = run.run_directory(datetime(2026, 11, 1, 12, 30, 5, tzinfo=UTC))

    assert folder.parent == run.report_directory()
    assert folder.name.startswith("harbor-20261101-123005-")
