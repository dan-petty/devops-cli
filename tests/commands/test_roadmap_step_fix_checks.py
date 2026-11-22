"""Tests for `devops roadmap step fix-checks` CLI command (#5023, #5971).

GitHub's REST API and `gh` are faked at their edges. The repair in a runner Job is tested end to
end in `tests/roadmap/steps/test_roadmap_step_fix_checks_repair.py`.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from devops_cli.roadmap.steps.fix_checks import FixChecksReport
from devops_cli.roadmap.stores.store import FixChecksResult
from tests.support.fakes.github import github_json
from tests.support.fakes.process import ProcessAnswer
from tests.support.job_templates import phase_cronjob_template

if TYPE_CHECKING:
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.process import ProcessFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

pytestmark = pytest.mark.usefixtures("keyring_store")

Cli = Callable[..., Any]

HEAD = "1" * 40
STATIC_FAIL = {
    "name": "Static Analysis",
    "status": "completed",
    "conclusion": "failure",
    "html_url": "https://github.com/example/project/actions/runs/101/job/202",
}
TYPE_ERROR = (
    "src/devops_cli/shout.py:5: error: Incompatible return value type "
    '(got "int", expected "str")  [return-value]\n'
)


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
    cli: Cli,
    github_api: GitHubApiFake,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The process is unreadable first, and the check of the runner then refuses the run before
    any read of GitHub. The spies replace the kernel calls, which would change the test run."""
    from devops_cli.core import process_hardening

    monkeypatch.setattr(process_hardening, "deny_environment_reads", lambda: None)

    result = cli(
        "roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42", "--confirm"
    )

    assert result.exit_code == 1
    assert "Could not fix checks on PR #42" in result.output
    assert github_api.sent == []


def test_the_command_without_confirm_plans_a_repair_and_writes_nothing(
    cli: Cli,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """The case of #5971 in the mode `plan`: a bot draft whose `Static Analysis` check failed with a
    log that names a file of the plan."""
    api, gh = github_api_and_gh
    api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json(
            {
                "state": "open",
                "draft": True,
                "head": {"ref": "feat/42-foo", "sha": HEAD},
                "base": {"ref": "main"},
                "user": {"login": "devops-cli[bot]"},
                "labels": [],
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/example/project/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [STATIC_FAIL]}),
    )
    gh.answer(lambda call: call.argv[1:3] == ("run", "view"), ProcessAnswer(stdout=TYPE_ERROR))

    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout) == {
        "job": "fix_checks",
        "repo": "example/project",
        "pull": 42,
        "result": "planned",
        "head": HEAD,
        "errors": 1,
        "reason": "Plan: repair check `Static Analysis` with tier 1, then the model in the plan "
        "scope",
    }
    assert [request.method for request in api.sent] == ["GET", "GET"]


def test_the_command_passes_the_check_of_the_unit_to_the_step(
    cli: Cli,
    github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    roadmap_store: InMemoryRoadmapStore,
) -> None:
    """The fix-checks Job names the check of its unit with `--check` (#5027): a check that does not
    fail on the head gives `skipped`."""
    api, _ = github_api_and_gh
    api.route(
        "GET",
        "/repos/example/project/pulls/42",
        github_json(
            {
                "state": "open",
                "draft": True,
                "head": {"ref": "feat/42-foo", "sha": HEAD},
                "base": {"ref": "main"},
                "user": {"login": "devops-cli[bot]"},
                "labels": [],
            }
        ),
    )
    api.route(
        "GET",
        f"/repos/example/project/commits/{HEAD}/check-runs?per_page=100",
        github_json({"total_count": 1, "check_runs": [STATIC_FAIL]}),
    )

    result = cli(
        "roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42",
        "--head", HEAD, "--check", "Type Check",
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["result"] == "skipped"


def test_a_sigterm_during_the_step_exits_75_with_no_result_line(
    cli: Cli, roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An eviction, a drain or the deadline of the Job ends the step: the command exits 75
    (`EX_TEMPFAIL`) with no result line, so the Service starts the next attempt (#5027)."""
    from devops_cli.roadmap.attempt_kill import AttemptKilled
    from devops_cli.roadmap.steps import fix_checks

    def killed(*_: Any, **__: Any) -> Any:
        raise AttemptKilled

    monkeypatch.setattr(fix_checks, "run_fix_checks", killed)

    result = cli("roadmap", "step", "fix-checks", "--repo", "example/project", "--pull", "42")

    assert (result.exit_code, '"job"' in result.stdout) == (75, False)


@pytest.mark.parametrize(
    ("phase", "runs", "runner"),
    [
        ("all", "run_fix_checks", "runner"),
        ("prepare", "prepare_phase", "runner"),
        ("agent", "agent_phase", "agent runner"),
        ("publish", "publish_phase", "runner"),
    ],
)
def test_each_confirmed_phase_makes_its_process_unreadable_before_anything_else(
    cli: Cli,
    roadmap_store: InMemoryRoadmapStore,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    phase: str,
    runs: str,
    runner: str,
) -> None:
    """The repair runs an agent step whose shell has the user of the Job, so each phase clears its
    dumpable flag first, before it reads the settings of the runner or a file of the run (#2667,
    #3702). The agent phase checks that it holds no App key, and the other phases that they act as
    the App (#6601). The spy replaces the kernel call, which would change the test run."""
    from devops_cli.core import process_hardening
    from devops_cli.roadmap.attempt_kill import AttemptKilled
    from devops_cli.roadmap.implement import implement_run
    from devops_cli.roadmap.steps import fix_checks, fix_checks_phases

    seen: list[str] = []
    monkeypatch.setattr(implement_run, "require_runner", lambda _repo: seen.append("runner"))
    monkeypatch.setattr(implement_run, "require_agent_runner", lambda: seen.append("agent runner"))
    monkeypatch.setattr(
        process_hardening, "deny_environment_reads", lambda: seen.append("unreadable")
    )

    def step(*_: Any, **__: Any) -> Any:
        seen.append("step")
        raise AttemptKilled

    module = fix_checks if phase == "all" else fix_checks_phases
    monkeypatch.setattr(module, runs, step)
    args = ["--phase", phase, "--work", str(tmp_path)] if phase != "all" else []

    cli(
        "roadmap",
        "step",
        "fix-checks",
        "--repo",
        "example/project",
        "--pull",
        "42",
        "--confirm",
        *args,
    )

    assert seen == ["unreadable", runner, "step"]


@pytest.mark.parametrize("phase", ["agent", "publish"])
def test_a_phase_of_a_repair_needs_a_run_folder(cli: Cli, phase: str) -> None:
    result = cli(
        "roadmap",
        "step",
        "fix-checks",
        "--repo",
        "example/project",
        "--pull",
        "42",
        "--phase",
        phase,
        "--confirm",
    )

    assert (result.exit_code, "--work" in result.output) == (1, True)


def test_each_container_of_a_plan_job_on_the_phases_runs_and_only_prepare_plans(
    cli: Cli, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A Job in mode `plan` has no `--confirm`. On the phases (#3700), `prepare` runs the plan
    round and prints its result line, and `agent` and `publish` exit 0 with nothing to do
    (#6690)."""
    from devops_cli.k8s.cluster_job import RUNNER_TEMPLATE, build_job
    from devops_cli.roadmap.fix_checks_row import FixDue, fix_args
    from devops_cli.roadmap.steps import fix_checks

    due = FixDue(pull=42, head="a" * 40, check="lint", item=5)
    job = build_job(
        phase_cronjob_template(RUNNER_TEMPLATE),
        list(fix_args("example/project", due, confirm=False)),
        "job-x",
        template=RUNNER_TEMPLATE,
    )
    pod_spec = job["spec"]["template"]["spec"]
    rounds: list[bool] = []

    def plan(*_: Any, confirm: bool, **__: Any) -> FixChecksReport:
        rounds.append(confirm)
        return FixChecksReport(
            repo="example/project", pull=42, result=FixChecksResult.PLANNED, reason="Plan"
        )

    monkeypatch.setattr(fix_checks, "run_fix_checks", plan)
    results = {
        container["name"]: cli(*container["args"])
        for container in [*pod_spec["initContainers"], *pod_spec["containers"]]
    }

    assert (
        {name: result.exit_code for name, result in results.items()},
        rounds,
        [name for name, result in results.items() if '"result": "planned"' in result.output],
    ) == ({"prepare": 0, "agent": 0, "publish": 0}, [False], ["prepare"])


@pytest.mark.parametrize(
    ("held", "refused"),
    [((), False), (("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY",), True), (("GH_TOKEN",), True)],
    ids=["model-key-only", "app-key", "github-token"],
)
def test_the_agent_phase_runs_only_with_no_app_key_and_no_github_token(
    config: Any, monkeypatch: pytest.MonkeyPatch, held: tuple[str, ...], refused: bool
) -> None:
    """The agent phase holds the model key only (#2695): in a runner it starts with no App key and
    no GitHub token in its environment, and refuses to start with either (#6601)."""
    from devops_cli.exceptions.roadmap import RoadmapImplementError
    from devops_cli.roadmap.implement.implement_run import require_agent_runner

    config(roadmap={"implement": {"in_runner": True}})
    for name in ("DEVOPS_CLI_SERVICE_GITHUB_APP_PRIVATE_KEY", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    for name in held:
        monkeypatch.setenv(name, "x")

    try:
        require_agent_runner()
        reason = ""
    except RoadmapImplementError as exc:
        reason = str(exc)

    assert (bool(reason), all(name in reason for name in held)) == (refused, True)
