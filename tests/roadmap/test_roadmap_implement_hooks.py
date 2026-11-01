"""The hooks of the repository, run by the Job as a child (#3043): the argv of the stage run, the
environment of the child, a hook that fixes a file, the exit codes, and the bound of the output.

Git runs for real on a checkout in `tmp_path`. `pre-commit` is answered by `process_fake`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

from devops_cli.config.constants import (
    CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS,
    CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS,
)
from devops_cli.exceptions import GitOperationError
from devops_cli.roadmap.implement_hooks import (
    HookRun,
    commit_stage,
    hook_environment,
    install_hook_environments,
    stage_run,
    trusted_config,
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


@pytest.fixture
def config(cache: Path) -> Path:
    """The trusted configuration that every run gets with `--config`."""
    return cache / "pre-commit-trusted-config.yaml"


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
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    (checkout / "src" / "other.py").write_text("OTHER = 2\n", encoding="utf-8")
    git(checkout, "add", "-A")

    failure = commit_stage(checkout, config)

    runs = _stage_runs(programs)
    assert (failure, len(runs), runs[0].cwd, runs[0].env) == (
        None,
        1,
        checkout,
        {"PRE_COMMIT_HOME": str(cache / "pre-commit")},
    )


def test_the_hooks_run_in_no_git_client(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    """A git client gets the token of the session. The hooks run as `uv`, so they get none."""
    commit_stage(checkout, config)

    assert {call.argv[0] for call in _stage_runs(programs)} == {"uv"}


def test_a_fix_of_a_hook_reaches_the_index(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
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

    failure = commit_stage(checkout, config)

    assert (
        failure,
        len(_stage_runs(programs)),
        git(checkout, "cat-file", "-s", ":src/other.py"),
        git(checkout, "diff", "--name-only"),
    ) == (None, 2, str(len("OTHER = 2\n")), "")


def test_a_failure_with_no_fixed_file_runs_the_stage_once(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    _hooks_answer(programs, ProcessAnswer(returncode=1, stdout="ast-grep scan...Failed\n"))

    failure = commit_stage(checkout, config)

    assert failure is not None
    assert (failure.returncode, failure.repairable, "ast-grep scan...Failed" in failure.output) == (
        1,
        True,
        True,
    )
    assert len(_stage_runs(programs)) == 1


def test_a_failure_after_a_fix_is_the_result_of_the_second_run(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
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

    failure = commit_stage(checkout, config)

    assert failure is not None
    assert (calls["count"], "check yaml...Failed" in failure.output) == (2, True)


def test_any_other_exit_code_is_not_repairable(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    _hooks_answer(programs, ProcessAnswer(returncode=3, stderr="An unexpected error has occurred"))

    failure = commit_stage(checkout, config)

    assert failure is not None
    assert (failure.returncode, failure.repairable, len(_stage_runs(programs))) == (3, False, 1)
    assert "An unexpected error has occurred" in failure.output


def test_the_output_is_masked_and_cut_from_its_start(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    long = "start of the output\n" + "x" * CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS
    _hooks_answer(programs, ProcessAnswer(returncode=1, stdout=f"{long}\ntoken {TOKEN}\n"))

    failure = commit_stage(checkout, config)

    assert failure is not None
    assert (
        len(failure.output) <= CONST_ROADMAP_IMPLEMENT_HOOK_OUTPUT_CHARS,
        "start of the output" in failure.output,
        TOKEN in failure.output,
    ) == (True, False, False)


def test_a_stage_run_names_the_stage_and_the_refs(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    run = stage_run(checkout, config, "pre-push", "--from-ref", "origin/main", "--to-ref", "HEAD")

    assert run == HookRun(returncode=0, output="")
    assert [command_text(call) for call in programs.calls if "pre-commit" in call.argv] == [
        "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD "
        f"--config {config}"
    ]


def test_the_install_runs_install_hooks_in_the_hook_home(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    assert install_hook_environments(checkout, config) is None

    calls = [call for call in programs.calls if "pre-commit" in call.argv]
    assert [(command_text(call), call.cwd, call.env) for call in calls] == [
        (
            f"uv run pre-commit install-hooks --config {config}",
            checkout,
            {"PRE_COMMIT_HOME": str(cache / "pre-commit")},
        )
    ]


def test_a_failed_install_gives_its_output(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    programs.answer(
        lambda call: "install-hooks" in call.argv,
        ProcessAnswer(returncode=1, stderr="could not resolve host example.com"),
    )

    failure = install_hook_environments(checkout, config)

    assert failure is not None
    assert "could not resolve host example.com" in failure


def test_every_run_names_the_trusted_configuration(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    commit_stage(checkout, config)
    install_hook_environments(checkout, config)

    runs = [command_text(call) for call in programs.calls if "pre-commit" in call.argv]
    assert runs
    assert all(run.endswith(f"--config {config}") for run in runs)


def test_a_stage_that_runs_out_of_time_is_a_failure_that_no_repair_fixes(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    def hang(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(call.argv, 1)

    programs.answer(
        lambda call: command_text(call).startswith(STAGE), ProcessAnswer(side_effect=hang)
    )

    failure = commit_stage(checkout, config)

    assert failure is not None
    assert (failure.repairable, len(_stage_runs(programs))) == (False, 1)
    assert f"ran out of time after {CONST_ROADMAP_IMPLEMENT_COMMAND_TIMEOUT_SECONDS} s" in (
        failure.output
    )


def test_an_install_that_runs_out_of_time_gives_its_reason(
    checkout: Path, programs: ProcessFake, cache: Path, config: Path
) -> None:
    def hang(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(call.argv, 1)

    programs.answer(lambda call: "install-hooks" in call.argv, ProcessAnswer(side_effect=hang))

    failure = install_hook_environments(checkout, config)

    assert failure is not None
    assert "install" in failure
    assert "ran out of time" in failure


CONFIG_FILE = ".pre-commit-config.yaml"


def _commit_config(checkout: Path, text: str) -> None:
    (checkout / CONFIG_FILE).write_text(text, encoding="utf-8")
    git(checkout, "add", "-A")
    git(checkout, "commit", "-q", "-m", "Set the hooks")


def test_the_trusted_configuration_is_the_one_that_the_commit_holds(
    checkout: Path, cache: Path
) -> None:
    _commit_config(checkout, "repos: []\n")

    path = trusted_config(checkout, "HEAD")

    assert path is not None
    assert (path.parent, path.read_text(encoding="utf-8")) == (cache, "repos: []\n")


def test_a_commit_with_no_configuration_has_no_hooks(checkout: Path, cache: Path) -> None:
    assert trusted_config(checkout, "HEAD") is None
    assert not cache.exists()


def test_an_agent_that_deletes_the_configuration_does_not_skip_the_hooks(
    checkout: Path, cache: Path
) -> None:
    _commit_config(checkout, "repos: []\n")
    (checkout / CONFIG_FILE).unlink()

    path = trusted_config(checkout, "HEAD")

    assert path is not None
    assert path.read_text(encoding="utf-8") == "repos: []\n"


def test_an_agent_that_edits_the_configuration_does_not_skip_the_hooks(
    checkout: Path, cache: Path
) -> None:
    """An edit to `repos: []` would make every hook pass. The commit decides, not the file."""
    _commit_config(checkout, "repos:\n  - repo: local\n")
    (checkout / CONFIG_FILE).write_text("repos: []\n", encoding="utf-8")

    path = trusted_config(checkout, "HEAD")

    assert path is not None
    assert path.read_text(encoding="utf-8") == "repos:\n  - repo: local\n"


def test_the_hooks_of_another_ref_are_those_of_that_ref(checkout: Path, cache: Path) -> None:
    _commit_config(checkout, "repos: []\n")

    assert (trusted_config(checkout, "HEAD") is not None, trusted_config(checkout, "HEAD~1")) == (
        True,
        None,
    )


def test_a_ref_that_git_cannot_read_is_an_error_not_a_repository_with_no_hooks(
    checkout: Path, cache: Path
) -> None:
    with pytest.raises(GitOperationError, match="no-such-branch"):
        trusted_config(checkout, "origin/no-such-branch")


_TWO_HOOKS = """\
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff
        entry: ruff check
        language: system
      - id: devops-ci-workflows-pre-push
        name: workflows
        entry: devops ci --check --only actionlint,zizmor
        language: system
        stages: [pre-push]
"""


def _missing(monkeypatch: pytest.MonkeyPatch, *hooks: str) -> None:
    """Make the image lack the programs of `hooks`."""
    monkeypatch.setattr(
        "devops_cli.roadmap.implement_hooks.hooks_without_programs", lambda: tuple(hooks)
    )


def test_the_trusted_configuration_leaves_out_a_hook_whose_program_the_image_lacks(
    checkout: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner image holds no `actionlint`, and no agent can install it, so the hook of the
    workflow checks would fail every item that changes a workflow (#3134). The checks of the pull
    request run it."""
    _missing(monkeypatch, "devops-ci-workflows-pre-push")
    _commit_config(checkout, _TWO_HOOKS)

    path = trusted_config(checkout, "HEAD")

    assert path is not None
    hooks = [
        hook["id"]
        for repo in yaml.safe_load(path.read_text("utf-8"))["repos"]
        for hook in repo["hooks"]
    ]
    assert hooks == ["ruff-check"]


def test_the_trusted_configuration_keeps_that_hook_where_the_program_is_on_the_path(
    checkout: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _missing(monkeypatch)
    _commit_config(checkout, _TWO_HOOKS)

    path = trusted_config(checkout, "HEAD")

    assert path is not None
    assert path.read_text(encoding="utf-8") == _TWO_HOOKS


def test_a_repository_whose_only_hook_is_left_out_leaves_the_list(
    checkout: Path, cache: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _missing(monkeypatch, "devops-ci-workflows-pre-push")
    only = _TWO_HOOKS.replace(
        "      - id: ruff-check\n        name: ruff\n        entry: ruff check\n        language: system\n",
        "",
    )
    _commit_config(checkout, only)

    path = trusted_config(checkout, "HEAD")

    assert path is not None
    assert yaml.safe_load(path.read_text(encoding="utf-8")) == {"repos": []}
