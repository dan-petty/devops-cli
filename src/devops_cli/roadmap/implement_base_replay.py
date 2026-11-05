"""The results of the exit checks that the PR comment of a step shows (#3042).

A behavior group's test files must fail on the base commit of the group, before the change. The
replay runs them on that base, with the tests of the head overlaid (`devops_cli.ci.fail_to_pass`),
and `judge_replay` reads the outcome of each test. A test that fails in its call phase proves the
group. A test that passes, or that stops with an error before its assertion, does not. A replay that could not run proves
nothing. A group of kind `other` keeps the output of its verify commands as a `VerifiedCommand`.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from devops_cli.ci.fail_to_pass import BaseReplayRun, replay_on_base

# The head whose tests are overlaid on the base: the working tree, with its staged files (#3042).
REPLAY_HEAD = "HEAD"


class BaseStatus(StrEnum):
    """What the replay of a behavior group's test files on the base commit shows."""

    FAILS = "fails_on_base"
    PASSES = "passes_on_base"
    ERRORS = "errors_on_base"
    NOT_RUN = "not_run"


class BaseReplay(BaseModel):
    """The replay of a behavior group's test files on its base commit. `failed` names the tests
    that failed in their call phase there, `exit_status` is pytest's, and `output` is the tail of
    its output when the run could not run."""

    model_config = ConfigDict(frozen=True)

    files: tuple[str, ...]
    status: BaseStatus
    failed: tuple[str, ...] = ()
    exit_status: int
    output: str = ""


class VerifiedCommand(BaseModel):
    """A verify command of a group of kind `other` that passed, with its exit status and the
    masked, bounded tail of its output."""

    model_config = ConfigDict(frozen=True)

    command: str
    status: int
    output: str = ""


def judge_replay(files: Sequence[str], run: BaseReplayRun) -> BaseReplay:
    """The result of a replay of `files`: a test that failed in its call phase proves the group,
    a collection error does not, and a run that could not run gives no result."""
    failed = tuple(outcome.test_id for outcome in run.outcomes if outcome.status == "failed")
    output = run.could_not_run.output_tail if run.could_not_run is not None else ""
    return BaseReplay(
        files=tuple(files),
        status=_status(run, failed),
        failed=failed,
        exit_status=run.exit_status,
        output=output,
    )


def _status(run: BaseReplayRun, failed: tuple[str, ...]) -> BaseStatus:
    """The status of a replay: the first of these that holds decides it."""
    if run.could_not_run is not None:
        return BaseStatus.NOT_RUN
    if failed:
        return BaseStatus.FAILS
    if any(outcome.status == "errored" for outcome in run.outcomes):
        return BaseStatus.ERRORS
    if run.outcomes:
        return BaseStatus.PASSES
    return BaseStatus.NOT_RUN


def replay_group_tests(root: Path, base: str, files: Sequence[str]) -> BaseReplay:
    """Replay `files` on the commit `base` of the checkout `root`, and judge the result (#3042)."""
    return judge_replay(files, replay_on_base(root, base, REPLAY_HEAD, files))
