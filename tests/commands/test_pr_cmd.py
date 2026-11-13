"""Unit tests for devops pr command group.

Every case reaches GitHub through the edges of the code: `gh` through `process_fake`, the GitHub
session through `github_api`, and the roadmap through the in-memory store.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import httpx2
import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app
from devops_cli.config.defaults import DEFAULT_GH_MUTATION_MIN_INTERVAL_SECONDS
from tests.support.fakes.process import ProcessAnswer
from tests.support.gh_process import (
    answer_gh,
    answer_origin,
    fresh_quota,
    gh_argv,
    mentions,
    script_gh,
)

if TYPE_CHECKING:
    from tests.support.fakes.clock import ClockFake
    from tests.support.fakes.github import GitHubApiFake
    from tests.support.fakes.process import ProcessFake
    from tests.support.fakes.roadmap_store import InMemoryRoadmapStore

LABELS = "".join(
    f'- name: "{name}"\n  color: "ededed"\n' for name in ("type/feature", "scope/pr", "type/fix")
)
TITLE = "feat(pr): open a draft pull request"
BODY = (
    "A draft pull request keeps the work out of review until the checks pass.\n\n"
    "Closes #3198\n\nChange: `openspec/changes/archive/2026-11-02-3198-pull-request-form/`"
)
NO_CLOSING_ISSUES = json.dumps(
    {
        "data": {
            "repository": {
                "pullRequest": {"closingIssuesReferences": {"totalCount": 0, "nodes": []}}
            }
        }
    }
)
GH_FAILED = ProcessAnswer(returncode=1, stderr="GraphQL: the query failed")
REPO = "example/roadmap"


def _threads_page(*threads: dict[str, Any]) -> str:
    """The reply to the listing of review threads, as GraphQL gives it."""
    page = {"nodes": list(threads), "pageInfo": {"hasNextPage": False}}
    return json.dumps({"data": {"repository": {"pullRequest": {"reviewThreads": page}}}})


def _thread(thread_id: str, *comments: tuple[str, str], resolved: bool = False) -> dict[str, Any]:
    """A review thread with `(author, body)` comments."""
    nodes = [
        {"id": f"{thread_id}_c{n}", "body": body, "author": {"login": author}}
        for n, (author, body) in enumerate(comments)
    ]
    return {
        "id": thread_id,
        "isResolved": resolved,
        "path": "src/main.py",
        "line": 20,
        "comments": {"nodes": nodes},
    }


def _thread_reply(data_key: str, *, resolved: bool) -> str:
    """The reply to a mutation that moves a thread."""
    return json.dumps({"data": {data_key: {"thread": {"isResolved": resolved}}}})


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def labels(roadmap_store: InMemoryRoadmapStore) -> InMemoryRoadmapStore:
    """The labels file of the repository, which `pr create` reads to check the scope of a title
    (#3198). The status and the labels of an opened pull request are held by
    tests/commands/test_pr_status.py and tests/commands/test_pr_title_labels.py."""
    roadmap_store.seed_file(".github/labels.yml", LABELS)
    roadmap_store.seed_file(".github/labels.yml", LABELS, ref="main")
    return roadmap_store


class TestPrCommands:
    """Tests for devops pr subcommands."""

    def test_list_prs_requires_gh_cli(self, runner: CliRunner) -> None:
        from unittest.mock import patch

        with patch("shutil.which", return_value=None):
            result = runner.invoke(app, ["list"])
            assert result.exit_code == 1
            assert "GitHub CLI ('gh') is required" in result.output

    def test_list_prs_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        mock_output = (
            '[{"number": 13, "title": "fix(security): resolve review findings", '
            '"state": "OPEN", "headRefName": "feat/security", "baseRefName": "main", '
            '"author": {"login": "devops-user"}, "updatedAt": "2026-08-18T15:00:00Z", '
            '"url": "https://example.com/org/repo/pull/13"}]'
        )
        answer_gh(gh_edge, "pr", "list", stdout=mock_output)
        result = runner.invoke(app, ["list", "--state", "open"])
        assert result.exit_code == 0
        assert "#13" in result.output
        assert "feat/security" in result.output
        assert "main" in result.output

    def test_list_prs_empty(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_gh(gh_edge, "pr", "list", stdout="[]")
        result = runner.invoke(app, ["list"])
        assert result.exit_code == 0
        assert "No pull requests found" in result.output

    def test_view_pr(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_gh(gh_edge, "pr", "view", stdout="PR details")
        result = runner.invoke(app, ["view", "13", "--repo", "owner/repo"])
        assert result.exit_code == 0
        assert len(gh_argv(gh_edge)) == 1
        args = gh_argv(gh_edge)[0]
        assert "view" in args
        assert "13" in args
        assert "owner/repo" in args

    def test_pr_checks(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        mock_checks = json.dumps(
            [
                {
                    "name": "CI Quality Gate",
                    "state": "SUCCESS",
                    "bucket": "pass",
                    "workflow": "CI",
                    "link": "https://example.com/runs/1",
                }
            ]
        )
        answer_gh(gh_edge, "pr", "checks", stdout=mock_checks)
        result = runner.invoke(app, ["checks", "13"])
        args = gh_argv(gh_edge)[0]
        assert (
            result.exit_code,
            len(gh_argv(gh_edge)),
            "checks" in args,
            "13" in args,
        ) == (0, 1, True, True)

    def test_edit_pr(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        result = runner.invoke(app, ["edit", "13", "--base", "main", "--title", "New Title"])
        assert result.exit_code == 0
        assert "Successfully updated PR #13" in result.output
        args = gh_argv(gh_edge)[0]
        assert "--base" in args
        assert "main" in args

    def test_create_opens_a_draft_into_the_default_branch(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        """Without --base gh picks the repository's default branch, and the PR is a draft."""
        answer_gh(gh_edge, "pr", "create", stdout="https://example.com/org/repo/pull/14\n")
        result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY])
        args = gh_argv(gh_edge)[0]
        assert (
            result.exit_code,
            "Opened a draft pull request: https://example.com/org/repo/pull/14." in result.output,
            "--draft" in args,
            "--base" in args,
        ) == (0, True, True, False)

    def test_create_passes_the_base_it_is_given(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        result = runner.invoke(
            app, ["create", "--title", TITLE, "--body", BODY, "--base", "feat/base"]
        )
        args = gh_argv(gh_edge)[0]
        assert (
            result.exit_code,
            args[args.index("--base") + 1],
            "--draft" in args,
            "Opened a draft pull request into feat/base." in result.output,
        ) == (0, "feat/base", True, True)

    def test_threads_list_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_origin(gh_edge, "owner/repo")
        listing = _threads_page(_thread("PRRT_1", ("alice", "Fix timeout")))
        answer_gh(gh_edge, stdout=listing)
        res = runner.invoke(app, ["threads", "list", "83"])
        assert res.exit_code == 0
        assert "PRRT_1" in res.output
        assert "Open" in res.output

    def test_threads_list_error_exit(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_origin(gh_edge, "owner/repo")
        answer_gh(gh_edge, returncode=1, stderr="API failure")
        res = runner.invoke(app, ["threads", "list", "83"])
        assert res.exit_code == 1
        assert "Failed to retrieve PR #83 review threads" in res.output
        assert "API failure" in res.output

    def test_threads_reply_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        reply = {"data": {"addPullRequestReviewThreadReply": {"comment": {"id": "C_reply_1"}}}}
        answer_gh(gh_edge, stdout=json.dumps(reply))
        res = runner.invoke(app, ["threads", "reply", "PRRT_1", "Addressed in commit 123"])
        assert res.exit_code == 0
        assert "In-thread reply posted successfully" in res.output
        assert "C_reply_1" in res.output
        assert any("body=Addressed in commit 123" in arg for arg in gh_argv(gh_edge)[0])

    def test_threads_resolve_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        one = {
            "data": {
                "node": _thread(
                    "PRRT_1", ("reviewer", "Fix this"), ("developer", "Addressed in commit abc")
                )
            }
        }
        gh_edge.answer(mentions("GetReviewThread"), ProcessAnswer(stdout=json.dumps(one)))
        gh_edge.answer(
            mentions("ResolveThread"),
            ProcessAnswer(stdout=_thread_reply("resolveReviewThread", resolved=True)),
        )
        res = runner.invoke(app, ["threads", "resolve", "PRRT_1"])
        assert (res.exit_code, "Thread PRRT_1 marked as resolved" in res.output) == (0, True)

    def test_threads_resolve_refuses_without_reply(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        # Probe case: follow-up by the same author does not count as a valid reply
        probe = {
            "data": {
                "node": _thread(
                    "PRRT_PROBE", ("reviewer", "Fix this"), ("reviewer", "Still not fixed.")
                )
            }
        }
        answer_gh(gh_edge, stdout=json.dumps(probe))
        res = runner.invoke(app, ["threads", "resolve", "PRRT_PROBE"])
        assert (
            res.exit_code,
            "has no reply from someone other than the thread opener" in res.output,
            "--without-reply" in res.output,
        ) == (1, True, True)

    def test_threads_resolve_override_without_reply(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        answer_gh(gh_edge, stdout=_thread_reply("resolveReviewThread", resolved=True))
        res = runner.invoke(app, ["threads", "resolve", "PRRT_1", "--without-reply"])
        assert (res.exit_code, "Thread PRRT_1 marked as resolved" in res.output) == (0, True)

    def test_threads_resolve_override_short_flag(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        answer_gh(gh_edge, stdout=_thread_reply("resolveReviewThread", resolved=True))
        res = runner.invoke(app, ["threads", "resolve", "PRRT_1", "-w"])
        assert (res.exit_code, "Thread PRRT_1 marked as resolved" in res.output) == (0, True)

    def test_threads_resolve_fetch_error(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_gh(gh_edge, returncode=1, stderr="GraphQL query failed")
        res = runner.invoke(app, ["threads", "resolve", "PRRT_FAIL"])
        assert (
            res.exit_code,
            "Failed to fetch review thread PRRT_FAIL" in res.output,
        ) == (1, True)

    def test_threads_unresolve_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_gh(gh_edge, stdout=_thread_reply("unresolveReviewThread", resolved=False))
        res = runner.invoke(app, ["threads", "unresolve", "PRRT_1"])
        assert res.exit_code == 0
        assert "reopened (unresolved)" in res.output

    def test_threads_resolve_all_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_origin(gh_edge, "owner/repo")
        listing = _threads_page(
            _thread("PRRT_1", ("reviewer", "Fix this"), ("developer", "Addressed")),
            _thread("PRRT_2", ("reviewer", "Still open")),
        )
        answer_gh(gh_edge, stdout=_thread_reply("resolveReviewThread", resolved=True))
        gh_edge.answer(mentions("GetReviewThreads"), ProcessAnswer(stdout=listing))
        res = runner.invoke(app, ["threads", "resolve-all", "83"])
        assert res.exit_code == 0
        assert "Resolved 1/1 review thread(s) on PR #83" in res.output
        resolved = [argv for argv in gh_argv(gh_edge) if any("ResolveThread" in a for a in argv)]
        assert [any("threadId=PRRT_1" == a for a in argv) for argv in resolved] == [True]

    def test_threads_resolve_all_empty(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        answer_origin(gh_edge, "owner/repo")
        answer_gh(gh_edge, stdout=_threads_page())
        res = runner.invoke(app, ["threads", "resolve-all", "83"])
        assert res.exit_code == 0
        assert "No unresolved candidate review threads found on PR #83" in res.output

    def test_pr_monitor_invalid_bounds_and_format(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        answer_origin(gh_edge, "owner/repo")
        res_int = runner.invoke(app, ["monitor", "168", "--interval", "0"])
        assert res_int.exit_code != 0

        res_timeout = runner.invoke(app, ["monitor", "168", "--timeout", "0"])
        assert res_timeout.exit_code != 0

        res_fmt = runner.invoke(app, ["monitor", "168", "--format", "invalid_fmt"])
        assert res_fmt.exit_code != 0
        assert "Unsupported format" in res_fmt.output

    def test_pr_diff_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr diff outputs unified diff."""
        answer_gh(gh_edge, stdout="diff --git a/file.py b/file.py\n+new line")
        result = runner.invoke(app, ["diff", "179"])
        assert result.exit_code == 0
        assert "+new line" in result.output
        args = gh_argv(gh_edge)[0]
        assert "diff" in args
        assert "179" in args

    def test_pr_close_success(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr close closes a pull request with optional comment."""
        result = runner.invoke(
            app, ["close", "179", "--comment", "Superseded by new design", "--delete-branch"]
        )
        assert result.exit_code == 0
        assert "closed successfully" in result.output
        args = gh_argv(gh_edge)[0]
        assert "close" in args
        assert "179" in args
        assert "--comment" in args
        assert "--delete-branch" in args

    def test_pr_view_fallback_on_gh_failure(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr view falls back to REST API when gh pr view fails."""
        mock_pr_json = json.dumps(
            {
                "title": "fix: resolve issue",
                "state": "open",
                "draft": True,
                "html_url": "https://example.com/pulls/184",
                "head": {"ref": "feature-branch"},
                "base": {"ref": "main"},
                "user": {"login": "testuser"},
                "body": "Detailed description text",
            }
        )
        answer_origin(gh_edge, "owner/repo")
        script_gh(gh_edge, GH_FAILED, ProcessAnswer(stdout=mock_pr_json))
        res = runner.invoke(app, ["view", "184"])
        assert res.exit_code == 0
        assert "fix: resolve issue" in res.output
        assert "Detailed description text" in res.output

    def test_pr_checks_fallback_on_gh_failure(
        self,
        runner: CliRunner,
        github_api_and_gh: tuple[GitHubApiFake, ProcessFake],
    ) -> None:
        """devops pr checks falls back to the REST check-runs listing, read through the GitHub
        session, when gh pr checks fails."""
        github_api, gh = github_api_and_gh
        fresh_quota()
        mock_checks_json = json.dumps(
            {
                "check_runs": [
                    {
                        "name": "Validation",
                        "status": "completed",
                        "conclusion": "success",
                        "html_url": "https://example.com/runs/1",
                    },
                    {
                        "name": "Analyze",
                        "status": "completed",
                        "conclusion": "failure",
                        "html_url": "https://example.com/runs/2",
                    },
                ]
            }
        )
        github_api.route(
            "GET",
            "/repos/owner/repo/commits/abcdef123456/check-runs?per_page=100",
            httpx2.Response(
                200, headers={"content-type": "application/json"}, content=mock_checks_json.encode()
            ),
        )
        mock_statuses_json = json.dumps(
            {
                "state": "success",
                "total_count": 1,
                "statuses": [
                    {
                        "context": "ci/status",
                        "state": "success",
                        "target_url": "https://example.com/status/1",
                    }
                ],
            }
        )
        answer_origin(gh, "owner/repo")
        script_gh(
            gh,
            GH_FAILED,
            ProcessAnswer(stdout=json.dumps({"head": {"sha": "abcdef123456"}})),
            ProcessAnswer(stdout=mock_statuses_json),
        )
        res = runner.invoke(app, ["checks", "184"])
        assert (
            res.exit_code,
            "Validation" in res.output,
            "Analyze" in res.output,
            "ci/status" in res.output,
        ) == (1, True, True, True)

    def test_pr_edit_fallback(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr edit falls back to REST PATCH when gh pr edit fails."""
        answer_origin(gh_edge, "owner/repo")
        script_gh(gh_edge, GH_FAILED, ProcessAnswer())
        res = runner.invoke(
            app, ["edit", "184", "--title", "New Title", "--body", "New Body", "--base", "main"]
        )
        assert res.exit_code == 0
        assert "Successfully updated PR #184" in res.output
        assert len(gh_argv(gh_edge)) == 2
        patch_cmd = gh_argv(gh_edge)[1]
        assert "PATCH" in patch_cmd
        assert "title=New Title" in patch_cmd

    def test_pr_edit_no_changes(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr edit warns when no options are provided."""
        answer_origin(gh_edge, "owner/repo")
        res = runner.invoke(app, ["edit", "184"])
        assert res.exit_code == 0
        assert "No changes specified" in res.output

    def test_pr_edit_with_milestone(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr edit passes --milestone to gh pr edit and succeeds."""
        answer_origin(gh_edge, "owner/repo")
        res = runner.invoke(app, ["edit", "184", "--milestone", "2026-11"])
        assert res.exit_code == 0
        assert "Successfully updated PR #184" in res.output
        assert "--milestone" in gh_argv(gh_edge)[0]
        assert "2026-11" in gh_argv(gh_edge)[0]

    def test_list_prs_rest_fallback(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr list falls back to REST when GraphQL fails."""
        mock_rest_prs = json.dumps(
            [
                {
                    "number": 187,
                    "title": "feat: test pr",
                    "head": {"ref": "feat/test"},
                    "base": {"ref": "main"},
                    "user": {"login": "test-user"},
                    "updated_at": "2026-09-13T12:00:00Z",
                    "html_url": "https://example.com/pr/187",
                }
            ]
        )
        answer_origin(gh_edge, "owner/repo")
        script_gh(gh_edge, GH_FAILED, ProcessAnswer(stdout=mock_rest_prs))
        res = runner.invoke(app, ["list"])
        assert res.exit_code == 0
        assert "#187" in res.output
        assert "feat: test pr" in res.output

    def test_pr_diff_mask_secrets(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr diff masks secret tokens in output."""
        answer_gh(gh_edge, stdout="+ export GITHUB_TOKEN=ghp_secrettoken1234567890abcdefghijklmn\n")
        res = runner.invoke(app, ["diff", "187"])
        assert res.exit_code == 0
        assert "ghp_secrettoken" not in res.output

    def test_pr_diff_error_masked(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr diff masks secrets in error output."""
        answer_gh(
            gh_edge,
            returncode=1,
            stderr="Failed diff token ghp_secrettoken1234567890abcdefghijklmn",
        )
        res = runner.invoke(app, ["diff", "187"])
        assert res.exit_code == 1
        assert "ghp_secrettoken" not in res.output

    def test_pr_close_error_masked(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr close masks secrets in error output."""
        answer_gh(
            gh_edge,
            returncode=1,
            stderr="Failed close token ghp_secrettoken1234567890abcdefghijklmn",
        )
        res = runner.invoke(app, ["close", "187"])
        assert res.exit_code == 1
        assert "ghp_secrettoken" not in res.output

    def test_fallback_create_pr_existing(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """The REST fallback of `pr create` discovers an existing PR and avoids a duplicate POST."""
        mock_existing = json.dumps(
            [
                {
                    "number": 187,
                    "html_url": "https://github.com/dan-petty/devops-cli/pull/187",
                    "base": {"ref": "main"},
                }
            ]
        )
        answer_origin(gh_edge, REPO)
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/test\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout=mock_existing))
        result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY, "--base", "main"])
        lookups = [argv for argv in gh_argv(gh_edge) if argv[:1] == ["api"]]
        assert (result.exit_code, "Pull request #187 already exists" in result.output) == (0, True)
        # Only the query was sent, not a POST.
        assert [argv[1] for argv in lookups] == [
            "repos/example/roadmap/pulls?head=example:feat/test&state=open"
        ]

    def test_fallback_create_pr_paces_its_post_as_a_write(
        self,
        runner: CliRunner,
        gh_edge: ProcessFake,
        clock: ClockFake,
        labels: InMemoryRoadmapStore,
    ) -> None:
        """Through the real `run_gh` with gh's process faked (#1125): the implicit-POST
        `gh api .../pulls -f ...` of the REST fallback is paced as a write, so it waits for the
        minimum interval after the write of `gh pr create` before it, and the lookup between them does
        not."""
        number = labels.seed_issue("feat(pr): a pull request", pull_request=True)
        created = {
            "number": number,
            "html_url": f"https://github.com/example/roadmap/pull/{number}",
        }
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/x\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
        gh_edge.answer(
            mentions("repos/example/roadmap/pulls", "title="),
            ProcessAnswer(stdout=json.dumps(created)),
        )
        gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=NO_CLOSING_ISSUES))
        # A wait happens before the command that follows it: note how many commands had started.
        started_before_long_waits: list[int] = []

        def note_long_wait() -> None:
            if clock.waits[-1] >= DEFAULT_GH_MUTATION_MIN_INTERVAL_SECONDS / 2:
                started_before_long_waits.append(len(gh_edge.calls))

        clock.after_each_sleep(note_long_wait)
        result = runner.invoke(
            app, ["create", "--title", TITLE, "--body", BODY, "--base", "main", "--repo", REPO]
        )
        waited_for = [gh_edge.calls[index].argv for index in started_before_long_waits]
        assert (
            result.exit_code,
            [argv[1:3] for argv in waited_for],
            any("title=" in a for a in waited_for[-1]),
        ) == (0, [("pr", "create"), ("api", "repos/example/roadmap/pulls")], True)

    @pytest.mark.parametrize(
        ("stdout", "said"),
        [
            (
                json.dumps({"html_url": "https://example.com/example/roadmap/pull/9"}),
                "Opened a draft pull request: https://example.com/example/roadmap/pull/9.",
            ),
            ("not json", "Opened a draft pull request into main."),
            ("[]", "Opened a draft pull request into main."),
        ],
        ids=["url", "not-json", "no-url"],
    )
    def test_the_fallback_names_the_draft_by_its_url_or_else_its_base(
        self, runner: CliRunner, gh_edge: ProcessFake, stdout: str, said: str
    ) -> None:
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/x\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
        gh_edge.answer(mentions("title="), ProcessAnswer(stdout=stdout))
        result = runner.invoke(
            app, ["create", "--title", TITLE, "--body", BODY, "--base", "main", "--repo", REPO]
        )
        assert said in result.output

    def test_the_fallback_reports_a_failed_post(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/x\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
        gh_edge.answer(mentions("title="), ProcessAnswer(returncode=1, stderr="HTTP 422"))
        result = runner.invoke(
            app, ["create", "--title", TITLE, "--body", BODY, "--base", "main", "--repo", REPO]
        )
        assert (result.exit_code, "Could not create the pull request" in result.output) == (1, True)

    def test_pr_list_fallback_merged_filter(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """The REST fallback of `pr list` keeps the pull requests with a `merged_at` when the
        state is merged."""
        mock_prs = json.dumps(
            [
                {
                    "number": 1,
                    "title": "PR 1",
                    "merged_at": "2026-09-12T10:00:00Z",
                    "user": {"login": "user1"},
                    "base": {"ref": "main"},
                    "head": {"ref": "feat/1"},
                },
                {
                    "number": 2,
                    "title": "PR 2",
                    "merged_at": None,
                    "user": {"login": "user2"},
                    "base": {"ref": "main"},
                    "head": {"ref": "feat/2"},
                },
            ]
        )
        answer_origin(gh_edge, REPO)
        script_gh(gh_edge, GH_FAILED, ProcessAnswer(stdout=mock_prs))
        result = runner.invoke(app, ["list", "--state", "merged", "--limit", "10"])
        assert (result.exit_code, "PR 1" in result.output, "PR 2" in result.output) == (
            0,
            True,
            False,
        )

    def test_create_pr_fallback_on_nonzero(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr create falls back to the REST API when gh pr create fails."""
        answer_origin(gh_edge, REPO)
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/test\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        existing = [{"number": 5, "html_url": "https://example.com/pull/5", "base": {"ref": ""}}]
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout=json.dumps(existing)))
        result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY])
        assert result.exit_code == 0
        assert "Pull request #5 already exists" in result.output

    def test_create_has_no_option_to_skip_the_draft(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        """devops pr ready is the only way to ready, so create takes no --draft flag at all."""
        result = runner.invoke(app, ["create", "--title", "t", "--draft"])
        assert (result.exit_code, gh_argv(gh_edge)) == (2, [])

    def test_the_fallback_opens_a_draft_into_the_default_branch_it_reads(
        self, runner: CliRunner, gh_edge: ProcessFake, labels: InMemoryRoadmapStore
    ) -> None:
        """Without --base the REST fallback reads the default branch, then posts a draft, and the
        new pull request gets its Status."""
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/x\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        gh_edge.answer(mentions("closingIssuesReferences"), ProcessAnswer(stdout=NO_CLOSING_ISSUES))
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
        gh_edge.answer(
            ["gh", "api", "repos/example/roadmap"],
            ProcessAnswer(stdout='{"default_branch": "trunk"}'),
        )
        number = labels.seed_issue("feat(pr): a pull request", pull_request=True)
        post = {"html_url": f"https://example.com/example/roadmap/pull/{number}", "number": number}
        gh_edge.answer(
            mentions("repos/example/roadmap/pulls", "title="),
            ProcessAnswer(stdout=json.dumps(post)),
        )
        result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY, "--repo", REPO])
        sent = gh_argv(gh_edge)
        posted = next(argv for argv in sent if any("title=" in a for a in argv))
        closing = next(argv for argv in sent if any("closingIssuesReferences" in a for a in argv))
        assert (
            result.exit_code,
            "base=trunk" in posted,
            posted[-2:],
            f"https://example.com/example/roadmap/pull/{number}" in result.output,
            f"number={number}" in closing,
        ) == (0, True, ["-F", "draft=true"], True, True)

    @pytest.mark.parametrize(
        "repository",
        [
            ProcessAnswer(returncode=1, stderr="gh: Server Error (HTTP 500)"),
            ProcessAnswer(stdout="not json"),
            ProcessAnswer(stdout="[]"),
        ],
        ids=["unread", "not-json", "no-object"],
    )
    def test_the_fallback_creates_nothing_when_the_default_branch_is_unread(
        self, runner: CliRunner, gh_edge: ProcessFake, repository: ProcessAnswer
    ) -> None:
        gh_edge.answer(["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/x\n"))
        answer_gh(gh_edge, "pr", "create", returncode=1, stderr="GraphQL error")
        gh_edge.answer(mentions("pulls?head="), ProcessAnswer(stdout="[]"))
        gh_edge.answer(["gh", "api", "repos/example/roadmap"], repository)
        result = runner.invoke(app, ["create", "--title", TITLE, "--body", BODY, "--repo", REPO])
        sent = gh_argv(gh_edge)
        assert (result.exit_code, len(sent), any("title=" in a for argv in sent for a in argv)) == (
            1,
            3,
            False,
        )

    def test_check_readiness_no_repo(self, runner: CliRunner, process_fake: ProcessFake) -> None:
        """devops pr check-readiness fails when repo cannot be resolved."""
        result = runner.invoke(app, ["check-readiness"])
        assert result.exit_code == 1
        assert "Target repository must be in OWNER/REPO format" in result.output

    def test_check_readiness_no_open_pr(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr check-readiness on a branch with no open PR exits 1 with a one-line error."""
        answer_origin(gh_edge, "owner/repo")
        gh_edge.answer(
            ["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/untracked\n")
        )
        answer_gh(gh_edge, returncode=1, stderr="no pull requests found")
        result = runner.invoke(app, ["check-readiness"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "No open pull request found for branch 'feat/untracked'" in result.output
        assert "Traceback" not in result.output

    def test_pr_monitor_no_open_pr(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr monitor on a branch with no open PR exits 1 with a one-line error."""
        answer_origin(gh_edge, "owner/repo")
        gh_edge.answer(
            ["git", "branch", "--show-current"], ProcessAnswer(stdout="feat/untracked\n")
        )
        answer_gh(gh_edge, returncode=1, stderr="no pull requests found")
        result = runner.invoke(app, ["monitor"], catch_exceptions=False)
        assert result.exit_code == 1
        assert "No open pull request found for branch 'feat/untracked'" in result.output
        assert "Traceback" not in result.output

    def test_a_merged_pull_request_prints_merged_with_no_check_count(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        """A pull request merged while the monitor waits is reported as merged, not as ready, and
        no check was read to count (#2530)."""
        answer_gh(
            gh_edge,
            "api",
            "repos/owner/repo/pulls/9",
            stdout=json.dumps({"number": 9, "state": "closed", "merged": True}),
        )
        result = runner.invoke(
            app,
            ["monitor", "9", "--repo", "owner/repo", "--settle-timeout", "0"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "PR #9 is merged." in result.output, result.output
        assert "Checks:" not in result.output, result.output
        assert "READY FOR MERGING" not in result.output, result.output

    def test_a_closed_pull_request_prints_closed_with_no_check_count(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        """A pull request closed without a merge can no longer become ready, so the monitor names
        it closed and exits 2, with no check count and no ready line (#2530)."""
        answer_gh(
            gh_edge,
            "api",
            "repos/owner/repo/pulls/9",
            stdout=json.dumps({"number": 9, "state": "closed", "merged": False}),
        )
        result = runner.invoke(
            app,
            ["monitor", "9", "--repo", "owner/repo", "--settle-timeout", "0"],
            catch_exceptions=False,
        )
        assert result.exit_code == 2, result.output
        assert "PR #9 is closed." in result.output, result.output
        assert "Checks:" not in result.output, result.output
        assert "READY FOR MERGING" not in result.output, result.output

    def test_render_threads_table_masks_secrets(
        self, runner: CliRunner, gh_edge: ProcessFake
    ) -> None:
        """The threads table masks secret tokens in comment bodies."""
        answer_origin(gh_edge, "owner/repo")
        leak = "Leak token: ghp_supersecrettoken1234567890abcdefghijklmn here"
        answer_gh(gh_edge, stdout=_threads_page(_thread("THREAD_SEC_1", ("bot", leak))))
        result = runner.invoke(app, ["threads", "list", "83"])
        assert (
            result.exit_code,
            "ghp_supersecrettoken" in result.output,
            "<masked-github-token>" in result.output,
        ) == (0, False, True)

    def test_pr_checks_fallback_empty_checks(
        self, runner: CliRunner, github_api_and_gh: tuple[GitHubApiFake, ProcessFake]
    ) -> None:
        """The checks fallback renders a table with 'no checks reported' pending when empty."""
        github_api, gh = github_api_and_gh
        fresh_quota()
        github_api.route(
            "GET",
            "/repos/owner/repo/commits/sha12345/check-runs?per_page=100",
            httpx2.Response(
                200, headers={"content-type": "application/json"}, content=b'{"check_runs": []}'
            ),
        )
        answer_origin(gh, "owner/repo")
        script_gh(
            gh,
            GH_FAILED,
            ProcessAnswer(stdout=json.dumps({"head": {"sha": "sha12345"}})),
            ProcessAnswer(
                stdout=json.dumps({"state": "pending", "statuses": [], "total_count": 0})
            ),
        )
        res = runner.invoke(app, ["checks", "184"])
        assert "no checks reported" in res.output
        assert "pending" in res.output

    def test_pr_diff_failure_exit_code(self, runner: CliRunner, gh_edge: ProcessFake) -> None:
        """devops pr diff exits with returncode when gh pr diff fails."""
        answer_gh(gh_edge, returncode=2, stderr="Error fetching diff")
        res = runner.invoke(app, ["diff", "184"])
        assert res.exit_code == 2


def test_a_failed_create_explains_itself(gh_edge: ProcessFake) -> None:
    """`run_gh` captures the CLI's output, so a failure printed nothing at all.

    Three invocations in one session produced no pull request and no message beyond the
    command's own elapsed time; the base branch did not exist and nothing said so.
    """
    answer_gh(gh_edge, returncode=1, stderr="Base ref must be a branch")
    result = CliRunner().invoke(
        app, ["create", "--title", TITLE, "--body", BODY, "--base", "feat/gone"]
    )
    assert (result.exit_code, "feat/gone" in result.output) == (1, True)


def test_a_failed_create_without_a_base_names_the_default_branch(gh_edge: ProcessFake) -> None:
    answer_gh(gh_edge, returncode=1, stderr="GraphQL error")
    result = CliRunner().invoke(app, ["create", "--title", TITLE, "--body", BODY])
    assert (result.exit_code, "against base 'the default branch'" in result.output) == (1, True)


def test_a_failed_create_relays_the_underlying_reason(gh_edge: ProcessFake) -> None:
    """The CLI's own message is the diagnostic; suppressing it hid the cause."""
    answer_gh(gh_edge, returncode=1, stderr="Base ref must be a branch")
    result = CliRunner().invoke(
        app, ["create", "--title", TITLE, "--body", BODY, "--base", "feat/gone"]
    )
    assert "Base ref must be a branch" in result.output


def test_an_unpushed_branch_gets_the_remedy(gh_edge: ProcessFake) -> None:
    """The most common cause has a one-line fix; naming it saves a round trip."""
    answer_gh(gh_edge, returncode=1, stderr="aborted: you must first push the current branch")
    result = CliRunner().invoke(app, ["create", "--title", TITLE, "--body", BODY, "--base", "main"])
    assert "git push -u origin HEAD" in result.output
