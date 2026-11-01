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
from tests.support.model_script import say, tool_calls
from tests.support.roadmap_implement import (
    PULL,
    SHOUT,
    JobWorld,
    two_groups,
)

pytestmark = pytest.mark.usefixtures("keyring_store")

INSTALL = "uv run pre-commit install-hooks"
PRE_PUSH = "uv run pre-commit run --hook-stage pre-push --from-ref origin/main --to-ref HEAD"
STATIC = "uv run devops ci --check --only constructs,docs,openspec"
TESTS = "uv run devops ci test --no-fallback src/devops_cli/shout.py"
RULE = "ast-grep scan....Failed\nerror: pytest.raises without match\n --> tests/test_shout.py"


def _commands(world: JobWorld) -> list[str]:
    return [command_text(call) for call in world.programs.calls]


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
        lambda call: command_text(call) == command, ProcessAnswer(side_effect=answer)
    )


def _item_record(world: JobWorld) -> tuple[str | None, dict[str, str | None]]:
    held = world.store.item(1)
    assert held is not None
    return held.status, {str(key): value for key, value in held.job_record.items()}


# ── The hook environments ─────────────────────────────────────────────────────────────────


def test_the_job_installs_the_hook_environments_before_the_first_step(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    commands = _commands(job_world)
    assert commands.count(INSTALL) == 1
    first_stage = _position(job_world, "uv run pre-commit run --hook-stage pre-commit")
    assert _position(job_world, INSTALL) < first_stage
    install = next(c for c in job_world.programs.calls if command_text(c) == INSTALL)
    assert install.cwd is not None
    assert install.cwd != job_world.repo.clone


def test_a_failed_install_stops_the_item_before_any_model_request(job_world: JobWorld) -> None:
    job_world.programs.answer(
        lambda call: command_text(call) == INSTALL,
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
    order.append(_position(job_world, TESTS))
    assert rebase < order[0] < order[1] < order[2] < push
    scoped = [job_world.programs.calls[i] for i in order]
    assert {call.cwd for call in scoped} == {job_world.programs.calls[order[0]].cwd}
    assert scoped[0].cwd not in (None, job_world.repo.clone)


def test_the_tests_get_the_changed_python_files(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    assert TESTS in _commands(job_world)


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
    assert _commands(job_world).count(STATIC) == 2
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
    assert _commands(job_world).count(PRE_PUSH) == 4
    assert any("ruff-check....Failed" in c for c in job_world.issue_comments())
    assert job_world.pull.ready_calls == []


def test_the_rounds_for_the_scoped_checks_come_from_the_setting(
    job_world: JobWorld, config: Callable[..., Path]
) -> None:
    config(roadmap={"implement": {"repair_rounds": 1}})
    _fails_until(job_world, PRE_PUSH, "ruff-check....Failed", times=99)

    job_world.run(two_groups(*_fix(1), *_fix(2)))

    assert _commands(job_world).count(PRE_PUSH) == 2


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
