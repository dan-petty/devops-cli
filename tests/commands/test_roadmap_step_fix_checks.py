"""Tests for `devops roadmap step fix-checks` CLI command (#5023, #5971).

The end-to-end tests run git for real on a clone with an `origin`, and fake GitHub's REST API, `gh`
and the model fix at their edges. The model fix is the one fake of the repair: it edits a file of
the plan and commits, as a fix step does when its exit checks pass.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.implement.implement_step import StepOutcome, StepStatus
from devops_cli.roadmap.stores.store import FixChecksRecordKey, ImplementRecordKey
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer
from tests.support.implement_step import git_for_real
from tests.support.roadmap_implement import (
    BRANCH,
    CHECK_LINK,
    FAIL,
    PULL,
    push_staged_branch,
    seed_staged,
)
from tests.support.roadmap_stage import STAGE_NAME, STAGE_REPO, StageRepo

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.process import ProcessFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]

STATIC_FAIL = {**FAIL, "name": "Static Analysis"}
# A type error in a file that the plan changes (`src/devops_cli/shout.py`): tier 1 has no fixer for
# it, so the model fix runs.
TYPE_ERROR = (
    "src/devops_cli/shout.py:5: error: Incompatible return value type "
    '(got "int", expected "str")  [return-value]\n'
)
FIXED = '"""Shout."""\n\n\ndef shout(text: str) -> str:\n    return text.upper()\n'


def test_fix_checks_help(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-checks", "--help")
    assert result.exit_code == 0
    assert "--pull" in result.output
    assert "--confirm" in result.output
    assert "--dry-run" in result.output


def test_fix_checks_missing_pull(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project")
    assert result.exit_code == 1
    assert "Pass --pull" in result.output


def test_fix_checks_invalid_repo(cli: Cli) -> None:
    result = cli("roadmap", "step", "fix-checks", "--repo", "invalid", "--pull", "42")
    assert result.exit_code == 1
    assert "Cannot resolve the repository" in result.output


def test_fix_checks_dry_run(cli: Cli) -> None:
    result = cli(
        "roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42", "--dry-run"
    )
    assert result.exit_code == 0


def test_fix_checks_command_success(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    github_api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json(
            {
                "state": "closed",
                "draft": True,
                "head": {"ref": "feat/42-foo", "sha": "1" * 40},
                "base": {"ref": "main"},
                "user": {"login": "devops-cli[bot]"},
                "labels": [],
            }
        ),
    )
    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")
    assert result.exit_code == 0
    assert '"result": "skipped"' in result.output


def test_fix_checks_command_error(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    github_api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json({"message": "Server error"}, status=500),
    )
    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")
    assert result.exit_code == 1
    assert "Could not fix checks on PR #42" in result.output


def test_confirm_outside_a_runner_job_reads_no_pull_request(
    cli: Cli, github_api: GitHubApiFake, roadmap_store: InMemoryRoadmapStore
) -> None:
    result = cli(
        "roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42", "--confirm"
    )

    assert result.exit_code == 1
    assert "Could not fix checks on PR #42" in result.output
    assert github_api.sent == []


# ── End to end, in a runner ──────────────────────────────────────────────────────────────


@dataclass
class FixWorld:
    """Pull request 5 of item 1: a bot draft whose `Static Analysis` check failed on its head."""

    repo: StageRepo
    api: GitHubApiFake
    programs: ProcessFake
    store: InMemoryRoadmapStore
    head: str
    fixes: list[dict[str, Any]] = field(default_factory=list)
    models: list[str] = field(default_factory=list)

    def run(self, cli: Cli, *options: str) -> Any:
        return cli("roadmap", "step", "fix-checks", "--repo", STAGE_REPO, "--pull", "5", *options)

    def origin_subjects(self) -> list[str]:
        out = self.repo.origin_git("log", "--format=%s", f"main..{BRANCH}")
        return out.splitlines()

    def writes(self) -> list[str]:
        return [f"{r.method} {r.url.path}" for r in self.api.sent if r.method != "GET"]


@pytest.fixture
def fix_world(
    stage_repo: StageRepo,
    app_slug: None,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    config: Callable[..., Path],
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> FixWorld:
    """A runner Job with the token of `STAGE_REPO`, the staged branch of item 1 on `origin`, and
    the model fix faked: it fixes `src/devops_cli/shout.py` and commits."""
    from devops_cli.roadmap.steps import fix_checks_repair

    push_staged_branch(stage_repo, files={"src/devops_cli/shout.py": "def shout(text):\n"})
    head = stage_repo.origin_git("rev-parse", BRANCH)
    api, programs = github_api_and_gh
    config(
        roadmap={"implement": {"in_runner": True}},
        service={"github_app": {"token_repository": STAGE_REPO}},
    )
    monkeypatch.setattr(
        "devops_cli.roadmap.implement.implement_run.acts_as_github_app", lambda: True
    )
    monkeypatch.setattr(fix_checks_repair, "model_clone", lambda repo: stage_repo.clone)
    programs.answer("git", ProcessAnswer(side_effect=git_for_real))
    programs.answer(
        lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=TYPE_ERROR)
    )
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/pulls/{PULL}",
        github_json(
            {
                "state": "open",
                "draft": True,
                "head": {"ref": BRANCH, "sha": head},
                "base": {"ref": "main"},
                "user": {"login": STAGE_NAME},
                "labels": [],
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/{STAGE_REPO}/commits/{head}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [{**STATIC_FAIL, "html_url": CHECK_LINK}]}),
    )
    number = seed_staged(roadmap_store)
    item = roadmap_store.item(number)
    assert item is not None
    roadmap_store.set_marks(item, {ImplementRecordKey.PR: str(PULL)})
    world = FixWorld(stage_repo, api, programs, roadmap_store, head)

    def model(task: str, **_: Any) -> str:
        world.models.append(task)
        return f"model of {task}"

    def fix_step(store: Any, **kwargs: Any) -> StepOutcome:
        world.fixes.append(kwargs)
        source: Path = kwargs["source"]
        (source / "src" / "devops_cli" / "shout.py").write_text(FIXED, encoding="utf-8")
        for args in (("add", "-A"), ("commit", "-q", "-m", "fix(roadmap): make the check pass")):
            subprocess.run(["git", "-C", str(source), *args], check=True)
        return StepOutcome(item=kwargs["item"], group=0, title="", status=StepStatus.DONE)

    monkeypatch.setattr(fix_checks_repair, "get_task_model", model)
    monkeypatch.setattr(fix_checks_repair, "run_fix_step", fix_step)
    return world


def test_the_command_repairs_a_failed_check_whose_log_names_a_file_of_the_plan(
    cli: Cli, fix_world: FixWorld
) -> None:
    """The case of #5971: the command takes over the head branch, runs the model fix of the task
    `fix_checks` under its token cap, and pushes one commit with a lease on the judged head."""
    result = fix_world.run(cli, "--confirm")

    assert result.exit_code == 0, result.output
    new_head = fix_world.repo.origin_git("rev-parse", BRANCH)
    assert '"result": "repaired"' in result.output
    assert f'"head": "{new_head}"' in result.output
    assert fix_world.origin_subjects() == [
        "fix(roadmap): make the check pass",
        "fix(roadmap): plan",
    ]
    assert fix_world.models == ["fix_checks"]
    [fix] = fix_world.fixes
    assert (fix["item"], fix["fix"].check, fix["fix"].log, fix["model"], fix["ladder"]) == (
        1,
        "Static Analysis",
        TYPE_ERROR,
        "model of fix_checks",
        (),
    )
    assert (fix["token_cap"].setting, fix["token_cap"].value) == (
        "roadmap.fix_checks.token_budget",
        16_000_000,
    )
    item = fix_world.store.item(1)
    assert item is not None
    assert item.job_record.get(FixChecksRecordKey.RESULT) == "repaired"
    assert fix_world.repo.git("worktree", "list").count("\n") == 0


def test_the_command_without_confirm_writes_nothing(cli: Cli, fix_world: FixWorld) -> None:
    result = fix_world.run(cli)

    assert result.exit_code == 0, result.output
    assert '"result": "planned"' in result.output
    assert fix_world.repo.origin_git("rev-parse", BRANCH) == fix_world.head
    assert (fix_world.fixes, fix_world.writes()) == ([], [])
    item = fix_world.store.item(1)
    assert item is not None
    assert {item.job_record.get(key) for key in FixChecksRecordKey} == {None}
