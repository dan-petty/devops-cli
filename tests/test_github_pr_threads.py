"""Unit tests for GitHub PR review thread management and GraphQL resolution."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devops_cli.commands.pr import app as pr_app
from devops_cli.config.constants import CONST_PR_THREAD_FILED_MARKER
from devops_cli.config.defaults import DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_threads import (
    ReviewComment,
    ReviewThread,
    ThreadResolutionResult,
    list_pr_review_threads,
    reply_pr_review_thread,
    resolve_pr_review_thread,
    unresolve_pr_review_thread,
)
from devops_cli.github.review_thread_issues import thread_issue_body
from devops_cli.roadmap.memory_store import InMemoryRoadmapStore
from devops_cli.roadmap.store import IssueRecord

SAMPLE_GRAPHQL_RESPONSE = {
    "data": {
        "repository": {
            "pullRequest": {
                "reviewThreads": {
                    "nodes": [
                        {
                            "id": "PRRT_thread_1",
                            "isResolved": False,
                            "path": "src/devops_cli/security.py",
                            "line": 42,
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "PRRC_comment_1",
                                        "body": "Please add bounded timeout",
                                        "author": {"login": "security-reviewer"},
                                        "createdAt": "2026-09-09T10:00:00Z",
                                    }
                                ]
                            },
                        },
                        {
                            "id": "PRRT_thread_2",
                            "isResolved": True,
                            "path": "src/devops_cli/main.py",
                            "line": 10,
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "PRRC_comment_2",
                                        "body": "Nice cleanup!",
                                        "author": {"login": "copilot"},
                                        "createdAt": "2026-09-09T10:05:00Z",
                                    }
                                ]
                            },
                        },
                    ]
                }
            }
        }
    }
}


def test_list_pr_review_threads_all() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps(SAMPLE_GRAPHQL_RESPONSE)

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_res):
        threads = list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=83)
        assert len(threads) == 2
        assert threads[0].id == "PRRT_thread_1"
        assert threads[0].is_resolved is False
        assert threads[0].path == "src/devops_cli/security.py"
        assert threads[0].line == 42
        assert len(threads[0].comments) == 1
        assert threads[0].comments[0].author == "security-reviewer"

        assert threads[1].id == "PRRT_thread_2"
        assert threads[1].is_resolved is True


def test_list_pr_review_threads_unresolved_only() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps(SAMPLE_GRAPHQL_RESPONSE)

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_res):
        threads = list_pr_review_threads(
            owner="dan-petty",
            repo="devops-cli",
            pr_number=83,
            unresolved_only=True,
        )
        assert len(threads) == 1
        assert threads[0].id == "PRRT_thread_1"
        assert threads[0].is_resolved is False


def test_reply_pr_review_thread_success() -> None:
    reply_resp = {
        "data": {
            "addPullRequestReviewThreadReply": {
                "comment": {
                    "id": "PRRC_reply_99",
                    "body": "Remediated with bounded timeout in commit abc1234",
                    "author": {"login": "dan-petty"},
                    "createdAt": "2026-09-09T11:00:00Z",
                }
            }
        }
    }
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps(reply_resp)

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_res):
        comment = reply_pr_review_thread(
            thread_id="PRRT_thread_1",
            body="Remediated with bounded timeout in commit abc1234",
        )
        assert isinstance(comment, ReviewComment)
        assert comment.id == "PRRC_reply_99"
        assert "Remediated with bounded timeout" in comment.body
        assert comment.author == "dan-petty"


def test_resolve_pr_review_thread_success() -> None:
    resolve_resp = {
        "data": {
            "resolveReviewThread": {
                "thread": {
                    "id": "PRRT_thread_1",
                    "isResolved": True,
                }
            }
        }
    }
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps(resolve_resp)

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_res):
        result = resolve_pr_review_thread("PRRT_thread_1")
        assert isinstance(result, ThreadResolutionResult)
        assert result.thread_id == "PRRT_thread_1"
        assert result.is_resolved is True
        assert result.success is True


def test_unresolve_pr_review_thread_success() -> None:
    unresolve_resp = {
        "data": {
            "unresolveReviewThread": {
                "thread": {
                    "id": "PRRT_thread_1",
                    "isResolved": False,
                }
            }
        }
    }
    mock_res = MagicMock()
    mock_res.returncode = 0
    mock_res.stdout = json.dumps(unresolve_resp)

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_res):
        result = unresolve_pr_review_thread("PRRT_thread_1")
        assert isinstance(result, ThreadResolutionResult)
        assert result.thread_id == "PRRT_thread_1"
        assert result.is_resolved is False
        assert result.success is True


def test_pr_threads_error_handling() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stderr = "GraphQL error: Thread not found"

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_res):
        with pytest.raises(GitHubOperationError, match="GraphQL error"):
            resolve_pr_review_thread("INVALID_ID")


def test_list_pr_review_threads_pagination() -> None:
    """Verify list_pr_review_threads walks through paginated GraphQL pages."""
    page_1 = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": True, "endCursor": "cursor_1"},
                        "nodes": [
                            {
                                "id": "PRRT_1",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 1,
                                "comments": {"nodes": []},
                            }
                        ],
                    }
                }
            }
        }
    }
    page_2 = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                        "nodes": [
                            {
                                "id": "PRRT_2",
                                "isResolved": True,
                                "path": "b.py",
                                "line": 2,
                                "comments": {"nodes": []},
                            }
                        ],
                    }
                }
            }
        }
    }

    mock_res_1 = MagicMock(returncode=0, stdout=json.dumps(page_1))
    mock_res_2 = MagicMock(returncode=0, stdout=json.dumps(page_2))

    with patch("devops_cli.github.pr_threads.run_gh", side_effect=[mock_res_1, mock_res_2]):
        threads = list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=86)
        assert len(threads) == 2
        assert threads[0].id == "PRRT_1"
        assert threads[1].id == "PRRT_2"


def test_list_pr_review_threads_graphql_rate_limit_honors_quota_no_rest_fallback() -> None:
    """Verify list_pr_review_threads honors rate limits and never falls back to REST."""
    mock_graphql_err = MagicMock()
    mock_graphql_err.returncode = 1
    mock_graphql_err.stderr = "GraphQL: API rate limit already exceeded for user ID 7726889."
    mock_graphql_err.stdout = ""

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_graphql_err) as mock_gh:
        with pytest.raises(GitHubOperationError, match="rate limit"):
            list_pr_review_threads(
                owner="dan-petty",
                repo="devops-cli",
                pr_number=83,
                unresolved_only=False,
            )
        assert mock_gh.call_count == 1
        call_args = mock_gh.call_args[0][0]
        assert "graphql" in call_args
        assert not any("pulls" in arg for arg in call_args)


def test_list_pr_review_threads_graphql_generic_error_propagates() -> None:
    """Verify non-rate-limit GraphQL errors are raised without attempting REST fallback."""
    mock_graphql_err = MagicMock()
    mock_graphql_err.returncode = 1
    mock_graphql_err.stderr = "Could not resolve to a Repository with the name 'unknown'."
    mock_graphql_err.stdout = ""

    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_graphql_err):
        with pytest.raises(GitHubOperationError, match="Could not resolve to a Repository"):
            list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=83)


def test_resolve_all_pr_review_threads_only_replied() -> None:
    """Verify resolve_all_pr_review_threads only targets threads with replies when only_replied=True."""
    from devops_cli.github.pr_threads import (
        ReviewComment,
        ReviewThread,
        ThreadResolutionResult,
        resolve_all_pr_review_threads,
    )

    t1 = ReviewThread(
        id="PRRT_1",
        is_resolved=False,
        comments=[
            ReviewComment(id="c1", author="reviewer", body="Issue"),
            ReviewComment(id="c2", author="dev", body="Fixed in commit abc"),
        ],
    )
    t2 = ReviewThread(
        id="PRRT_2",
        is_resolved=False,
        comments=[ReviewComment(id="c3", author="reviewer", body="Unaddressed issue")],
    )

    with (
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[t1, t2]),
        patch(
            "devops_cli.github.pr_threads.resolve_pr_review_thread",
            return_value=ThreadResolutionResult(thread_id="PRRT_1", is_resolved=True, success=True),
        ) as mock_resolve,
    ):
        results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200, only_replied=True)
        assert (len(results), results[0].thread_id, results[0].is_resolved) == (1, "PRRT_1", True)
        mock_resolve.assert_called_once_with("PRRT_1")


def test_resolve_all_pr_review_threads_all() -> None:
    """Verify resolve_all_pr_review_threads resolves all threads when only_replied=False."""
    from devops_cli.github.pr_threads import (
        ReviewComment,
        ReviewThread,
        ThreadResolutionResult,
        resolve_all_pr_review_threads,
    )

    t1 = ReviewThread(
        id="PRRT_1",
        is_resolved=False,
        comments=[
            ReviewComment(id="c1", author="reviewer", body="Comment 1"),
            ReviewComment(id="c2", author="dev", body="Reply"),
        ],
    )
    t2 = ReviewThread(
        id="PRRT_2",
        is_resolved=False,
        comments=[ReviewComment(id="c3", author="reviewer", body="Comment 2")],
    )

    def side_effect(tid: str) -> ThreadResolutionResult:
        return ThreadResolutionResult(thread_id=tid, is_resolved=True, success=True)

    with (
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[t1, t2]),
        patch(
            "devops_cli.github.pr_threads.resolve_pr_review_thread", side_effect=side_effect
        ) as mock_resolve,
    ):
        results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200, only_replied=False)
        assert (len(results), mock_resolve.call_count) == (2, 2)


def test_resolve_all_pr_review_threads_handles_individual_errors() -> None:
    """Verify individual thread resolution errors are logged and captured without failing the batch."""
    from devops_cli.github.pr_threads import (
        ReviewComment,
        ReviewThread,
        ThreadResolutionResult,
        resolve_all_pr_review_threads,
    )

    t1 = ReviewThread(
        id="PRRT_1",
        is_resolved=False,
        comments=[
            ReviewComment(id="c1", author="reviewer", body="Comment 1"),
            ReviewComment(id="c2", author="dev", body="Reply"),
        ],
    )
    t2 = ReviewThread(
        id="PRRT_2",
        is_resolved=False,
        comments=[
            ReviewComment(id="c3", author="reviewer", body="Comment 2"),
            ReviewComment(id="c4", author="dev", body="Reply"),
        ],
    )

    def side_effect(tid: str) -> ThreadResolutionResult:
        if tid == "PRRT_1":
            raise GitHubOperationError("GraphQL timeout")
        return ThreadResolutionResult(thread_id=tid, is_resolved=True, success=True)

    with (
        patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[t1, t2]),
        patch("devops_cli.github.pr_threads.resolve_pr_review_thread", side_effect=side_effect),
    ):
        results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200, only_replied=True)
        assert (
            len(results),
            results[0].thread_id,
            results[0].success,
            results[0].is_resolved,
            results[1].thread_id,
            results[1].success,
            results[1].is_resolved,
        ) == (2, "PRRT_1", False, False, "PRRT_2", True, True)


def test_resolve_all_pr_review_threads_empty() -> None:
    """Verify resolve_all_pr_review_threads returns empty list when no unresolved threads exist."""
    from devops_cli.github.pr_threads import resolve_all_pr_review_threads

    with patch("devops_cli.github.pr_threads.list_pr_review_threads", return_value=[]):
        results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200)
        assert results == []


def test_has_non_opener_reply_predicates() -> None:
    """Verify has_non_opener_reply correctly distinguishes opener follow-ups from true replies."""
    from devops_cli.github.pr_threads import ReviewComment, ReviewThread, has_non_opener_reply

    empty_thread = ReviewThread(id="t0", comments=[])
    single_comment = ReviewThread(
        id="t1",
        comments=[ReviewComment(id="c1", author="reviewer", body="Fix this")],
    )
    # Probe case: reviewer's own follow-up comment
    probe_case = ReviewThread(
        id="t2",
        comments=[
            ReviewComment(id="c1", author="reviewer", body="Fix this"),
            ReviewComment(id="c2", author="reviewer", body="Still not fixed."),
        ],
    )
    case_insensitive_probe = ReviewThread(
        id="t3",
        comments=[
            ReviewComment(id="c1", author="Reviewer", body="Fix this"),
            ReviewComment(id="c2", author=" reviewer ", body="Still not fixed."),
        ],
    )
    three_same_author = ReviewThread(
        id="t4",
        comments=[
            ReviewComment(id="c1", author="copilot", body="Comment 1"),
            ReviewComment(id="c2", author="copilot", body="Comment 2"),
            ReviewComment(id="c3", author="copilot", body="Comment 3"),
        ],
    )
    valid_reply = ReviewThread(
        id="t5",
        comments=[
            ReviewComment(id="c1", author="reviewer", body="Fix this"),
            ReviewComment(id="c2", author="developer", body="Addressed in commit abc"),
        ],
    )
    follow_up_then_reply = ReviewThread(
        id="t6",
        comments=[
            ReviewComment(id="c1", author="reviewer", body="Fix this"),
            ReviewComment(id="c2", author="reviewer", body="Ping"),
            ReviewComment(id="c3", author="developer", body="Addressed now"),
        ],
    )

    predicates = (
        has_non_opener_reply(empty_thread),
        has_non_opener_reply(single_comment),
        has_non_opener_reply(probe_case),
        has_non_opener_reply(case_insensitive_probe),
        has_non_opener_reply(three_same_author),
        has_non_opener_reply(valid_reply),
        has_non_opener_reply(follow_up_then_reply),
    )
    assert predicates == (False, False, False, False, False, True, True)


def test_resolve_all_pr_review_threads_probe_case_skipped() -> None:
    """Verify resolve_all_pr_review_threads skips threads where reviewer only replied to self."""
    from devops_cli.github.pr_threads import (
        ReviewComment,
        ReviewThread,
        ThreadResolutionResult,
        resolve_all_pr_review_threads,
    )

    probe_thread = ReviewThread(
        id="PRRT_PROBE",
        is_resolved=False,
        comments=[
            ReviewComment(id="c1", author="codeql", body="Security alert"),
            ReviewComment(id="c2", author="codeql", body="Still not fixed."),
        ],
    )
    valid_thread = ReviewThread(
        id="PRRT_VALID",
        is_resolved=False,
        comments=[
            ReviewComment(id="c3", author="reviewer", body="Issue found"),
            ReviewComment(id="c4", author="author", body="Resolved in fix commit"),
        ],
    )

    with (
        patch(
            "devops_cli.github.pr_threads.list_pr_review_threads",
            return_value=[probe_thread, valid_thread],
        ),
        patch(
            "devops_cli.github.pr_threads.resolve_pr_review_thread",
            return_value=ThreadResolutionResult(
                thread_id="PRRT_VALID", is_resolved=True, success=True
            ),
        ) as mock_resolve,
    ):
        results = resolve_all_pr_review_threads("owner", "repo", 42, only_replied=True)
        assert (len(results), results[0].thread_id) == (1, "PRRT_VALID")
        mock_resolve.assert_called_once_with("PRRT_VALID")


def test_get_pr_review_thread_success() -> None:
    """Verify get_pr_review_thread parses GraphQL node into ReviewThread."""
    from devops_cli.github.pr_threads import get_pr_review_thread

    resp = {
        "data": {
            "node": {
                "id": "PRRT_node_1",
                "isResolved": False,
                "path": "src/cli.py",
                "line": 42,
                "comments": {
                    "nodes": [
                        {
                            "id": "PRRC_1",
                            "body": "Check bounds",
                            "author": {"login": "reviewer"},
                            "createdAt": "2026-09-01T00:00:00Z",
                        },
                        {
                            "id": "PRRC_2",
                            "body": "Fixed in 99beef",
                            "author": {"login": "dev"},
                            "createdAt": "2026-09-01T01:00:00Z",
                        },
                    ]
                },
            }
        }
    }
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(resp))
    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_proc):
        thread = get_pr_review_thread("PRRT_node_1")
        assert (
            thread.id,
            thread.is_resolved,
            thread.path,
            thread.line,
            len(thread.comments),
            thread.comments[0].author,
            thread.comments[1].author,
        ) == ("PRRT_node_1", False, "src/cli.py", 42, 2, "reviewer", "dev")


def test_get_pr_review_thread_not_found() -> None:
    """Verify get_pr_review_thread raises GitHubOperationError when node is missing."""
    from devops_cli.github.pr_threads import get_pr_review_thread

    resp = {"data": {"node": None}}
    mock_proc = MagicMock(returncode=0, stdout=json.dumps(resp))
    with patch("devops_cli.github.pr_threads.run_gh", return_value=mock_proc):
        with pytest.raises(GitHubOperationError, match="Review thread PRRT_missing not found"):
            get_pr_review_thread("PRRT_missing")


def test_resolve_all_paces_each_resolve_as_a_write_and_the_listing_as_a_read() -> None:
    """Through the real `run_gh` with gh's process stubbed (#1125): the thread listing acquires
    as a read and each of the three resolves as a write, so `pr threads resolve-all` sends its
    resolves at least the write interval apart."""
    import subprocess

    from devops_cli.github.pr_threads import resolve_all_pr_review_threads
    from devops_cli.github.rate_limiter import GitHubRateLimiter

    replied = {
        "nodes": [
            {"id": "C1", "body": "fix", "author": {"login": "reviewer"}, "createdAt": ""},
            {"id": "C2", "body": "done", "author": {"login": "author"}, "createdAt": ""},
        ]
    }
    threads = [
        {"id": f"PRRT_{n}", "isResolved": False, "path": "a.py", "line": n, "comments": replied}
        for n in (1, 2, 3)
    ]
    listing = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {"pageInfo": {"hasNextPage": False}, "nodes": threads}
                }
            }
        }
    }
    resolved = {"data": {"resolveReviewThread": {"thread": {"isResolved": True}}}}

    def gh(cmd: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
        reply = resolved if any("resolveReviewThread" in arg for arg in cmd) else listing
        return subprocess.CompletedProcess(cmd, 0, json.dumps(reply), "")

    with (
        patch("devops_cli.github.rate_limiter._burst_protected_subprocess", side_effect=gh),
        patch.object(GitHubRateLimiter, "acquire", autospec=True, return_value=0.0) as acquire,
    ):
        results = resolve_all_pr_review_threads("o", "r", 7)
    assert (
        [result.success for result in results],
        [call.kwargs["is_mutation"] for call in acquire.call_args_list],
    ) == ([True, True, True], [False, True, True, True])


# ── Remaining threads filed as follow-up issues (#1345) ─────────────────────────────────────────
#
# The pull request read is REST and the thread reads and writes are GraphQL; every reply below is
# in the shape GitHub's documented schema gives the query or mutation that asks for it:
# `PullRequestReviewThread` (`id`, `isResolved`, `path`, `line`, `comments`) and
# `PullRequestReviewComment` (`id`, `body`, `author { login }`, `createdAt`, `url`), with Copilot
# as the GraphQL login `copilot-pull-request-reviewer`.

_REPO = "dan-petty/devops-cli"
_PULL = 1283
_COPILOT_GRAPHQL = "copilot-pull-request-reviewer"


def _comment(
    comment_id: str, body: str, *, author: str = _COPILOT_GRAPHQL, discussion: int
) -> dict[str, Any]:
    return {
        "id": comment_id,
        "body": body,
        "author": {"login": author},
        "createdAt": "2026-10-07T12:43:24Z",
        "url": f"https://github.com/{_REPO}/pull/{_PULL}#discussion_r{discussion}",
    }


def _thread(
    thread_id: str, path: str, line: int | None, *comments: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": thread_id,
        "isResolved": False,
        "path": path,
        "line": line,
        "comments": {"nodes": list(comments)},
    }


_THREAD_A = _thread(
    "PRRT_kwDOThbRVc5Ak1aA",
    "src/devops_cli/github/pr_monitor.py",
    412,
    _comment("PRRC_kwDOThbRVc6Ak1aA", "Rename `state` to `copilot_state`.", discussion=2412345678),
)
_THREAD_B = _thread(
    "PRRT_kwDOThbRVc5Ak1bB",
    "src/devops_cli/commands/pr.py",
    2890,
    _comment("PRRC_kwDOThbRVc6Ak1bB", "This loop reads the board twice.", discussion=2412345679),
    _comment(
        "PRRC_kwDOThbRVc6Ak1bC",
        "Agreed, after the release.",
        author="maintainer",
        discussion=2412345680,
    ),
)


def _release_pull(head: str = "release/v0.2.37", base: str = "main") -> dict[str, Any]:
    repo = {"full_name": _REPO, "default_branch": "main"}
    sides = {"head": {"ref": head, "repo": repo}, "base": {"ref": base, "repo": repo}}
    return {"number": _PULL, "state": "open", "merged": False, **sides}


class _ThreadsGitHub:
    """`run_gh` answering the pull request read and the review thread GraphQL calls, recording
    every call in `calls` and every write, in order, in `events`."""

    def __init__(
        self,
        threads: list[dict[str, Any]],
        events: list[tuple[Any, ...]],
        pull: dict[str, Any] | None = None,
    ) -> None:
        self.calls: list[list[str]] = []
        self._threads = threads
        self._events = events
        self._pull = pull or _release_pull()

    def __call__(self, args: list[str], **_: object) -> MagicMock:
        argv = [str(arg) for arg in args]
        self.calls.append(argv)
        if argv[-1] == f"repos/{_REPO}/pulls/{_PULL}":
            return MagicMock(returncode=0, stdout=json.dumps(self._pull), stderr="")
        flags = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in ("-f", "-F")]
        fields = dict(flag.split("=", 1) for flag in flags)
        answer = self._answer(fields.get("query", ""), fields)
        return MagicMock(returncode=0, stdout=json.dumps(answer), stderr="")

    def _answer(self, query: str, fields: dict[str, str]) -> dict[str, Any]:
        if query.startswith("query GetReviewThreads"):
            page = {"pageInfo": {"hasNextPage": False, "endCursor": "Y3Vyc29yOnYyOpHOBUf6iA=="}}
            threads = {"reviewThreads": {**page, "nodes": self._threads}}
            budget = {
                "limit": 5000,
                "remaining": 4990,
                "cost": 1,
                "resetAt": "2026-10-19T01:00:00Z",
            }
            return {"data": {"rateLimit": budget, "repository": {"pullRequest": threads}}}
        if query.startswith("mutation AddReply"):
            self._events.append(("reply", fields["threadId"], fields["body"]))
            reply = _comment(
                "PRRC_kwDOThbRVc6Ak1zZ", fields["body"], author="maintainer", discussion=1
            )
            return {"data": {"addPullRequestReviewThreadReply": {"comment": reply}}}
        if query.startswith("mutation ResolveThread"):
            self._events.append(("resolve", fields["threadId"]))
            thread = {"id": fields["threadId"], "isResolved": True}
            return {"data": {"resolveReviewThread": {"thread": thread}}}
        return {"errors": [{"message": f"unscripted: {query[:40]}"}]}


@pytest.fixture
def filing_events(
    roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> list[tuple[Any, ...]]:
    """Every write of a filing run, in order: each issue the roadmap store opens, then the
    replies and resolves the GraphQL stand-in records."""
    events: list[tuple[Any, ...]] = []
    create = roadmap_store.create_issue

    def recorded(title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        issue = create(title, body, labels=labels)
        events.append(("issue", issue.number))
        return issue

    monkeypatch.setattr(roadmap_store, "create_issue", recorded)
    return events


def _file_issues(gh: _ThreadsGitHub, *args: str) -> Any:
    with (
        patch("devops_cli.github.pr_threads.run_gh", side_effect=gh),
        patch("devops_cli.github.pr_monitor.run_gh", side_effect=gh),
    ):
        return CliRunner().invoke(
            pr_app, ["threads", "file-issues", str(_PULL), "--repo", _REPO, *args]
        )


def test_each_unresolved_thread_is_filed_then_replied_to_then_resolved(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    """Each thread becomes one issue, with no milestone and labelled source/agent, before its
    reply names the issue and the thread is resolved, one thread after the other."""
    result = _file_issues(_ThreadsGitHub([_THREAD_A, _THREAD_B], filing_events), "--confirm")
    issues = roadmap_store.issues()
    assert (
        result.exit_code,
        [event[:2] for event in filing_events],
        "Filed as #1" in filing_events[1][2],
        "Filed as #2" in filing_events[4][2],
        issues[0].title,
        [(issue.labels, issue.release) for issue in issues],
    ) == (
        0,
        [
            ("issue", 1),
            ("reply", "PRRT_kwDOThbRVc5Ak1aA"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
            ("issue", 2),
            ("reply", "PRRT_kwDOThbRVc5Ak1bB"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1bB"),
        ],
        True,
        True,
        "chore(review): follow up src/devops_cli/github/pr_monitor.py:412 from #1283",
        [(("source/agent",), None), (("source/agent",), None)],
    )


def test_an_issue_holds_the_fenced_thread_its_location_and_its_link(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    _file_issues(_ThreadsGitHub([_THREAD_B], filing_events), "--confirm")
    body = roadmap_store.issues()[0].body
    fenced = body.split("```")[1]
    assert (
        "This loop reads the board twice." in fenced,
        "Agreed, after the release." in fenced,
        "src/devops_cli/commands/pr.py:2890" in body,
        f"https://github.com/{_REPO}/pull/{_PULL}#discussion_r2412345679" in body,
    ) == (True, True, True, True)


def test_a_mention_and_an_issue_reference_stay_inside_a_fence_longer_than_any_in_the_text(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    """Neither `@someone` nor `#12` may notify or link from the issue, and a fence in the
    comment cannot close the one around it."""
    text = "@someone see #12 first:\n```python\nx = 1\n```"
    thread = _thread("PRRT_kwDOThbRVc5Ak1cC", "src/a.py", 3, _comment("PRRC_c", text, discussion=7))
    _file_issues(_ThreadsGitHub([thread], filing_events), "--confirm")
    before, fenced, after = roadmap_store.issues()[0].body.split("````\n", 2)
    outside = before + after
    reference = re.compile(r"#12\b")
    assert (
        "@someone" in fenced,
        bool(reference.search(fenced)),
        "@someone" in outside,
        bool(reference.search(outside)),
    ) == (True, True, False, False)


def test_a_kept_thread_is_left_untouched(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    """`--keep` leaves open the thread of a regression the release fixes before it merges."""
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], filing_events)
    result = _file_issues(gh, "--confirm", "--keep", "PRRT_kwDOThbRVc5Ak1bB")
    assert (
        result.exit_code,
        [event[:2] for event in filing_events],
        len(roadmap_store.issues()),
    ) == (
        0,
        [("issue", 1), ("reply", "PRRT_kwDOThbRVc5Ak1aA"), ("resolve", "PRRT_kwDOThbRVc5Ak1aA")],
        1,
    )


def test_without_confirm_the_threads_are_read_and_nothing_is_written(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], filing_events)
    result = _file_issues(gh)
    title = "chore(review): follow up src/devops_cli/commands/pr.py:2890 from #1283"
    assert (result.exit_code, filing_events, roadmap_store.issues(), title in result.output) == (
        0,
        [],
        [],
        True,
    )


def test_dry_run_makes_no_request_and_lists_the_requests(
    roadmap_store: InMemoryRoadmapStore,
    roadmap_store_repos: list[str],
    filing_events: list[tuple[Any, ...]],
) -> None:
    """`--dry-run` reads nothing either (#412): it lists the reads, then the issue, reply and
    resolve each thread would get."""
    gh = _ThreadsGitHub([_THREAD_A], filing_events)
    result = _file_issues(gh, "--confirm", "--dry-run")
    assert (
        result.exit_code,
        gh.calls,
        roadmap_store_repos,
        f"repos/{_REPO}/issues" in result.output,
        "labels[]=source/agent" in result.output,
        "mutation AddReply" in result.output,
        "mutation ResolveThread" in result.output,
    ) == (0, [], [], True, True, True, True)


def test_a_thread_already_filed_is_resolved_and_not_filed_again(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    """A run that stopped after the reply left the thread open; the rerun reads the marker in
    that reply and only resolves it."""
    earlier = f"Filed as #7, a follow-up issue.\n\n{CONST_PR_THREAD_FILED_MARKER}"
    replied = _comment("PRRC_kwDOThbRVc6Ak1aZ", earlier, author="maintainer", discussion=8)
    filed = {**_THREAD_A, "comments": {"nodes": [*_THREAD_A["comments"]["nodes"], replied]}}
    result = _file_issues(_ThreadsGitHub([filed, _THREAD_B], filing_events), "--confirm")
    assert (result.exit_code, [event[:2] for event in filing_events]) == (
        0,
        [
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
            ("issue", 1),
            ("reply", "PRRT_kwDOThbRVc5Ak1bB"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1bB"),
        ],
    )


def test_a_failed_issue_stops_the_run_before_its_reply_and_resolve(
    roadmap_store: InMemoryRoadmapStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[tuple[Any, ...]] = []

    def refused(title: str, body: str, *, labels: Sequence[str] = ()) -> IssueRecord:
        raise GitHubOperationError("Could not open the issue (exit 1): HTTP 502")

    monkeypatch.setattr(roadmap_store, "create_issue", refused)
    result = _file_issues(_ThreadsGitHub([_THREAD_A, _THREAD_B], events), "--confirm")
    assert (result.exit_code, events, "HTTP 502" in result.output) == (1, [], True)


def test_a_pull_request_that_is_not_the_release_pull_request_is_refused(
    roadmap_store: InMemoryRoadmapStore, filing_events: list[tuple[Any, ...]]
) -> None:
    """The stop rule is the release pull request's: an item pull request's threads are its
    author's to answer."""
    pull = _release_pull(head="feat/1345-review-threads", base="release/v0.2.37")
    gh = _ThreadsGitHub([_THREAD_A], filing_events, pull=pull)
    result = _file_issues(gh, "--confirm")
    queries = [call for call in gh.calls if "graphql" in call]
    assert (
        result.exit_code,
        queries,
        filing_events,
        "not the release pull request" in result.output,
    ) == (1, [], [], True)


def test_a_long_thread_is_cut_and_says_so() -> None:
    text = "x" * (DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS + 50)
    comment = {"id": "PRRC_long", "body": text, "author": _COPILOT_GRAPHQL}
    thread = ReviewThread.model_validate(
        {"id": "PRRT_long", "path": "src/a.py", "line": 1, "comments": [comment]}
    )
    body = thread_issue_body(_PULL, thread)
    assert (body.count("x") <= DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS, "cut" in body) == (True, True)
