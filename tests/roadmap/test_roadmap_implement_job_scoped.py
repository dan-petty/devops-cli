"""The hooks and the scoped checks of the implement job (#3043): the install of the hook
environments, the checks before the push, the fix steps they cause, and the lines they add to the
comment on the pull request.

Git runs for real on a clone with an `origin`. The model is scripted. The checks of the project
are answered at the process edge.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelResponse

from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    PULL,
    SHOUT,
    JobWorld,
    group_one_calls,
    group_two_calls,
    two_groups,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

INSTALL = "uv run pre-commit install-hooks"
PRE_COMMIT = "uv run pre-commit run --hook-stage pre-commit"
PRE_PUSH = "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD"
STATIC = "uv run devops ci --check --only constructs,docs,openspec"
TESTS = "uv run devops ci test tests/test_shout.py"
RULE = "ast-grep scan....Failed\nerror: pytest.raises without match\n --> tests/test_shout.py"


CONFIG = ".pre-commit-config.yaml"
HOOKS = "repos:\n  - repo: local\n    hooks: []\n"
TEST_MODULE = "tests/test_shout.py"


@pytest.fixture
def job_world(job_world: JobWorld) -> JobWorld:
    """The job world, with the configuration of the hooks on `main` of `origin`. The staged branch
    is older than it, and the job rebases onto it."""
    repo = job_world.repo
    (repo.clone / CONFIG).write_text(HOOKS, encoding="utf-8")
    (repo.clone / TEST_MODULE).parent.mkdir(exist_ok=True)
    (repo.clone / TEST_MODULE).write_text("from devops_cli.shout import shout\n", encoding="utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Add the hooks and a test")
    repo.git("push", "-q", "origin", "main")
    return job_world


def _commands(world: JobWorld) -> list[str]:
    return [command_text(call) for call in world.programs.calls]


def _count(world: JobWorld, prefix: str) -> int:
    """How many commands start with `prefix`."""
    return sum(text.startswith(prefix) for text in _commands(world))


def _position(world: JobWorld, wanted: str) -> int:
    """The index of the first call whose command line starts with `wanted`."""
    return next(i for i, text in enumerate(_commands(world)) if text.startswith(wanted))


def _git_push(world: JobWorld) -> list[ProcessCall]:
    return [call for call in world.programs.calls if call.argv[0] == "git" and "push" in call.argv]


def _fix(round_number: int) -> tuple[ModelResponse, ModelResponse]:
    """A fix that changes the code in a way that no earlier fix did."""
    changed = SHOUT + "".join(f"\n\nVALUE_{k} = {k}\n" for k in range(round_number))
    path = "src/devops_cli/shout.py"
    return (
        tool_calls(("write_file", {"path": path, "content": changed})),
        say(f"Fixed round {round_number}."),
    )


def _fails_until(world: JobWorld, command: str, report: str, *, times: int) -> None:
    """`command` exits 1 with `report` for its first `times` runs, then exits 0."""
    runs: list[int] = []

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        runs.append(1)
        failed = len(runs) <= times
        return subprocess.CompletedProcess(
            call.argv, 1 if failed else 0, stdout=f"{report}\n" if failed else "", stderr=""
        )

    world.programs.answer(
        lambda call: command_text(call).startswith(command), ProcessAnswer(side_effect=answer)
    )


def _item_record(world: JobWorld) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(1)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


# ── The hook environments ─────────────────────────────────────────────────────────────────


def test_the_job_installs_the_hook_environments_before_the_first_step(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    assert _count(job_world, INSTALL) == 1
    first_stage = _position(job_world, "uv run pre-commit run --hook-stage pre-commit")
    assert _position(job_world, INSTALL) < first_stage
    install = next(c for c in job_world.programs.calls if command_text(c).startswith(INSTALL))
    assert install.cwd is not None
    assert install.cwd != job_world.repo.clone


def test_a_failed_install_stops_the_item_before_any_model_request(job_world: JobWorld) -> None:
    job_world.programs.answer(
        lambda call: command_text(call).startswith(INSTALL),
        ProcessAnswer(returncode=1, stderr="could not resolve host example.com"),
    )
    script = two_groups()

    applied = job_world.run(script)

    status, record = _item_record(job_world)
    assert (applied.stopped, script.seen, status, record["implement.stopped"]) == (
        (1,),
        [],
        "Blocked",
        "hooks",
    )
    assert any("could not resolve host example.com" in c for c in job_world.issue_comments())
    assert _git_push(job_world) == []


# ── The scoped checks ─────────────────────────────────────────────────────────────────────


def test_the_scoped_checks_run_in_the_worktree_after_the_last_commit_and_before_the_push(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    commands = _commands(job_world)
    rebase = max(i for i, text in enumerate(commands) if " rebase " in f" {text} ")
    push = next(i for i, text in enumerate(commands) if " push " in f" {text} ")
    order = [_position(job_world, PRE_PUSH), _position(job_world, STATIC)]
    order.append(max(i for i, text in enumerate(commands) if text.startswith(TESTS)))
    assert rebase < order[0] < order[1] < order[2] < push
    scoped = [job_world.programs.calls[i] for i in order]
    assert {call.cwd for call in scoped} == {job_world.programs.calls[order[0]].cwd}
    assert scoped[0].cwd not in (None, job_world.repo.clone)


def test_the_tests_get_the_test_modules_that_cover_the_changed_sources(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    # One run is the verification command of group 1, the other the scoped check.
    assert _count(job_world, TESTS) == 2
    assert not any("src/" in text for text in _commands(job_world) if "ci test" in text)


def test_an_ast_grep_violation_is_repaired_before_the_first_push(job_world: JobWorld) -> None:
    _fails_until(job_world, STATIC, RULE, times=1)
    script = two_groups(*_fix(1))

    applied = job_world.run(script)

    assert (applied.ready, applied.stopped) == ((1,), ())
    assert job_world.origin_log()[-2:] == [
        "docs(openspec): archive the change (#1)",
        "Make check static pass (#1)",
    ]
    assert len(_git_push(job_world)) == 1
    assert _count(job_world, STATIC) == 2
    fix_prompt = next(str(getattr(p, "content", "")) for p in script.seen[4][-1].parts)
    assert "ast-grep scan....Failed" in fix_prompt


def test_the_documentation_is_generated_again_after_a_fix(job_world: JobWorld) -> None:
    _fails_until(job_world, STATIC, RULE, times=1)

    job_world.run(two_groups(*_fix(1)))

    commands = _commands(job_world)
    generate = [i for i, text in enumerate(commands) if text.startswith("uv run devops docs gen")]
    assert len(generate) == 2
    assert generate[1] > _position(job_world, STATIC)


def test_a_check_that_no_fix_repairs_stops_the_item_and_pushes_nothing(
    job_world: JobWorld,
) -> None:
    _fails_until(job_world, PRE_PUSH, "ruff-check....Failed", times=99)
    script = two_groups(*_fix(1), *_fix(2), *_fix(3))

    applied = job_world.run(script)

    status, record = _item_record(job_world)
    assert (applied.stopped, status, record["implement.stopped"]) == (
        (1,),
        "Blocked",
        "scoped checks",
    )
    assert job_world.origin_log() == ["fix(roadmap): plan"]
    assert _git_push(job_world) == []
    assert _count(job_world, PRE_PUSH) == 4
    assert any("ruff-check....Failed" in c for c in job_world.issue_comments())
    assert job_world.pull.ready_calls == []


def test_the_rounds_for_the_scoped_checks_come_from_the_setting(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"repair_rounds": 1}})
    _fails_until(job_world, PRE_PUSH, "ruff-check....Failed", times=99)

    job_world.run(two_groups(*_fix(1), *_fix(2)))

    assert _count(job_world, PRE_PUSH) == 2


def test_a_fix_step_that_stops_in_the_scoped_checks_pushes_nothing(job_world: JobWorld) -> None:
    _fails_until(job_world, STATIC, RULE, times=1)
    script = two_groups(say("I changed nothing."))

    applied = job_world.run(script)

    status, record = _item_record(job_world)
    assert (applied.stopped, status, record["implement.stopped"]) == (
        (1,),
        "Blocked",
        "fix",
    )
    assert _git_push(job_world) == []


# ── The configuration of the hooks ────────────────────────────────────────────────────────


def _hook_runs(world: JobWorld) -> list[str]:
    return [text for text in _commands(world) if text.startswith("uv run pre-commit")]


def test_an_edit_of_the_hook_configuration_by_the_agent_skips_no_hook(job_world: JobWorld) -> None:
    """The agent writes `repos: []` into the configuration. Every hook run still reads the copy
    of the default branch, which `--config` names."""
    skip = ("write_file", {"path": CONFIG, "content": "repos: []\n"})
    script = ModelScript(
        tool_calls(*group_one_calls(), skip),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)

    runs = _hook_runs(job_world)
    install = next(text for text in runs if text.startswith(INSTALL))
    trusted = install.rsplit("--config ", 1)[1]
    assert applied.ready == (1,)
    assert len(runs) >= 4
    assert all(text.endswith(f"--config {trusted}") for text in runs)
    assert Path(trusted).read_text(encoding="utf-8") == HOOKS
    assert Path(trusted).parent != job_world.repo.clone


# ── The stops of the scoped checks ────────────────────────────────────────────────────────


def _times_out_from(world: JobWorld, prefix: str, first: int, last: int = 99) -> None:
    """The commands that start with `prefix` run out of time, from the `first` one to the `last`."""
    runs: list[int] = []

    def hang(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        runs.append(1)
        if first <= len(runs) <= last:
            raise subprocess.TimeoutExpired(call.argv, 1)
        return subprocess.CompletedProcess(call.argv, 0, stdout="", stderr="")

    world.programs.answer(
        lambda call: command_text(call).startswith(prefix), ProcessAnswer(side_effect=hang)
    )


def test_a_hook_stage_that_runs_out_of_time_in_a_fix_step_pushes_nothing(
    job_world: JobWorld,
) -> None:
    """The stage of the fix step is the third run of the stage: one for each group before it."""
    _fails_until(job_world, STATIC, RULE, times=1)
    _times_out_from(job_world, PRE_COMMIT, 3)

    applied = job_world.run(two_groups(*_fix(1)))

    status, record = _item_record(job_world)
    assert (applied.stopped, status, record["implement.stopped"]) == ((1,), "Blocked", "fix")
    assert _git_push(job_world) == []
    assert job_world.origin_log() == ["fix(roadmap): plan"]
    assert any("ran out of time" in c for c in job_world.issue_comments())


def test_an_error_in_the_scoped_checks_pushes_nothing(job_world: JobWorld) -> None:
    """The error of git comes after the archive, in the phase of the scoped checks."""

    def broken(call: ProcessCall) -> bool:
        archived = any(
            text.startswith("uv run devops openspec archive") for text in _commands(job_world)
        )
        return archived and "ls-tree" in call.argv

    job_world.programs.answer(
        broken, ProcessAnswer(returncode=128, stderr="fatal: Not a valid object name")
    )

    applied = job_world.run(two_groups())

    status, record = _item_record(job_world)
    assert (applied.stopped, status, record["implement.stopped"]) == (
        (1,),
        "Blocked",
        "scoped checks",
    )
    assert _git_push(job_world) == []
    assert job_world.origin_log() == ["fix(roadmap): plan"]


def test_a_tests_check_that_runs_out_of_time_is_a_failed_check(job_world: JobWorld) -> None:
    _times_out_from(job_world, TESTS, 2, 2)

    applied = job_world.run(two_groups(*_fix(1)))

    assert (applied.ready, applied.stopped) == ((1,), ())
    assert _git_push(job_world) != []


# ── The comment on the pull request ───────────────────────────────────────────────────────


def test_the_comment_shows_the_repair_rounds_of_each_step_and_each_scoped_check(
    job_world: JobWorld,
) -> None:
    job_world.run(two_groups())

    (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
    lines = comment["body"].splitlines()
    assert any(
        line.startswith("- group 1 (The first group): done") and "0 repair rounds" in line
        for line in lines
    )
    for name in ("pre-push", "static", "tests"):
        assert any(
            line.startswith(f"- scoped check {name}: passed, ") and line.endswith(" s")
            for line in lines
        ), name


def test_the_comment_lists_the_failed_run_of_a_check_and_the_run_after_its_fix(
    job_world: JobWorld,
) -> None:
    _fails_until(job_world, STATIC, RULE, times=1)

    job_world.run(two_groups(*_fix(1)))

    (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
    lines = [line for line in comment["body"].splitlines() if "scoped check static" in line]
    assert [line.split(": ")[1].split(",")[0] for line in lines] == ["failed", "passed"]


def test_a_repository_with_no_hook_configuration_gets_no_install_and_no_pre_push_check(
    job_world: JobWorld,
) -> None:
    repo = job_world.repo
    repo.git("rm", "-q", CONFIG)
    repo.git("commit", "-q", "-m", "Remove the hooks")
    repo.git("push", "-q", "origin", "main")

    applied = job_world.run(two_groups())

    commands = _commands(job_world)
    assert applied.ready == (1,)
    assert [text for text in commands if text.startswith("uv run pre-commit")] == []
    assert any(text.startswith(STATIC) for text in commands)


def test_a_change_that_no_test_covers_runs_no_test_and_the_comment_says_so(
    job_world: JobWorld,
) -> None:
    repo = job_world.repo
    repo.git("rm", "-q", TEST_MODULE)
    repo.git("commit", "-q", "-m", "Remove the test")
    repo.git("push", "-q", "origin", "main")

    applied = job_world.run(two_groups())

    (comment,) = job_world.sent("POST", f"issues/{PULL}/comments")
    assert applied.ready == (1,)
    assert _commands(job_world).count("uv run devops ci test tests/test_shout.py") == 1
    assert (
        "- scoped check tests: not run, because no test covers the changed files"
        in (comment["body"])
    )
