"""The hooks of the repository, run by the Job as a child (#3043): the argv of the stage run, the
environment of the child, a hook that fixes a file, the exit codes, and the bound of the output.

Git runs for real on a checkout in `tmp_path`. `pre-commit` is answered by `process_fake`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from devops_cli.config.constants import CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS
from devops_cli.roadmap.implement_hooks import (
    HookRun,
    commit_stage,
    hook_environment,
    install_hook_environments,
    stage_run,
)
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.implement_step import command_text, git

STAGE = "uv run pre-commit run --hook-stage pre-commit"
TOKEN = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"


@pytest.fixture
def checkout(implement_checkout: Path) -> Path:
    return implement_checkout


@pytest.fixture
def programs(implement_programs: ProcessFake) -> ProcessFake:
    return implement_programs


@pytest.fixture
def cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """The cache directory of the data directory, where the hook environments live."""
    root = tmp_path / "data"
    monkeypatch.setenv("DEVOPS_CLI_DATA_DIR", str(root))
    return root / "cache"


def _stage_runs(programs: ProcessFake) -> list[ProcessCall]:
    return [call for call in programs.calls if command_text(call).startswith(STAGE)]


def _hooks_answer(programs: ProcessFake, *answers: ProcessAnswer) -> None:
    """The answers of the successive runs of the stage; the last one repeats."""
    queue = list(answers)

    def answer(_call: ProcessCall) -> ProcessAnswer:
        return queue.pop(0) if len(queue) > 1 else queue[0]

    programs.answer(lambda call: command_text(call).startswith(STAGE), answer)


def _fix_the_file(path: Path) -> Callable[[ProcessCall], subprocess.CompletedProcess[str]]:
    """A hook that adds a newline to `path` and exits 1, as `end-of-file-fixer` does."""

    def run(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        return subprocess.CompletedProcess(call.argv, 1, stdout="fix end of files...Failed\n")

    return run


def test_the_environment_puts_the_hook_home_under_the_cache(cache: Path) -> None:
    assert hook_environment() == {"PRE_COMMIT_HOME": str(cache / "pre-commit")}


def test_the_commit_stage_runs_pre_commit_on_the_staged_files_and_passes(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    (checkout / "src" / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    git(checkout, "add", "-A")

    failure = commit_stage(checkout)

    runs = _stage_runs(programs)
    assert (failure, len(runs), runs[0].cwd, runs[0].env) == (
        None,
        1,
        checkout,
        {"PRE_COMMIT_HOME": str(cache / "pre-commit")},
    )


def test_the_hooks_run_in_no_git_client(checkout: Path, programs: ProcessFake, cache: Path) -> None:
    """A git client gets the token of the session. The hooks run as `uv`, so they get none."""
    commit_stage(checkout)

    assert {call.argv[0] for call in _stage_runs(programs)} == {"uv"}


def test_a_fix_of_a_hook_reaches_the_index(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    target = checkout / "src" / "other.py"
    target.write_text("OTHER = 2", encoding="utf-8")
    git(checkout, "add", "-A")
    fixed = {"done": False}

    def run(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        if fixed["done"]:
            return subprocess.CompletedProcess(call.argv, 0, stdout="", stderr="")
        fixed["done"] = True
        return _fix_the_file(target)(call)

    programs.answer(
        lambda call: command_text(call).startswith(STAGE), ProcessAnswer(side_effect=run)
    )

    failure = commit_stage(checkout)

    assert (
        failure,
        len(_stage_runs(programs)),
        git(checkout, "cat-file", "-s", ":src/other.py"),
        git(checkout, "diff", "--name-only"),
    ) == (None, 2, str(len("OTHER = 2\n")), "")


def test_a_failure_with_no_fixed_file_runs_the_stage_once(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    _hooks_answer(programs, ProcessAnswer(returncode=1, stdout="ast-grep scan...Failed\n"))

    failure = commit_stage(checkout)

    assert failure is not None
    assert (failure.returncode, failure.repairable, "ast-grep scan...Failed" in failure.output) == (
        1,
        True,
        True,
    )
    assert len(_stage_runs(programs)) == 1


def test_a_failure_after_a_fix_is_the_result_of_the_second_run(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    target = checkout / "src" / "other.py"
    target.write_text("OTHER = 2", encoding="utf-8")
    git(checkout, "add", "-A")
    calls = {"count": 0}

    def run(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        calls["count"] += 1
        if calls["count"] == 1:
            return _fix_the_file(target)(call)
        return subprocess.CompletedProcess(call.argv, 1, stdout="check yaml...Failed\n")

    programs.answer(
        lambda call: command_text(call).startswith(STAGE), ProcessAnswer(side_effect=run)
    )

    failure = commit_stage(checkout)

    assert failure is not None
    assert (calls["count"], "check yaml...Failed" in failure.output) == (2, True)


def test_any_other_exit_code_is_not_repairable(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    _hooks_answer(programs, ProcessAnswer(returncode=3, stderr="An unexpected error has occurred"))

    failure = commit_stage(checkout)

    assert failure is not None
    assert (failure.returncode, failure.repairable, len(_stage_runs(programs))) == (3, False, 1)
    assert "An unexpected error has occurred" in failure.output


def test_the_output_is_masked_and_cut_from_its_start(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    long = "start of the output\n" + "x" * CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS
    _hooks_answer(programs, ProcessAnswer(returncode=1, stdout=f"{long}\ntoken {TOKEN}\n"))

    failure = commit_stage(checkout)

    assert failure is not None
    assert (
        len(failure.output) <= CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS,
        "start of the output" in failure.output,
        TOKEN in failure.output,
    ) == (True, False, False)


def test_a_stage_run_names_the_stage_and_the_refs(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    run = stage_run(checkout, "pre-push", "--from-ref", "origin/main", "--to-ref", "HEAD")

    assert run == HookRun(returncode=0, output="")
    assert [command_text(call) for call in programs.calls if "pre-commit" in call.argv] == [
        "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD"
    ]


def test_the_install_runs_install_hooks_in_the_hook_home(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    assert install_hook_environments(checkout) is None

    calls = [call for call in programs.calls if "pre-commit" in call.argv]
    assert [(command_text(call), call.cwd, call.env) for call in calls] == [
        (
            "uv run pre-commit install-hooks",
            checkout,
            {"PRE_COMMIT_HOME": str(cache / "pre-commit")},
        )
    ]


def test_a_failed_install_gives_its_output(
    checkout: Path, programs: ProcessFake, cache: Path
) -> None:
    programs.answer(
        lambda call: "install-hooks" in call.argv,
        ProcessAnswer(returncode=1, stderr="could not resolve host example.com"),
    )

    failure = install_hook_environments(checkout)

    assert failure is not None
    assert "could not resolve host example.com" in failure
