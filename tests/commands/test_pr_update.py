"""Unit and integration tests for GitHub Pull Request branch update integrations."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest
from typer.testing import CliRunner

from devops_cli.ai.mcp.server import pr_update
from devops_cli.commands.pr import app
from devops_cli.config.defaults import (
    DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
    DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS,
)
from devops_cli.core.process import PlannedRequest
from devops_cli.github.branch_update import (
    build_dispatch_ci_cmd,
    build_update_branch_cmd,
    parse_update_error,
    plan_update_single_pr,
)
from tests.support.fakes.github import GitHubApiFake, github_json
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

if TYPE_CHECKING:
    from tests.support.fakes.clock import ClockFake
    from tests.support.fakes.mcp_dispatcher import DispatcherFake

Edges = tuple[GitHubApiFake, ProcessFake]

REQUIRED = ("Static Analysis", "Tests & Coverage")


def _pr(sha: str = "old", head_repo: str = "owner/repo", state: str = "blocked") -> str:
    """Pull request 42 as the REST API gives it, with GitHub's merge state `state`."""
    return json.dumps(
        {
            "head": {"ref": "feat/my-branch", "sha": sha, "repo": {"full_name": head_repo}},
            "base": {"ref": "main"},
            "mergeable": state != "dirty",
            "mergeable_state": state,
        }
    )


def _answer_reads_of_pr_42(
    fake: ProcessFake, *shas: str, head_repo: str = "owner/repo", state: str = "blocked"
) -> None:
    """Answer each read of pull request 42 with the next head SHA; the last one repeats."""
    heads = shas or ("old",)
    reads: list[str] = []

    def answer(call: ProcessCall) -> ProcessAnswer:
        reads.append(call.argv[-1])
        return ProcessAnswer(stdout=_pr(heads[min(len(reads), len(heads)) - 1], head_repo, state))

    fake.answer(["gh", "api", "repos/owner/repo/pulls/42"], answer)


def _serve_checks(
    api: GitHubApiFake,
    sha: str = "old",
    *,
    failing: tuple[str, ...] = ("Tests & Coverage",),
    extra: tuple[str, ...] = (),
) -> None:
    """Route the rules of `main`, which require `REQUIRED`, and the check runs of `sha`: one run
    for each required check and each name in `extra`, failed when `failing` names it."""
    api.route(
        "GET",
        "/repos/owner/repo/rules/branches/main?per_page=100",
        github_json(
            [
                {"type": "deletion"},
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "required_status_checks": [{"context": name} for name in REQUIRED]
                    },
                },
            ]
        ),
    )
    names = (*REQUIRED, *extra)
    api.route(
        "GET",
        f"/repos/owner/repo/commits/{sha}/check-runs?per_page=100",
        github_json(
            {
                "total_count": len(names),
                "check_runs": [
                    {
                        "name": name,
                        "status": "completed",
                        "conclusion": "failure" if name in failing else "success",
                    }
                    for name in names
                ],
            }
        ),
    )


def _updates(fake: ProcessFake) -> list[tuple[str, ...]]:
    """Each update-branch request the fake saw."""
    return [call.argv for call in fake.calls if "update-branch" in " ".join(call.argv)]


def _dispatches(fake: ProcessFake) -> list[tuple[str, ...]]:
    """Each workflow dispatch the fake saw."""
    return [call.argv for call in fake.calls if "dispatches" in " ".join(call.argv)]


def _text(output: str) -> str:
    """`output` with each run of white space as one space, so a wrapped line reads as one."""
    return " ".join(output.split())


PUT_42 = ["gh", "api", "-X", "PUT", "repos/owner/repo/pulls/42/update-branch"]
POST_DISPATCH = ["gh", "api", "-X", "POST", "repos/owner/repo/actions/workflows/ci.yml/dispatches"]


def test_build_update_branch_cmd() -> None:
    """Test construction of GitHub CLI update-branch API command."""
    cmd_plain = build_update_branch_cmd("owner/repo", 101)
    cmd_sha = build_update_branch_cmd("owner/repo", 101, expected_head_sha="sha999")

    assert (
        cmd_plain,
        cmd_sha[-2:],
    ) == (
        ["gh", "api", "-X", "PUT", "repos/owner/repo/pulls/101/update-branch"],
        ["-f", "expected_head_sha=sha999"],
    )


def test_parse_update_error() -> None:
    """Test parsing structured error responses from GitHub API."""
    err_simple = json.dumps({"message": "Branch update failed"})
    err_detailed = json.dumps(
        {"message": "Validation Failed", "errors": ["merge commit cannot be clean"]}
    )
    err_plain = "HTTP 500 Server Error"

    assert (
        parse_update_error(err_simple),
        parse_update_error(err_detailed),
        parse_update_error(err_plain),
        parse_update_error(""),
    ) == (
        "Branch update failed",
        "Validation Failed: merge commit cannot be clean",
        "HTTP 500 Server Error",
        "Unknown API error",
    )


def test_a_dirty_pull_request_gets_the_rebase_steps_and_no_api_write(
    github_api_and_gh: Edges,
) -> None:
    """A pull request that has a merge conflict gets the local rebase steps. The command reads
    no check and sends no update-branch request, which GitHub refuses for a conflict (#4674)."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, state="dirty")

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])

    assert (
        result.exit_code,
        "git fetch origin && git rebase origin/main" in _text(result.output),
        "git push --force-with-lease" in _text(result.output),
        _updates(gh),
        api.requested,
    ) == (1, True, True, [], [])


def test_a_pull_request_behind_main_with_green_checks_gets_no_update(
    github_api_and_gh: Edges,
) -> None:
    """A pull request that is only behind `main`, with every required check green, gets no
    catch-up update, and the command exits 0 with the reason (#4674)."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, state="behind")
    _serve_checks(api, failing=())

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])

    assert (
        result.exit_code,
        _updates(gh),
        "no required check failed" in _text(result.output),
    ) == (0, [], True)


def test_a_failed_required_check_with_no_conflict_gets_one_update(
    github_api_and_gh: Edges,
) -> None:
    """A required check that failed on the head of a pull request with no conflict gets exactly
    one update-branch request, locked to the head that was judged (#4674)."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh)
    _serve_checks(api)
    gh.answer(PUT_42, ProcessAnswer(stdout='{"message": "Updating branch"}'))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])

    assert (
        result.exit_code,
        _updates(gh),
        "Tests & Coverage" in result.output,
    ) == (0, [(*PUT_42, "-f", "expected_head_sha=old")], True)


def test_a_failed_check_that_no_rule_requires_gets_no_update(github_api_and_gh: Edges) -> None:
    """A failed check that the rules of the base branch do not require gets no update (#4674)."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, state="unstable")
    _serve_checks(api, failing=("Docs",), extra=("Docs",))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])

    assert (result.exit_code, _updates(gh)) == (0, [])


def test_checks_that_cannot_be_read_get_no_update(github_api_and_gh: Edges) -> None:
    """When the check runs of the head cannot be read, the command updates nothing and exits 1
    with the reason (#4674)."""
    _, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh)

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])

    assert (
        result.exit_code,
        _updates(gh),
        "Cannot read the required checks of PR #42" in _text(result.output),
    ) == (1, [], True)


def test_the_update_command_takes_one_pull_request_and_has_no_all_option(
    process_fake: ProcessFake,
) -> None:
    """`--all` is gone, and the command needs the number of one pull request (#4674)."""
    runner = CliRunner()
    with_all = runner.invoke(app, ["update", "--all"])
    without_number = runner.invoke(app, ["update"])
    help_text = runner.invoke(app, ["update", "--help"]).output

    assert (
        with_all.exit_code,
        without_number.exit_code,
        "--all" in help_text,
        "--base" in help_text,
        process_fake.calls,
    ) == (2, 2, False, False, [])


def test_the_dry_run_plan_reads_the_checks_before_the_conditional_update() -> None:
    """The plan names the reads that decide the update, and the update only under its condition
    (#4674)."""
    condition = "no conflict, and a required check failed on the head"

    assert plan_update_single_pr(42, "owner/repo") == [
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/pulls/42",
            argv=("gh", "api", "repos/owner/repo/pulls/42"),
        ),
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/rules/branches/<base>",
            condition="no conflict",
            repeat="for each page",
        ),
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/commits/<head-sha>/check-runs",
            condition="no conflict",
            repeat="for each page",
        ),
        PlannedRequest(
            method="PUT",
            target="repos/owner/repo/pulls/42/update-branch",
            argv=tuple(build_update_branch_cmd("owner/repo", 42, "<head-sha>")),
            condition=condition,
        ),
    ]


def test_execute_update_branch(github_api_and_gh: Edges) -> None:
    """Test execution of update branch command on success and failure."""
    api, gh = github_api_and_gh
    runner = CliRunner()
    _answer_reads_of_pr_42(gh)
    _serve_checks(api)
    gh.answer(PUT_42, ProcessAnswer(stdout='{"message": "Updating branch"}'))
    success = runner.invoke(app, ["update", "42", "--repo", "owner/repo"])

    gh.answer(
        PUT_42,
        ProcessAnswer(
            returncode=1, stderr=json.dumps({"message": "Merge conflict between base and head"})
        ),
    )
    failed = runner.invoke(app, ["update", "42", "--repo", "owner/repo"])

    assert (
        success.exit_code,
        failed.exit_code,
        "Merge conflict" in failed.output,
    ) == (0, 1, True)


def test_update_single_pr_cli_success(github_api_and_gh: Edges, clock: ClockFake) -> None:
    """Test CLI devops pr update for a single PR succeeding."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh)
    _serve_checks(api)
    gh.answer(PUT_42, ProcessAnswer(stdout='{"message": "Updating branch"}'))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        len(_updates(gh)),
        len(_dispatches(gh)),
        DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS in clock.waits,
        "Successfully updated branch for PR #42" in result.stdout,
    ) == (0, 1, 0, False, True)


def test_update_single_pr_cli_dry_run(process_fake: ProcessFake) -> None:
    """Test CLI devops pr update with --dry-run bypassing remote API call."""
    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dry-run"])
    assert (
        result.exit_code,
        len(process_fake.calls),
        "[dry-run]" in result.output,
    ) == (0, 0, True)


def test_update_single_pr_cli_failure(github_api_and_gh: Edges) -> None:
    """Test CLI devops pr update failure exiting with status 1."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh)
    _serve_checks(api)
    gh.answer(PUT_42, ProcessAnswer(returncode=1, stderr=json.dumps({"message": "merge conflict"})))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        "Failed to update PR #42" in result.output,
    ) == (1, True)


def test_mcp_pr_update(mcp_dispatcher: DispatcherFake) -> None:
    """Test FastMCP pr_update tool command assembly."""
    res = pr_update(
        number=55,
        repo="owner/repo",
        expected_head_sha="sha123",
        dry_run=True,
    )

    expected_cmd = (
        "uv",
        "run",
        "devops",
        "pr",
        "update",
        "55",
        "--repo",
        "owner/repo",
        "--expected-head-sha",
        "sha123",
        "--dry-run",
    )
    assert (res, [call.argv for call in mcp_dispatcher.calls]) == ("Success", [expected_cmd])


def test_build_dispatch_ci_cmd() -> None:
    """build_dispatch_ci_cmd returns proper GitHub CLI API dispatch invocation."""
    cmd = build_dispatch_ci_cmd("owner/repo", "feat/x")
    assert cmd == [
        "gh",
        "api",
        "-X",
        "POST",
        "repos/owner/repo/actions/workflows/ci.yml/dispatches",
        "-f",
        "ref=feat/x",
    ]


def test_update_single_pr_cli_dispatch_ci_success(
    github_api_and_gh: Edges, clock: ClockFake
) -> None:
    """Test CLI devops pr update --dispatch-ci dispatches CI on head SHA change."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, "old", "new")
    _serve_checks(api)
    gh.answer(PUT_42, ProcessAnswer(stdout="{}"))
    gh.answer(POST_DISPATCH, ProcessAnswer())

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        _dispatches(gh),
        "Dispatched ci.yml" in result.stdout or "dispatched" in result.stdout.lower(),
    ) == (
        0,
        [
            (
                "gh",
                "api",
                "-X",
                "POST",
                "repos/owner/repo/actions/workflows/ci.yml/dispatches",
                "-f",
                "ref=feat/my-branch",
            )
        ],
        True,
    )


def test_update_single_pr_cli_head_sha_unchanged(
    github_api_and_gh: Edges, clock: ClockFake
) -> None:
    """When head.sha never changes, the poll waits at most attempts times, no dispatch, exits 1."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, "unchanged_sha")
    _serve_checks(api, "unchanged_sha")
    gh.answer(PUT_42, ProcessAnswer(stdout="{}"))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    polls = [w for w in clock.waits if w == DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS]
    assert (
        result.exit_code,
        len(_dispatches(gh)),
        len(polls) <= DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
        len(polls) > 0,
        "did not change" in result.output,
    ) == (1, 0, True, True, True)


def test_update_single_pr_cli_fork_head(github_api_and_gh: Edges, clock: ClockFake) -> None:
    """When head.repo is a fork, no poll, no dispatch, output names fork, exits 0."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, "fork_sha", head_repo="other/repo")
    _serve_checks(api, "fork_sha")
    gh.answer(PUT_42, ProcessAnswer(stdout="{}"))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(_dispatches(gh)),
        DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS in clock.waits,
        "other/repo" in result.output,
    ) == (0, 0, False, True)


def test_update_single_pr_cli_dispatch_failed(github_api_and_gh: Edges, clock: ClockFake) -> None:
    """When the dispatch returns non-zero, output carries parsed API error and exits 1."""
    api, gh = github_api_and_gh
    _answer_reads_of_pr_42(gh, "old", "new")
    _serve_checks(api)
    gh.answer(PUT_42, ProcessAnswer(stdout="{}"))
    gh.answer(
        POST_DISPATCH,
        ProcessAnswer(returncode=1, stderr=json.dumps({"message": "Workflow not found"})),
    )

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        "Workflow not found" in result.output,
    ) == (1, True)


def test_update_single_pr_cli_dispatch_ci_dry_run(
    process_fake: ProcessFake, clock: ClockFake
) -> None:
    """update 42 --repo owner/repo --dispatch-ci --dry-run: no poll, no sleep, no dispatch."""
    result = CliRunner().invoke(
        app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci", "--dry-run"]
    )
    assert (
        result.exit_code,
        len(process_fake.calls),
        clock.waits,
        "[dry-run]" in result.output,
    ) == (0, 0, [], True)


def _rate_limit_answer(call: ProcessCall) -> ProcessAnswer:
    return ProcessAnswer(
        returncode=0,
        stdout=json.dumps(
            {
                "resources": {
                    "core": {"limit": 5000, "remaining": 5000, "reset": int(time.time()) + 1},
                    "graphql": {"limit": 5000, "remaining": 5000, "reset": int(time.time()) + 1},
                }
            }
        ),
    )


def test_pr_edit_fallback_patch_title_body_base_milestone(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """devops pr edit falls back to REST PATCH when gh pr edit fails (#2159)."""
    # 0. Answer rate_limit requests
    process_fake.answer(
        lambda call: "rate_limit" in call.argv,
        _rate_limit_answer,
    )
    # 1. gh pr edit fails (triggering fallback)
    process_fake.answer(
        ["gh", "pr", "edit"],
        ProcessAnswer(returncode=1, stderr="GraphQL: mutation error"),
    )
    # 2. REST PATCH pulls (title, body, base) succeeds
    process_fake.answer(
        ["gh", "api", "--method", "PATCH", "repos/owner/repo/pulls/184"],
        ProcessAnswer(returncode=0, stdout='{"number": 184}'),
    )
    # 3. REST PATCH issues (milestone) succeeds
    process_fake.answer(
        ["gh", "api", "--method", "PATCH", "repos/owner/repo/issues/184"],
        ProcessAnswer(returncode=0, stdout='{"number": 184}'),
    )

    result = cli(
        "pr",
        "edit",
        "184",
        "--title",
        "fix(pr): update the title",
        "--body",
        "New Body",
        "--base",
        "main",
        "--milestone",
        "2026-11",
        "--repo",
        "owner/repo",
    )

    assert result.exit_code == 0
    assert "Successfully updated PR #184" in result.output
    # Verify the exact commands executed (excluding internal rate_limit checks)
    cmd_argvs = [call.argv for call in process_fake.calls if "rate_limit" not in call.argv]
    assert len(cmd_argvs) == 3
    assert cmd_argvs[0] == (
        "gh",
        "pr",
        "edit",
        "184",
        "--base",
        "main",
        "--title",
        "fix(pr): update the title",
        "--body",
        "New Body",
        "--repo",
        "owner/repo",
        "--milestone",
        "2026-11",
    )
    assert cmd_argvs[1] == (
        "gh",
        "api",
        "--method",
        "PATCH",
        "repos/owner/repo/pulls/184",
        "-f",
        "title=fix(pr): update the title",
        "-f",
        "body=New Body",
        "-f",
        "base=main",
    )
    assert cmd_argvs[2] == (
        "gh",
        "api",
        "--method",
        "PATCH",
        "repos/owner/repo/issues/184",
        "-F",
        "milestone=2026-11",
    )


def test_pr_edit_fallback_milestone_failure_fails_with_message(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """A failed milestone PATCH makes devops pr edit fail with its message (#2159)."""
    # 0. Answer rate_limit requests
    process_fake.answer(
        lambda call: "rate_limit" in call.argv,
        _rate_limit_answer,
    )
    # 1. gh pr edit fails
    process_fake.answer(
        ["gh", "pr", "edit"],
        ProcessAnswer(returncode=1, stderr="GraphQL: mutation error"),
    )
    # 2. REST PATCH pulls succeeds
    process_fake.answer(
        ["gh", "api", "--method", "PATCH", "repos/owner/repo/pulls/184"],
        ProcessAnswer(returncode=0, stdout='{"number": 184}'),
    )
    # 3. REST PATCH issues (milestone) fails with descriptive error message
    process_fake.answer(
        ["gh", "api", "--method", "PATCH", "repos/owner/repo/issues/184"],
        ProcessAnswer(returncode=1, stderr="Milestone '2026-11' does not exist."),
    )

    result = cli(
        "pr",
        "edit",
        "184",
        "--title",
        "fix(pr): update the title",
        "--milestone",
        "2026-11",
        "--repo",
        "owner/repo",
    )

    assert result.exit_code != 0
    assert "Milestone '2026-11' does not exist." in result.output


@pytest.mark.parametrize(
    ("title", "problem"),
    [
        ("fix(pr)!: add the check", "The title has `!`."),
        ("fix(pr): " + "a" * 70, "The summary has 70 characters"),
    ],
)
def test_pr_edit_refuses_a_title_that_the_title_check_refuses(
    cli: Callable[..., Any], process_fake: ProcessFake, title: str, problem: str
) -> None:
    """An edited title keeps the form of `pr create` (#4782)."""
    result = cli("pr", "edit", "184", "--title", title)

    assert (result.exit_code, problem in result.output) == (1, True)
    assert all(
        "pr" != call.argv[1:2][0] for call in process_fake.calls if call.argv[:2] == ["gh", "pr"]
    )
