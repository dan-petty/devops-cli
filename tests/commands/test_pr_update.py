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
    open_prs_argv,
    parse_update_error,
    plan_update_all_prs,
)
from devops_cli.lang import MESSAGES
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake

if TYPE_CHECKING:
    from tests.support.fakes.clock import ClockFake
    from tests.support.fakes.mcp_dispatcher import DispatcherFake


def _pr(sha: str = "old", head_repo: str = "owner/repo") -> str:
    """Pull request 42 as the REST API gives it."""
    return json.dumps(
        {
            "head": {"ref": "feat/my-branch", "sha": sha, "repo": {"full_name": head_repo}},
            "base": {"ref": "main"},
        }
    )


def _answer_reads_of_pr_42(fake: ProcessFake, *shas: str, head_repo: str = "owner/repo") -> None:
    """Answer each read of pull request 42 with the next head SHA; the last one repeats."""
    heads = shas or ("old",)
    reads: list[str] = []

    def answer(call: ProcessCall) -> ProcessAnswer:
        reads.append(call.argv[-1])
        return ProcessAnswer(stdout=_pr(heads[min(len(reads), len(heads)) - 1], head_repo))

    fake.answer(["gh", "api", "repos/owner/repo/pulls/42"], answer)


def _updates(fake: ProcessFake) -> list[tuple[str, ...]]:
    """Each update-branch request the fake saw."""
    return [call.argv for call in fake.calls if "update-branch" in " ".join(call.argv)]


def _dispatches(fake: ProcessFake) -> list[tuple[str, ...]]:
    """Each workflow dispatch the fake saw."""
    return [call.argv for call in fake.calls if "dispatches" in " ".join(call.argv)]


def _candidates(*numbers: int, draft: tuple[int, ...] = ()) -> str:
    """`gh pr list` output for open pull requests `numbers`."""
    return json.dumps(
        [
            {
                "number": n,
                "headRefName": f"feat/{n}",
                "baseRefName": "main",
                "isDraft": n in draft,
            }
            for n in numbers
        ]
    )


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


def test_execute_update_branch(gh_edge: ProcessFake) -> None:
    """Test execution of update branch command on success and failure."""
    runner = CliRunner()
    _answer_reads_of_pr_42(gh_edge)
    gh_edge.answer(PUT_42, ProcessAnswer(stdout='{"message": "Updating branch"}'))
    success = runner.invoke(app, ["update", "42", "--repo", "owner/repo"])

    gh_edge.answer(
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


def test_process_candidate_pr_row(gh_edge: ProcessFake) -> None:
    """Test processing draft and active pull request table rows."""
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=_candidates(10, 11, draft=(10,))))
    gh_edge.answer(
        ["gh", "api", "repos/owner/repo/pulls/11"],
        ProcessAnswer(stdout=_pr()),
    )
    gh_edge.answer(["gh", "api", "-X", "PUT"], ProcessAnswer(stdout="{}"))

    result = CliRunner().invoke(app, ["update", "--all", "--repo", "owner/repo"])

    rows = {n: next(x for x in result.output.splitlines() if n in x) for n in ("#10", "#11")}
    assert (result.exit_code, "draft (skipped)" in rows["#10"], "updated" in rows["#11"]) == (
        0,
        True,
        True,
    )


def test_update_single_pr_cli_success(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """Test CLI devops pr update for a single PR succeeding."""
    _answer_reads_of_pr_42(gh_edge)
    gh_edge.answer(PUT_42, ProcessAnswer(stdout='{"message": "Updating branch"}'))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        len(_updates(gh_edge)),
        len(_dispatches(gh_edge)),
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


def test_update_single_pr_cli_failure(gh_edge: ProcessFake) -> None:
    """Test CLI devops pr update failure exiting with status 1."""
    _answer_reads_of_pr_42(gh_edge)
    gh_edge.answer(
        PUT_42, ProcessAnswer(returncode=1, stderr=json.dumps({"message": "merge conflict"}))
    )

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        "Failed to update PR #42" in result.output,
    ) == (1, True)


def test_update_all_prs_cli(gh_edge: ProcessFake) -> None:
    """Test CLI devops pr update --all batch processing."""
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=_candidates(201, 202, draft=(202,))))
    gh_edge.answer(["gh", "api", "repos/owner/repo/pulls/201"], ProcessAnswer(stdout=_pr()))
    gh_edge.answer(["gh", "api", "-X", "PUT"], ProcessAnswer(stdout="{}"))

    result = CliRunner().invoke(app, ["update", "--all", "--repo", "owner/repo"])
    assert (
        result.exit_code,
        "Pull Request Branch Update Summary" in result.stdout,
        "#201" in result.stdout,
        "#202" in result.stdout,
    ) == (0, True, True, True)


def test_update_missing_args(process_fake: ProcessFake) -> None:
    """Test CLI devops pr update without PR number or --all exits with error."""
    result = CliRunner().invoke(app, ["update"])
    assert (
        result.exit_code,
        "Please specify a PR number or use --all" in result.output,
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


def test_sort_prs_oldest_first() -> None:
    """Verify sort_prs_oldest_first orders PRs in ascending order by number (FIFO)."""
    from devops_cli.github.pr_monitor import sort_prs_oldest_first

    newest_first = [
        {"number": 577, "title": "PR 577"},
        {"number": 576, "title": "PR 576"},
        {"number": 573, "title": "PR 573"},
        {"number": 575, "title": "PR 575"},
        {"number": 574, "title": "PR 574"},
    ]
    sorted_prs = sort_prs_oldest_first(newest_first)
    numbers = [p["number"] for p in sorted_prs]
    assert numbers == [573, 574, 575, 576, 577]


def test_update_all_prs_runs_oldest_first(gh_edge: ProcessFake) -> None:
    """Verify devops pr update --all processes candidates in oldest-first order."""
    # Provide descending PR numbers matching gh pr list default order
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=_candidates(577, 576, 573)))
    gh_edge.answer(["gh", "api", "-X", "PUT"], ProcessAnswer(stdout="{}"))
    gh_edge.answer(["gh", "api", "repos/owner/repo/pulls"], ProcessAnswer(stdout=_pr()))

    res = CliRunner().invoke(app, ["update", "--all", "--repo", "owner/repo"])
    updated_order = [int(argv[-1].split("/")[-2]) for argv in _updates(gh_edge)]
    assert (res.exit_code, updated_order) == (0, [573, 576, 577])


def test_fetch_open_prs_sorts_oldest_first(gh_edge: ProcessFake) -> None:
    """Verify `update --all` sorts gh pr list output in oldest-first order."""
    raw_output = json.dumps(
        [
            {"number": 300, "headRefName": "feat/3", "baseRefName": "main", "isDraft": False},
            {"number": 100, "headRefName": "feat/1", "baseRefName": "main", "isDraft": False},
            {"number": 200, "headRefName": "feat/2", "baseRefName": "main", "isDraft": False},
        ]
    )
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=raw_output))
    gh_edge.answer(["gh", "api", "-X", "PUT"], ProcessAnswer(stdout="{}"))
    gh_edge.answer(["gh", "api", "repos/owner/repo/pulls"], ProcessAnswer(stdout=_pr()))
    CliRunner().invoke(app, ["update", "--all", "--repo", "owner/repo", "--base", "main"])
    numbers = [int(argv[-1].split("/")[-2]) for argv in _updates(gh_edge)]
    assert numbers == [100, 200, 300]


@pytest.mark.parametrize(
    ("base", "filtered"),
    [(None, []), ("main", ["--base", "main"])],
    ids=["any-base", "one-base"],
)
def test_update_all_lists_only_the_current_accounts_open_prs(
    base: str | None, filtered: list[str], gh_edge: ProcessFake
) -> None:
    """`--all` lists the open PRs that gh's own account wrote, so a PR that a bot or another
    person owns, such as the one release-please writes, is never updated."""
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout="[]"))
    CliRunner().invoke(
        app, ["update", "--all", "--repo", "owner/repo", *(["--base", base] if base else [])]
    )
    listed = list(gh_edge.calls[0].argv)
    planned = list(plan_update_all_prs("owner/repo", base)[0].argv)
    assert (listed[:7], listed[-2:] if base else [], planned) == (
        ["gh", "pr", "list", "--state", "open", "--author", "@me"],
        filtered,
        listed,
    )


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


def test_update_single_pr_cli_dispatch_ci_success(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """Test CLI devops pr update --dispatch-ci dispatches CI on head SHA change."""
    _answer_reads_of_pr_42(gh_edge, "old", "new")
    gh_edge.answer(PUT_42, ProcessAnswer(stdout="{}"))
    gh_edge.answer(POST_DISPATCH, ProcessAnswer())

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        _dispatches(gh_edge),
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


def test_update_single_pr_cli_head_sha_unchanged(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """When head.sha never changes, the poll waits at most attempts times, no dispatch, exits 1."""
    _answer_reads_of_pr_42(gh_edge, "unchanged_sha")
    gh_edge.answer(PUT_42, ProcessAnswer(stdout="{}"))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    polls = [w for w in clock.waits if w == DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS]
    assert (
        result.exit_code,
        len(_dispatches(gh_edge)),
        len(polls) <= DEFAULT_PR_UPDATE_HEAD_POLL_ATTEMPTS,
        len(polls) > 0,
        "did not change" in result.output,
    ) == (1, 0, True, True, True)


def test_update_single_pr_cli_fork_head(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """When head.repo is a fork, no poll, no dispatch, output names fork, exits 0."""
    _answer_reads_of_pr_42(gh_edge, "fork_sha", head_repo="other/repo")
    gh_edge.answer(PUT_42, ProcessAnswer(stdout="{}"))

    result = CliRunner().invoke(app, ["update", "42", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(_dispatches(gh_edge)),
        DEFAULT_PR_UPDATE_HEAD_POLL_INTERVAL_SECONDS in clock.waits,
        "other/repo" in result.output,
    ) == (0, 0, False, True)


def test_update_single_pr_cli_dispatch_failed(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """When the dispatch returns non-zero, output carries parsed API error and exits 1."""
    _answer_reads_of_pr_42(gh_edge, "old", "new")
    gh_edge.answer(PUT_42, ProcessAnswer(stdout="{}"))
    gh_edge.answer(
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


def test_update_all_prs_cli_dispatch_ci(gh_edge: ProcessFake, clock: ClockFake) -> None:
    """update --all --repo owner/repo --dispatch-ci dispatches CI for each pull request it updates."""
    gh_edge.answer(["gh", "pr", "list"], ProcessAnswer(stdout=_candidates(201, 202, draft=(202,))))
    reads = iter(["old", "new"])
    gh_edge.answer(
        ["gh", "api", "repos/owner/repo/pulls/201"],
        lambda call: ProcessAnswer(stdout=_pr(next(reads, "new"))),
    )
    gh_edge.answer(["gh", "api", "-X", "PUT"], ProcessAnswer(stdout="{}"))
    gh_edge.answer(
        ["gh", "api", "-X", "POST", "repos/owner/repo/actions/workflows/ci.yml/dispatches"],
        ProcessAnswer(),
    )

    result = CliRunner().invoke(app, ["update", "--all", "--repo", "owner/repo", "--dispatch-ci"])
    assert (
        result.exit_code,
        len(_dispatches(gh_edge)),
        "dispatched" in result.stdout,
        "draft (skipped)" in result.stdout,
    ) == (0, 1, True, True)


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
        "New Title",
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
        "New Title",
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
        "title=New Title",
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
        "New Title",
        "--milestone",
        "2026-11",
        "--repo",
        "owner/repo",
    )

    assert result.exit_code != 0
    assert "Milestone '2026-11' does not exist." in result.output


def test_pr_update_all_dry_run_plan_whole_value(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """devops pr update --all --dry-run plans requests without mutating external state (#2159)."""
    # 1. Plan without --dispatch-ci as whole value
    plan_no_dispatch = plan_update_all_prs("owner/repo", None, dispatch_ci=False)
    assert plan_no_dispatch == [
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/pulls",
            argv=tuple(open_prs_argv("owner/repo", None)),
        ),
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/pulls/<number>",
            argv=("gh", "api", "repos/owner/repo/pulls/<number>"),
            repeat="each open non-draft PR",
        ),
        PlannedRequest(
            method="PUT",
            target="repos/owner/repo/pulls/<number>/update-branch",
            argv=("gh", "api", "-X", "PUT", "repos/owner/repo/pulls/<number>/update-branch"),
            repeat="each open non-draft PR",
        ),
    ]

    # 2. Plan with --dispatch-ci as whole value
    plan_dispatch = plan_update_all_prs("owner/repo", "main", dispatch_ci=True)
    assert plan_dispatch == [
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/pulls",
            argv=tuple(open_prs_argv("owner/repo", "main")),
        ),
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/pulls/<number>",
            argv=("gh", "api", "repos/owner/repo/pulls/<number>"),
            repeat="each open non-draft PR",
        ),
        PlannedRequest(
            method="PUT",
            target="repos/owner/repo/pulls/<number>/update-branch",
            argv=("gh", "api", "-X", "PUT", "repos/owner/repo/pulls/<number>/update-branch"),
            repeat="each open non-draft PR",
        ),
        PlannedRequest(
            method="GET",
            target="repos/owner/repo/pulls/<number>",
            argv=("gh", "api", "repos/owner/repo/pulls/<number>"),
            repeat="each open non-draft PR; up to 6, 5s apart",
        ),
        PlannedRequest(
            method="POST",
            target="repos/owner/repo/actions/workflows/ci.yml/dispatches",
            argv=tuple(build_dispatch_ci_cmd("owner/repo", "<branch>")),
            condition="the head changed and lives in this repository",
            repeat="each open non-draft PR",
        ),
    ]

    # 3. CLI execution with --dry-run
    res1 = cli("pr", "update", "--all", "--dry-run", "--repo", "owner/repo")
    assert res1.exit_code == 0
    assert MESSAGES.pr.update_all_dry_run_heading in res1.output
    assert "repos/owner/repo/pulls/<number>/update-branch" in res1.output

    # 4. CLI execution with --dry-run and --dispatch-ci
    res2 = cli("pr", "update", "--all", "--dry-run", "--dispatch-ci", "--repo", "owner/repo")
    assert res2.exit_code == 0
    assert "repos/owner/repo/actions/workflows/ci.yml/dispatches" in res2.output

    # 5. Zero external requests were sent
    assert len(process_fake.calls) == 0


def test_pr_update_all_executes_oldest_first_and_skips_draft(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """devops pr update --all updates open PRs oldest first and leaves drafts alone (#2159)."""
    # 0. Answer rate_limit requests
    process_fake.answer(
        lambda call: "rate_limit" in call.argv,
        _rate_limit_answer,
    )
    # Candidate list: PR 10 (older), PR 20 (newer), PR 5 (draft)
    candidate_prs = [
        {
            "number": 20,
            "headRefName": "feat/newer",
            "baseRefName": "main",
            "isDraft": False,
            "createdAt": "2026-10-05T12:00:00Z",
        },
        {
            "number": 10,
            "headRefName": "feat/older",
            "baseRefName": "main",
            "isDraft": False,
            "createdAt": "2026-10-01T12:00:00Z",
        },
        {
            "number": 5,
            "headRefName": "feat/draft",
            "baseRefName": "main",
            "isDraft": True,
            "createdAt": "2026-09-20T12:00:00Z",
        },
    ]

    process_fake.answer(
        ["gh", "pr", "list"],
        ProcessAnswer(returncode=0, stdout=json.dumps(candidate_prs)),
    )
    process_fake.answer(
        ["gh", "api", "-X", "PUT", "repos/owner/repo/pulls/10/update-branch"],
        ProcessAnswer(returncode=0, stdout='{"message": "Updating branch"}'),
    )
    process_fake.answer(
        ["gh", "api", "-X", "PUT", "repos/owner/repo/pulls/20/update-branch"],
        ProcessAnswer(returncode=0, stdout='{"message": "Updating branch"}'),
    )

    result = cli("pr", "update", "--all", "--repo", "owner/repo")
    assert result.exit_code == 0
    assert "draft (skipped)" in result.output

    # Query filtered by --author @me, leaving pull requests of other authors alone
    list_call = next(
        call for call in process_fake.calls if "pr" in call.argv and "list" in call.argv
    )
    assert "--author" in list_call.argv
    assert "@me" in list_call.argv

    # Check update order: PR 10 before PR 20; PR 5 not updated
    update_calls = [
        call.argv for call in process_fake.calls if "update-branch" in " ".join(call.argv)
    ]
    assert len(update_calls) == 2
    assert "repos/owner/repo/pulls/10/update-branch" in update_calls[0]
    assert "repos/owner/repo/pulls/20/update-branch" in update_calls[1]


def test_pr_update_all_no_open_prs_prints_message(
    cli: Callable[..., Any], process_fake: ProcessFake
) -> None:
    """devops pr update --all prints no PRs message when none are found (#2159)."""
    # 0. Answer rate_limit requests
    process_fake.answer(
        lambda call: "rate_limit" in call.argv,
        _rate_limit_answer,
    )
    process_fake.answer(
        ["gh", "pr", "list"],
        ProcessAnswer(returncode=0, stdout="[]"),
    )

    result = cli("pr", "update", "--all", "--repo", "owner/repo")
    assert result.exit_code == 0
    assert MESSAGES.pr.update_branch_no_prs in result.output
    # No update requests were made
    assert not any("update-branch" in " ".join(call.argv) for call in process_fake.calls)
