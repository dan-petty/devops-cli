"""The repair of the step `fix-checks` in a runner Job (#5971): the checkout of the head branch,
tier 1 (the fixers of a lint failure, their commit, and their checks again), the model fix, and
the push.

Git runs for real on a clone with an `origin`. GitHub's REST API and `gh` are faked at their edges,
the model is scripted, and the fixers of tier 1 and their checks are answered at the process edge:
a ruff fix rewrites the file it names.
"""

from __future__ import annotations

import subprocess

import pytest

from devops_cli.ai.client import factory
from devops_cli.roadmap.steps.fix_checks import FixChecksResult, run_fix_checks
from devops_cli.roadmap.steps.fix_checks_repair import job_repair, tier1_fix
from devops_cli.roadmap.stores.store import FixChecksRecordKey, ImplementRecordKey
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake
from tests.support.fakes.roadmap_store import InMemoryRoadmapStore
from tests.support.implement_step import command_text, git_for_real
from tests.support.model_script import ModelScript, say
from tests.support.roadmap_implement import (
    BRANCH,
    CHECK_LINK,
    FAIL,
    PULL,
    STEPS_DECLARATION,
    STEPS_FILE,
    a_fix,
    push_staged_branch,
    seed_staged,
)
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo

pytestmark = pytest.mark.usefixtures("keyring_store")

SAMPLE = "src/devops_cli/sample.py"
LINT_LOG = f"{SAMPLE}:1:8: F401 [*] `os` imported but unused\nFound 1 error.\n"
TYPE_LOG = f'{SAMPLE}:2: error: Incompatible types in assignment (got "str")  [assignment]\n'
STATIC = "Static Analysis"


@pytest.fixture
def branch(stage_repo: StageRepo, process_fake: ProcessFake) -> StageRepo:
    """The clone on the branch of item 1, with one commit that adds an unused import."""
    stage_repo.track({STEPS_FILE: STEPS_DECLARATION})
    stage_repo.git("switch", "-q", "-c", "fix/1-sample")
    (stage_repo.clone / SAMPLE).write_text("import os\nVALUE = 1\n", encoding="utf-8")
    stage_repo.git("add", "-A")
    stage_repo.git("commit", "-q", "-m", "fix(roadmap): add the value")
    process_fake.answer("git", ProcessAnswer(side_effect=git_for_real))
    process_fake.answer(lambda call: command_text(call).startswith("uv "), ProcessAnswer())
    return stage_repo


def _ruff_fix(call: ProcessCall) -> subprocess.CompletedProcess[str]:
    """What `ruff check --fix` does to the file: it drops the unused import."""
    assert call.cwd is not None
    (call.cwd / SAMPLE).write_text("VALUE = 1\n", encoding="utf-8")
    return subprocess.CompletedProcess(call.argv, 0, stdout="Found 1 error (1 fixed).")


def _uv_commands(fake: ProcessFake) -> list[str]:
    return [command_text(call) for call in fake.calls if call.argv[0] == "uv"]


def _fixes(fake: ProcessFake) -> None:
    fake.answer(
        lambda call: command_text(call).startswith("uv run ruff check --fix"),
        ProcessAnswer(side_effect=_ruff_fix),
    )


def test_tier1_commits_the_fixes_of_a_lint_failure_and_is_done_when_the_checks_pass(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    _fixes(process_fake)

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is True
    assert branch.git("log", "-1", "--format=%s") == (
        "style: apply the fixers of tier 1 for check Static Analysis (#1)"
    )
    assert branch.git("status", "--porcelain") == ""
    assert _uv_commands(process_fake) == [
        f"uv run ruff check --fix -- {SAMPLE}",
        f"uv run ruff format -- {SAMPLE}",
        "uv run devops docs generate",
        f"uv run ruff check -- {SAMPLE}",
        f"uv run ruff format --check -- {SAMPLE}",
        "uv run devops ci docs",
    ]


def test_a_tier1_commit_whose_check_still_fails_stays_for_the_model_fix(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    _fixes(process_fake)
    process_fake.answer(
        lambda call: command_text(call) == f"uv run ruff check -- {SAMPLE}",
        ProcessAnswer(returncode=1, stdout="E501 Line too long"),
    )

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is False
    assert "ruff check" in fixed.reason
    assert branch.git("log", "-1", "--format=%s").startswith("style: apply the fixers of tier 1")


def test_tier1_runs_no_fixer_for_a_failure_that_is_not_lint(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    head = branch.git("rev-parse", "HEAD")

    fixed = tier1_fix(branch.clone, 1, STATIC, TYPE_LOG)

    assert fixed.done is False
    assert (_uv_commands(process_fake), branch.git("rev-parse", "HEAD")) == ([], head)


def test_tier1_makes_no_commit_when_the_fixers_change_no_file(
    branch: StageRepo, process_fake: ProcessFake
) -> None:
    head = branch.git("rev-parse", "HEAD")

    fixed = tier1_fix(branch.clone, 1, STATIC, LINT_LOG)

    assert fixed.done is False
    assert "changed no file" in fixed.reason
    assert branch.git("rev-parse", "HEAD") == head


# ── The round end to end ─────────────────────────────────────────────────────────────────

# A type error in a file that the plan changes (`src/devops_cli/shout.py`): tier 1 has no fixer for
# it, so the model fix runs.
TYPE_ERROR = (
    "src/devops_cli/shout.py:5: error: Incompatible return value type "
    '(got "int", expected "str")  [return-value]\n'
)


@pytest.fixture
def failed_draft(
    stage_repo: StageRepo,
    app_slug: None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
) -> tuple[StageRepo, InMemoryRoadmapStore, str]:
    """Pull request 5 of item 1: a bot draft on the staged branch, whose `Static Analysis` check
    failed on its head with a log that names a file of the plan. The store holds the item."""
    push_staged_branch(stage_repo, files={"src/devops_cli/shout.py": "def shout(text):\n"})
    head = stage_repo.origin_git("rev-parse", BRANCH)
    api, programs = github_api_and_gh
    programs.answer("git", ProcessAnswer(side_effect=git_for_real))
    programs.answer(lambda call: command_text(call).startswith("uv "), ProcessAnswer())
    programs.answer(
        lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=TYPE_ERROR)
    )
    status = {
        "state": "open",
        "draft": True,
        "head": {"ref": BRANCH, "sha": head},
        "base": {"ref": "main"},
        "user": {"login": STAGE_NAME},
        "labels": [],
    }
    api.route("GET", f"/repos/{STAGE_REPO}/pulls/{PULL}", github_json(status))
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{head}/check-runs?per_page=100",
        github_json(
            {
                "total_count": 1,
                "check_runs": [{**FAIL, "name": "Static Analysis", "html_url": CHECK_LINK}],
            }
        ),
    )
    store = InMemoryRoadmapStore(repo=STAGE_REPO)
    number = seed_staged(store)
    held = store.item(number)
    assert held is not None
    store.set_marks(held, {ImplementRecordKey.PR: str(PULL)})
    return stage_repo, store, head


def test_a_failed_check_whose_log_names_a_file_of_the_plan_is_repaired_and_pushed(
    failed_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
) -> None:
    """The case of #5971: the round takes over the head branch, runs the model fix of the task
    `fix_checks`, and pushes one commit to the head branch with a lease on the judged head."""
    repo, store, head = failed_draft
    script = ModelScript(*a_fix())
    factory.set_llm_client_override(script.model())

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    new_head = repo.origin_git("rev-parse", BRANCH)
    assert (report.result, report.head, report.reason) == (
        FixChecksResult.REPAIRED,
        new_head,
        "Tier 2 model repaired check",
    )
    assert repo.origin_git("rev-parse", f"{new_head}~1") == head
    assert len(script.seen) == 2
    held = store.item(1)
    assert held is not None
    assert held.job_record.get(FixChecksRecordKey.RESULT) == "repaired"
    assert repo.git("worktree", "list").count("\n") == 0


def test_a_round_whose_model_fix_stops_pushes_nothing(
    failed_draft: tuple[StageRepo, InMemoryRoadmapStore, str],
) -> None:
    repo, store, head = failed_draft
    factory.set_llm_client_override(ModelScript(say("I see no fix.")).model())

    report = run_fix_checks(
        store,
        STAGE_REPO,
        PULL,
        confirm=True,
        repair=job_repair(store, STAGE_REPO, source=repo.clone),
    )

    assert report.result == FixChecksResult.FAILED
    assert report.reason.startswith("Model repair failed")
    assert repo.origin_git("rev-parse", BRANCH) == head
    assert repo.git("worktree", "list").count("\n") == 0
