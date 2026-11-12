"""No program that a git configuration file names sees the GitHub token of the implement job (GHSA).

The agent of a step runs as the user of the Job, so it can write the git configuration of the home
folder and of the clone. Git runs for real through the process runner, which pins the session's
token (`PINNED_GITHUB_TOKEN`) on the git children that it gives a token. Each planted program
writes the `GH_TOKEN` that it sees into one file.
"""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from devops_cli.core.process import DefaultProcessRunner
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.github_identity import PINNED_GITHUB_TOKEN
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    BRANCH,
    JobWorld,
    group_one_calls,
    group_two_calls,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

HOOKS = ("pre-commit", "post-commit", "pre-push", "reference-transaction")


def _through_the_runner(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """Run a git call through the real process runner, which builds the environment of the child
    and pins the token, as in a Job."""
    stdin = call.stdin if isinstance(call.stdin, str) else None
    return DefaultProcessRunner().run(
        list(call.argv),
        input=stdin,
        cwd=call.cwd,
        env=call.env,
        timeout=call.timeout,
        isolate_env=call.isolate_env,
        extra_allowed_env=call.extra_allowed_env or None,
        quiet=True,
    )


def _recorder(path: Path, capture: Path, name: str) -> Path:
    """A program that reads its input and adds `<name> <GH_TOKEN or none>` to `capture`."""
    path.write_text(
        f"#!/bin/sh\ncat >/dev/null\nprintf '%s %s\\n' '{name}' \"${{GH_TOKEN:-none}}\" >> '{capture}'\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _plants(folder: Path, capture: Path) -> tuple[Path, Path]:
    """A hook folder with each hook of `HOOKS`, and a credential helper."""
    hooks = folder / "hooks"
    hooks.mkdir(parents=True)
    for name in HOOKS:
        _recorder(hooks / name, capture, name)
    helper = _recorder(folder / "helper", capture, "helper")
    return hooks, helper


def _fresh_quota(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """GitHub's answer to `gh api rate_limit`: a full quota, which resets in a day."""
    reset = int(time.time()) + 86400
    resource = {"limit": 5000, "remaining": 5000, "used": 0, "reset": reset}
    body = {"resources": {name: resource for name in ("core", "graphql", "search")}}
    return subprocess.CompletedProcess(list(call.argv), 0, json.dumps(body), "")


@pytest.fixture
def real_git(planned_world: JobWorld) -> JobWorld:
    """The Planned world, with each git call through the real process runner. A read of the quota
    gets a full quota: the git calls of a run with planted programs take real time."""
    planned_world.programs.answer("git", ProcessAnswer(side_effect=_through_the_runner))
    planned_world.programs.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(side_effect=_fresh_quota)
    )
    return planned_world


@pytest.fixture
def home_gitconfig() -> Iterator[Path]:
    """The git configuration of the home folder of the test run, put back as it was after the
    test. The home folder stays the one of the run, so no other reader of `HOME` changes."""
    gitconfig = Path.home() / ".gitconfig"
    before = gitconfig.read_text(encoding="utf-8") if gitconfig.exists() else None
    try:
        yield gitconfig
    finally:
        if before is None:
            gitconfig.unlink(missing_ok=True)
        else:
            gitconfig.write_text(before, encoding="utf-8")


def test_no_program_that_the_home_folder_names_sees_the_token(
    real_git: JobWorld, tmp_path: Path, home_gitconfig: Path
) -> None:
    """A turn of the agent writes hooks and a credential helper into the git configuration of the
    home folder. The run pushes its branch, and none of them sees the token: a local git call gets
    no token, and a network call reads no configuration file of the home folder. The job reads the
    home folder before the first turn too, when a Job has a new one, so the plant waits for it."""
    capture = tmp_path / "capture.txt"
    hooks, helper = _plants(tmp_path / "planted", capture)

    def plant() -> None:
        with home_gitconfig.open("a", encoding="utf-8") as config:
            config.write(f"[core]\n\thooksPath = {hooks}\n[credential]\n\thelper = {helper}\n")

    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
        effects={2: plant},
    )

    applied = real_git.run(script)

    seen = capture.read_text(encoding="utf-8") if capture.exists() else ""
    assert (applied.ready, applied.stopped, applied.failed) == ((1,), (), ())
    assert real_git.repo.origin_git("rev-parse", "--verify", f"refs/heads/{BRANCH}")
    assert ("pre-commit none" in seen, PINNED_GITHUB_TOKEN in seen) == (True, False)


def test_no_program_that_the_configuration_of_the_clone_names_sees_the_token(
    real_git: JobWorld, tmp_path: Path
) -> None:
    """A turn of the agent writes a hook folder and a credential helper into the configuration of
    the clone. No hook and no helper sees the token in the rest of the run."""
    capture = tmp_path / "capture.txt"
    hooks, helper = _plants(tmp_path / "planted", capture)

    def plant() -> None:
        real_git.repo.git("config", "core.hooksPath", str(hooks))
        real_git.repo.git("config", "credential.helper", str(helper))

    script = ModelScript(
        tool_calls(*group_one_calls()),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
        effects={2: plant},
    )

    real_git.run(script)

    seen = capture.read_text(encoding="utf-8") if capture.exists() else ""
    assert PINNED_GITHUB_TOKEN not in seen
