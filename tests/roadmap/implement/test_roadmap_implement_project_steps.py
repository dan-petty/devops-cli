"""The project steps of the implement job (#3484): the job regenerates the documents and archives
the change only where the default branch of the target declares the step.

Git runs for real on a clone with an `origin`. The model is scripted. The commands of the project
are answered at the process edge.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime

import pytest
from pydantic_ai.messages import ModelResponse

from devops_cli.exceptions import ConfigurationError
from devops_cli.roadmap.failure import ACTION_BY_CLASS, FailureAction, FailureClass
from devops_cli.roadmap.planned import PlannedChanges
from devops_cli.roadmap.pull_form import body_problems
from devops_cli.roadmap.stop_clear import ClearLimits, clear_stops
from devops_cli.roadmap.stores.store import ImplementRecordKey, Item
from tests.support.fakes.process import ProcessAnswer, ProcessCall
from tests.support.implement_step import command_text
from tests.support.model_script import ModelScript, say, tool_calls
from tests.support.roadmap_implement import (
    CHANGE,
    PULL,
    SHOUT,
    STEPS_DECLARATION,
    STEPS_FILE,
    JobWorld,
    group_one_calls,
    group_two_calls,
    two_groups,
    undeclare_steps,
)
from tests.support.roadmap_stage import StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

DOCS = "uv run devops docs generate"
ARCHIVE = ("uv run devops openspec archive", "openspec archive")
HOOK_PRE_PUSH = "uv run --frozen pre-commit run --hook-stage pre-push"
STATIC = "uv run devops ci --check --only constructs,docs,openspec"
RULE = "ast-grep scan....Failed\nerror: pytest.raises without match\n --> tests/test_shout.py"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64
NO_PLANS = PlannedChanges("main", {}, {})
NOW = datetime(2026, 11, 4, 12, 0, tzinfo=UTC)
LIMITS = ClearLimits(per_class=1, per_item=3, continuations=2)
HOOKS = "repos:\n  - repo: local\n    hooks: []\n"


def _count(world: JobWorld, prefix: str | tuple[str, ...]) -> int:
    prefixes = (prefix,) if isinstance(prefix, str) else prefix
    return sum(
        any(command_text(call).startswith(p) for p in prefixes) for call in world.programs.calls
    )


def _remove_openspec(repo: StageRepo) -> None:
    repo.git("rm", "-q", "openspec/config.yaml")
    repo.git("commit", "-q", "-m", "Remove openspec")
    repo.git("push", "-q", "origin", "main")


def _fails_once(world: JobWorld, command: str, report: str) -> None:
    """`command` exits 1 with `report` for its first run, then exits 0."""
    runs: list[int] = []

    def answer(call: ProcessCall) -> subprocess.CompletedProcess[str]:
        runs.append(1)
        failed = len(runs) == 1
        return subprocess.CompletedProcess(
            call.argv, 1 if failed else 0, stdout=f"{report}\n" if failed else "", stderr=""
        )

    world.programs.answer(
        lambda call: command_text(call).startswith(command), ProcessAnswer(side_effect=answer)
    )


def _one_fix() -> tuple[ModelResponse, ModelResponse]:
    path = "src/devops_cli/shout.py"
    return (
        tool_calls(("write_file", {"path": path, "content": SHOUT + "\n\nVALUE = 1\n"})),
        say("Fixed."),
    )


def test_a_target_with_no_declaration_skips_the_docs_step_and_ends_with_a_draft(
    job_world: JobWorld,
) -> None:
    undeclare_steps(job_world.repo)

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped, _count(job_world, DOCS)) == ((1,), (), 0)
    assert "docs: regenerate the documentation (#1)" not in job_world.origin_log()
    assert job_world.pull.ready_calls == []


def test_a_target_with_no_declaration_skips_the_docs_step_after_a_fix_too(
    job_world: JobWorld,
) -> None:
    undeclare_steps(job_world.repo)
    job_world.repo.track({".pre-commit-config.yaml": HOOKS})
    _fails_once(job_world, HOOK_PRE_PUSH, "error: pre-push hook failed")

    applied = job_world.run(two_groups(*_one_fix()))

    assert (applied.drafted, applied.stopped) == ((1,), ())
    assert _count(job_world, HOOK_PRE_PUSH) == 2
    assert _count(job_world, DOCS) == 0


def test_a_target_without_openspec_skips_the_archive_step(job_world: JobWorld) -> None:
    _remove_openspec(job_world.repo)

    applied = job_world.run(two_groups())

    assert (applied.drafted, applied.stopped, _count(job_world, ARCHIVE)) == ((1,), (), 0)
    assert "docs(openspec): archive the change (#1)" not in job_world.origin_log()


def test_a_target_that_declares_the_steps_runs_them(job_world: JobWorld) -> None:
    applied = job_world.run(two_groups())

    assert (applied.drafted, _count(job_world, DOCS), _count(job_world, ARCHIVE)) == ((1,), 1, 1)
    assert job_world.origin_log()[-2:] == [
        "docs: regenerate the documentation (#1)",
        "docs(openspec): archive the change (#1)",
    ]


def test_a_neutral_target_runs_archive_and_no_docs_step(job_world: JobWorld) -> None:
    job_world.repo.track({STEPS_FILE: '[project]\ntoolchain = "neutral"\n'})

    applied = job_world.run(two_groups())

    assert (applied.drafted, _count(job_world, DOCS), _count(job_world, ARCHIVE)) == ((1,), 0, 1)


def test_an_agent_that_adds_the_declaration_in_the_checkout_adds_no_step(
    job_world: JobWorld,
) -> None:
    undeclare_steps(job_world.repo)
    script = ModelScript(
        tool_calls(
            *group_one_calls(),
            (
                "write_file",
                {"path": STEPS_FILE, "content": STEPS_DECLARATION},
            ),
        ),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)

    assert (applied.drafted, _count(job_world, DOCS), _count(job_world, ARCHIVE)) == ((1,), 0, 1)


def test_an_agent_that_removes_the_declaration_in_the_checkout_removes_no_step(
    job_world: JobWorld,
) -> None:
    script = ModelScript(
        tool_calls(
            *group_one_calls(),
            (
                "write_file",
                {
                    "path": STEPS_FILE,
                    "content": '[project]\ntoolchain = "neutral"\n',
                },
            ),
        ),
        say("Group 1 is done."),
        tool_calls(*group_two_calls()),
        say("Group 2 is done."),
    )

    applied = job_world.run(script)

    assert (applied.drafted, _count(job_world, DOCS), _count(job_world, ARCHIVE)) == ((1,), 1, 1)


def test_the_comment_of_the_job_names_each_step_that_it_skipped(job_world: JobWorld) -> None:
    undeclare_steps(job_world.repo)
    _remove_openspec(job_world.repo)

    job_world.run(two_groups())

    comment = next(
        body
        for body in (request["body"] for request in job_world.sent("POST", "issues/5/comments"))
        if "step docs" in body
    )
    assert "- step docs: skipped" in comment
    assert "- step archive: skipped" in comment
    assert STEPS_FILE in comment


def test_a_project_without_the_archive_step_gets_a_body_that_names_the_active_folder(
    job_world: JobWorld,
) -> None:
    _remove_openspec(job_world.repo)

    job_world.run(two_groups())

    (patched,) = job_world.sent("PATCH", f"pulls/{PULL}")
    assert body_problems(patched["body"]) == []
    assert patched["body"].endswith(f"Change: `openspec/changes/{CHANGE}/`")


def test_the_comment_of_the_job_names_no_step_that_it_ran(job_world: JobWorld) -> None:
    job_world.run(two_groups())

    bodies = [request["body"] for request in job_world.sent("POST", "issues/5/comments")]
    assert not any("skipped" in body for body in bodies)


def test_a_declaration_that_is_not_valid_stops_the_item_and_runs_no_step(
    job_world: JobWorld,
) -> None:
    job_world.repo.track({STEPS_FILE: '[project]\ntoolchain = "invalid"\n'})

    applied = job_world.run(two_groups())

    assert (applied.stopped, _count(job_world, DOCS), _count(job_world, ARCHIVE)) == ((1,), 0, 0)
    assert STEPS_FILE in job_world.issue_comments()[0]


def test_the_project_profile_is_read_from_the_commit_and_not_from_the_files(
    stage_repo: StageRepo,
) -> None:
    from devops_cli.roadmap.project_profile import resolve_profile
    from devops_cli.roadmap.toolchains import NEUTRAL_PRESET

    stage_repo.track({STEPS_FILE: '[project]\ntoolchain = "neutral"\n'})
    (stage_repo.clone / STEPS_FILE).write_text(STEPS_DECLARATION, encoding="utf-8")

    found = resolve_profile(stage_repo.clone, "origin/main")

    assert found == NEUTRAL_PRESET


def test_a_commit_with_no_declaration_resolves_to_neutral_preset(stage_repo: StageRepo) -> None:
    from devops_cli.roadmap.project_profile import resolve_profile
    from devops_cli.roadmap.toolchains import NEUTRAL_PRESET

    assert resolve_profile(stage_repo.clone, "origin/main") == NEUTRAL_PRESET


def test_a_declaration_with_a_toolchain_that_does_not_exist_is_refused(
    stage_repo: StageRepo,
) -> None:
    from devops_cli.roadmap.project_profile import resolve_profile

    stage_repo.track({STEPS_FILE: '[project]\ntoolchain = "cargo"\n'})

    with pytest.raises(ConfigurationError, match=r"roadmap\.toml"):
        resolve_profile(stage_repo.clone, "origin/main")


def _stopped_on_the_docs_step(world: JobWorld, error: str) -> Item:
    """The item after a run whose docs step exits 1 with `error`."""
    world.programs.answer(
        lambda call: command_text(call).startswith(DOCS),
        ProcessAnswer(returncode=1, stderr=error),
    )
    applied = world.run(two_groups())
    item = world.store.item(1)
    assert (applied.stopped, item is not None) == ((1,), True)
    assert item is not None
    return item


def test_a_stop_on_a_read_only_path_has_the_class_read_only_path_and_the_action_wait(
    job_world: JobWorld,
) -> None:
    item = _stopped_on_the_docs_step(
        job_world, "OSError: [Errno 30] Read-only file system: '/app/docs'\n"
    )

    failure = item.job_record[ImplementRecordKey.FAILURE]
    assert failure == "read_only_path"
    assert ACTION_BY_CLASS[FailureClass(failure)] is FailureAction.WAIT


def test_a_new_runner_image_does_not_clear_a_stop_on_a_read_only_path(
    job_world: JobWorld,
) -> None:
    item = _stopped_on_the_docs_step(
        job_world, "OSError: [Errno 30] Read-only file system: '/app/docs'\n"
    )
    job_world.store.set_marks(item, {ImplementRecordKey.JOB_DIGEST: DIGEST_A})
    stopped = job_world.store.item(1)
    assert stopped is not None

    cleared = clear_stops(
        job_world.store, planned=NO_PLANS, digest=lambda: DIGEST_B, limits=LIMITS, now=NOW
    )
    # The same stop with a class that a retry can fix is cleared, so the rule did run.
    job_world.store.set_marks(stopped, {ImplementRecordKey.FAILURE: FailureClass.PROVIDER.value})
    control = clear_stops(
        job_world.store, planned=NO_PLANS, digest=lambda: DIGEST_B, limits=LIMITS, now=NOW
    )

    assert (cleared.cleared, control.cleared) == ((), (1,))
