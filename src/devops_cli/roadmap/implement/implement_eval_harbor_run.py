"""The run of the trials of a Harbor task (#3104).

Harbor (`harbor-framework/harbor`) runs one agent on one task in a container, N times, and writes
the reward and the cost of each trial. `implement_eval_harbor` exports an implement fixture as a
task folder; this module runs the trials of that folder with the harbor program, reads their
rewards and writes the pass rate and the cost of the run as `result.json` under the data
directory.

The program goes through `run_subprocess`, so a test answers harbor and the Docker engine through
the process fake and starts no program. The flags and the files are those of the pinned Harbor
version of `pyproject.toml`: a correction of that version changes one function here and its test.

The harbor program gets the isolated environment of a child, so this command passes it no
credential of the process. The first real run of a person confirms how the agent of the task gets
its model credential, as the proposal of #3104 records.
"""

from __future__ import annotations

import json
import tempfile
import tomllib
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.core.process import run_subprocess
from devops_cli.exceptions.roadmap import ImplementEvalError
from devops_cli.roadmap.implement.implement_eval_harbor import TASK_CONFIG_FILE
from devops_cli.roadmap.verification_command import shown

HARBOR_BIN = "harbor"
# The folder of the reports of the runs, under the data directory, and the file of one report.
REPORTS_FOLDER = "eval/harbor"
REPORT_FILE = "result.json"
# The name of the job that harbor makes in the folder of a run, and the file of the result of one
# trial of that job.
JOB_NAME = "implement-eval"
TRIAL_RESULT_FILE = "result.json"
# The key that the pinned Harbor version gives the reward that the test script of the task writes.
REWARD_KEY = "reward"
# The agent of a trial: the Coder harness of the Service, which Harbor loads by its import path
# (`module.path:ClassName`). The model is the default tier of the implement task. The first real run
# of a person confirms both, as the proposal of #3104 says.
DEFAULT_AGENT = "pydantic_ai_harness.coder:Coder"
DEFAULT_MODEL = "devops-coder"
# The sandbox provider of a trial: the Docker engine of the workstation.
DEFAULT_PROVIDER = "docker"


class HarborTrial(BaseModel):
    """One trial of a task: the reward that its test script wrote, and the cost of its agent."""

    model_config = ConfigDict(frozen=True)

    reward: float
    cost_usd: float


class HarborReport(BaseModel):
    """The report of a run: the share of its trials that passed, their count, their total cost, and
    the reward of each trial in the order of its name."""

    model_config = ConfigDict(frozen=True)

    pass_rate: float
    trial_count: int
    total_cost_usd: float
    rewards: tuple[float, ...]


def harbor_argv(
    task: Path, trials: int, agent: str, model: str, provider: str, out: Path
) -> list[str]:
    """The argv of the run of the pinned Harbor version: the task folder, the count of its trials,
    the agent, its model, the sandbox provider and the folder of the job.

    `--n-attempts` is the count of trials that Harbor makes of one task, and `--yes` answers its
    prompts, because the command runs with no terminal.
    """
    return [
        HARBOR_BIN,
        "run",
        "--path",
        str(task),
        "--n-attempts",
        str(trials),
        "--agent",
        agent,
        "--model",
        model,
        "--env",
        provider,
        "--jobs-dir",
        str(out),
        "--job-name",
        JOB_NAME,
        "--yes",
    ]


def read_trials(folder: Path) -> tuple[HarborTrial, ...]:
    """The reward and the cost of each trial of the job in `folder`, in the order of the names of
    its trials. A job with no trial result is refused, because a run with no trial has no pass
    rate."""
    paths = sorted(folder.glob(f"*/{TRIAL_RESULT_FILE}"))
    if not paths:
        raise ImplementEvalError(
            f"The job folder {folder} holds no trial result ({TRIAL_RESULT_FILE})."
        )
    return tuple(_trial(path) for path in paths)


def run_trials(
    task: Path, trials: int, agent: str, model: str, provider: str, out: Path
) -> HarborReport:
    """Run `trials` trials of the task folder `task` with the harbor program, write the report of
    the run as `result.json` in `out`, and return it. A harbor run that fails is refused, and so is
    a trial with no reward or no cost."""
    out.mkdir(parents=True, exist_ok=True)
    done = run_subprocess(
        harbor_argv(task, trials, agent, model, provider, out),
        timeout=_run_timeout(task, trials),
    )
    if done.returncode:
        raise ImplementEvalError(
            f"The harbor run exited {done.returncode}: {shown(_last_line(done.stderr or done.stdout))}"
        )
    report = _report(read_trials(out / JOB_NAME))
    (out / REPORT_FILE).write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return report


def report_directory() -> Path:
    """The folder of the reports, under the data directory."""
    from devops_cli.config.settings import load_settings
    from devops_cli.core.repo import resolve_data_path

    return resolve_data_path(load_settings().data.dir) / REPORTS_FOLDER


def run_directory(moment: datetime) -> Path:
    """A new folder of one run under the report folder, whose name starts with `moment`, so that
    two runs of the same second keep two folders."""
    parent = report_directory()
    parent.mkdir(parents=True, exist_ok=True)
    stamp = moment.strftime("%Y%m%d-%H%M%S")
    return Path(tempfile.mkdtemp(prefix=f"harbor-{stamp}-", dir=parent))


def _trial(path: Path) -> HarborTrial:
    """The reward and the cost of one trial result. A result that lacks either is refused, because
    a trial that no verifier and no agent recorded would read as a clean one."""
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        reward = result["verifier_result"]["rewards"][REWARD_KEY]
        cost = result["agent_result"]["cost_usd"]
        return HarborTrial(reward=float(reward), cost_usd=float(cost))
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise ImplementEvalError(
            f"Trial {path.parent.name}: {path.name} holds no reward or no cost ({exc})."
        ) from exc


def _report(trials: Sequence[HarborTrial]) -> HarborReport:
    """The report of the trials: the share of them that passed, their count, their total cost, and
    the reward of each one."""
    rewards = tuple(trial.reward for trial in trials)
    return HarborReport(
        pass_rate=sum(1 for reward in rewards if reward == 1.0) / len(rewards),
        trial_count=len(rewards),
        total_cost_usd=sum(trial.cost_usd for trial in trials),
        rewards=rewards,
    )


def _run_timeout(task: Path, trials: int) -> float:
    """The time that the harbor program may take for `trials` trials: the three time limits of the
    task, once for each trial and once more for the build of its image. The export writes them into
    `task.toml`, so a run holds no limit of its own. A task folder that holds no such limit is
    refused."""
    try:
        config = tomllib.loads((task / TASK_CONFIG_FILE).read_text(encoding="utf-8"))
        limit = (
            float(config["environment"]["build_timeout_sec"])
            + float(config["agent"]["timeout_sec"])
            + float(config["verifier"]["timeout_sec"])
        )
    except (OSError, UnicodeDecodeError, ValueError, KeyError, TypeError) as exc:
        raise ImplementEvalError(
            f"The task folder {task} holds no readable time limit in {TASK_CONFIG_FILE} ({exc})."
        ) from exc
    return limit * (trials + 1)


def _last_line(text: str) -> str:
    """The last line that the harbor program printed."""
    lines = text.strip().splitlines()
    return lines[-1] if lines else ""
