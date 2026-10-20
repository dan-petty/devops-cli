"""Unit tests for GitHub PR review thread management and GraphQL resolution."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    from graphql.language import (
        SelectionSetNode,
    )
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
from devops_cli.github.session import get_github_session
from devops_cli.roadmap import store as roadmap_module
from devops_cli.roadmap.github_store import GitHubRoadmapStore
from tests.support.fakes.github import (
    API,
    GitHubApiFake,
    RunnerSession,
    github_json,
    next_page,
)
from tests.support.paths import FIXTURES

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
# The pull request read is REST and the thread reads and writes are GraphQL. The stand-in holds
# each object in the shape GitHub's documented schema gives it, `PullRequestReviewThread` (`id`,
# `isResolved`, `isOutdated`, `path`, `line`, `originalLine`, `comments`) and
# `PullRequestReviewComment` (`id`, `body`, `author { login }`, null for a deleted account,
# `createdAt`, `url`), with Copilot as the GraphQL login `copilot-pull-request-reviewer`, and
# answers each query with only the fields it selects, as GitHub does. A GraphQL error makes gh
# exit 1 and name it on stderr.
#
# Each run opens the GitHub roadmap store, as the command does. Its gh commands, the issue it
# opens included, go to the stand-in, which answers with an issue in the shape GitHub's REST API
# returns, from a recorded one. Its issue listing goes through the GitHub session (#983):
# `RunnerSession` asks the stand-in for it, and the tests of paging, a bad page and the dry run
# read it through the real session over the `github_api` fake.

_REPO = "dan-petty/devops-cli"
_PULL = 1283
_COPILOT_GRAPHQL = "copilot-pull-request-reviewer"
_VIEWER = "maintainer"
_FIRST_PAGE_END = "Y3Vyc29yOnYyOpHOBUf6iA=="
_ISSUES_LISTING = f"/repos/{_REPO}/issues?state=all&per_page=100"
_FIRST_NEW_ISSUE = 1701
_RECORDED_ISSUE = json.loads(
    (FIXTURES / "roadmap" / "issues-open.json").read_text(encoding="utf-8")
)[1]


def _comment(
    comment_id: str, body: str, *, author: str | None = _COPILOT_GRAPHQL, discussion: int
) -> dict[str, Any]:
    return {
        "id": comment_id,
        "body": body,
        "author": None if author is None else {"login": author},
        "createdAt": "2026-10-07T12:43:24Z",
        "url": f"https://github.com/{_REPO}/pull/{_PULL}#discussion_r{discussion}",
    }


def _thread(
    thread_id: str,
    path: str,
    line: int | None,
    *comments: dict[str, Any],
    original_line: int | None = None,
    outdated: bool = False,
    more_after: str | None = None,
) -> dict[str, Any]:
    """A thread node; `more_after` is the cursor after its first page of comments when GitHub
    holds more of them."""
    page = {"hasNextPage": more_after is not None, "endCursor": more_after or _FIRST_PAGE_END}
    return {
        "id": thread_id,
        "isResolved": False,
        "isOutdated": outdated,
        "path": path,
        "line": line,
        "originalLine": line if original_line is None else original_line,
        "comments": {"pageInfo": page, "nodes": list(comments)},
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
        "PRRC_kwDOThbRVc6Ak1bC", "Agreed, after the release.", author=_VIEWER, discussion=2412345680
    ),
)


def _release_pull(head: str = "release/v0.2.37", base: str = "main") -> dict[str, Any]:
    repo = {"full_name": _REPO, "default_branch": "main"}
    sides = {"head": {"ref": head, "repo": repo}, "base": {"ref": base, "repo": repo}}
    return {"number": _PULL, "state": "open", "merged": False, **sides}


def _rest_issue(
    number: int, title: str, body: str, *, labels: Sequence[str] = (), state: str = "open"
) -> dict[str, Any]:
    """An issue as GitHub's REST API lists it and answers its creation, from a recorded one."""
    return {
        **_RECORDED_ISSUE,
        "url": f"https://api.github.com/repos/{_REPO}/issues/{number}",
        "html_url": f"https://github.com/{_REPO}/issues/{number}",
        "id": 5670191474 + number,
        "number": number,
        "title": title,
        "body": body,
        "labels": [{"name": label, "color": "ededed"} for label in labels],
        "state": state,
        "state_reason": None if state == "open" else "completed",
        "milestone": None,
    }


def _linking(thread: dict[str, Any]) -> str:
    """A follow-up issue's body for `thread`: it ends a line with the link to its first comment."""
    first = thread["comments"]["nodes"][0]
    return f"Quoted thread.\n\n{thread['path']}:{thread['line']}, {first['url']}\n"


def _gh_reply(payload: Any) -> MagicMock:
    return MagicMock(returncode=0, stdout=json.dumps(payload), stderr="")


def _selected(value: Any, selection: SelectionSetNode | None) -> Any:
    """`value` cut to the fields `selection` asks for, as GitHub answers a query: a field the
    query does not ask for is left out, and one the stand-in lacks fails the test."""
    if selection is None or value is None:
        return value
    if isinstance(value, list):
        return [_selected(item, selection) for item in value]
    from graphql.language import FieldNode, InlineFragmentNode

    answer: dict[str, Any] = {}
    for node in selection.selections:
        if isinstance(node, InlineFragmentNode):
            answer.update(_selected(value, node.selection_set))
            continue
        assert isinstance(node, FieldNode)
        name = node.name.value
        assert name in value, f"the stand-in holds no {name} for the query to select"
        answer[name] = _selected(value[name], node.selection_set)
    return answer


class _ThreadsGitHub:
    """`run_gh` answering the pull request read, the review thread GraphQL calls and the roadmap
    store's gh commands and issue listing, recording every call in `calls`, every write, in
    order, in `events`, each issue it opened in `opened` and each store a run opened in
    `stores`. The listing holds `issues` and every issue opened since; `later_comments` holds the
    comments past a thread's first page; a reply in a thread of `failing_replies` fails as
    GitHub's GraphQL rate limit fails it, and with `failing_issue` opening an issue fails."""

    def __init__(
        self,
        threads: list[dict[str, Any]],
        events: list[tuple[Any, ...]],
        *,
        pull: dict[str, Any] | None = None,
        issues: Sequence[dict[str, Any]] = (),
        later_comments: dict[str, list[dict[str, Any]]] | None = None,
        failing_replies: frozenset[str] = frozenset(),
        failing_issue: bool = False,
    ) -> None:
        self.calls: list[list[str]] = []
        self.opened: list[dict[str, Any]] = []
        self.stores: list[str] = []
        self._threads = threads
        self._events = events
        self._pull = pull or _release_pull()
        self._issues = list(issues)
        self._later = later_comments or {}
        self._failing = failing_replies
        self._failing_issue = failing_issue

    def __call__(self, args: list[str], **_: object) -> MagicMock:
        argv = [str(arg) for arg in args]
        self.calls.append(argv)
        if argv[-1] == f"repos/{_REPO}/pulls/{_PULL}":
            return _gh_reply(self._pull)
        if argv == [f"{API}{_ISSUES_LISTING}"]:
            return _gh_reply(self._issues)
        if argv[:4] == ["api", "-X", "POST", f"repos/{_REPO}/issues"]:
            return self._open_issue(argv[4:])
        flags = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg in ("-f", "-F")]
        fields = dict(flag.split("=", 1) for flag in flags)
        from graphql import parse
        from graphql.language import OperationDefinitionNode

        operation = next(
            definition
            for definition in parse(fields["query"]).definitions
            if isinstance(definition, OperationDefinitionNode)
        )
        name = operation.name.value if operation.name else ""
        if name == "AddReply" and fields["threadId"] in self._failing:
            limited = "API rate limit exceeded for user ID 1."
            error = {"errors": [{"type": "RATE_LIMITED", "message": limited}]}
            return MagicMock(returncode=1, stdout=json.dumps(error), stderr=f"gh: {limited}")
        return _gh_reply({"data": _selected(self._data(name, fields), operation.selection_set)})

    def _open_issue(self, flags: list[str]) -> MagicMock:
        fields = [flag.split("=", 1) for flag in flags[1::2]]
        if self._failing_issue:
            return MagicMock(returncode=1, stdout="", stderr="gh: Server Error (HTTP 502)")
        title = next(value for name, value in fields if name == "title")
        body = next(value for name, value in fields if name == "body")
        labels = [value for name, value in fields if name == "labels[]"]
        number = _FIRST_NEW_ISSUE + len(self.opened)
        issue = _rest_issue(number, title, body, labels=labels)
        self.opened.append(issue)
        self._issues.append(issue)
        self._events.append(("issue", number))
        return _gh_reply(issue)

    def _data(self, operation: str, fields: dict[str, str]) -> dict[str, Any]:
        if operation == "GetReviewThreads":
            page = {"pageInfo": {"hasNextPage": False, "endCursor": _FIRST_PAGE_END}}
            threads = {"reviewThreads": {**page, "nodes": self._threads}}
            budget = {
                "limit": 5000,
                "remaining": 4990,
                "cost": 1,
                "resetAt": "2026-10-19T01:00:00Z",
            }
            return {"rateLimit": budget, "repository": {"pullRequest": threads}}
        if operation == "GetThreadComments":
            page = {"hasNextPage": False, "endCursor": "Y3Vyc29yOnYyOpHOBUf6iB=="}
            nodes = self._later[fields["threadId"]]
            return {"node": {"comments": {"pageInfo": page, "nodes": nodes}}}
        if operation == "Viewer":
            return {"viewer": {"login": _VIEWER}}
        if operation == "AddReply":
            self._events.append(("reply", fields["threadId"], fields["body"]))
            reply = _comment("PRRC_kwDOThbRVc6Ak1zZ", fields["body"], author=_VIEWER, discussion=1)
            return {"addPullRequestReviewThreadReply": {"comment": reply}}
        if operation == "ResolveThread":
            self._events.append(("resolve", fields["threadId"]))
            return {
                "resolveReviewThread": {"thread": {"id": fields["threadId"], "isResolved": True}}
            }
        raise AssertionError(f"unscripted GraphQL operation {operation!r}")


def _file_issues(gh: _ThreadsGitHub, *args: str, over_github: bool = False) -> Any:
    """Run file-issues with `gh` answering every gh command. Each roadmap store the run opens is
    the GitHub store, its gh commands sent to `gh` and its issue listing read through
    `RunnerSession` from `gh`, or, `over_github`, through the process's GitHub session from the
    `github_api` fake."""

    def open_store(repo: str, **_: Any) -> GitHubRoadmapStore:
        gh.stores.append(repo)
        session = get_github_session() if over_github else RunnerSession(gh)
        return GitHubRoadmapStore(repo, runner=gh, session=session)

    with (
        patch("devops_cli.github.pr_threads.run_gh", side_effect=gh),
        patch("devops_cli.github.pr_monitor.run_gh", side_effect=gh),
        patch.object(roadmap_module, "get_roadmap_store", open_store),
    ):
        from devops_cli.commands.pr import app as pr_app

        return CliRunner().invoke(
            pr_app, ["threads", "file-issues", str(_PULL), "--repo", _REPO, *args]
        )


def _writes(events: list[tuple[Any, ...]]) -> list[tuple[Any, ...]]:
    return [event[:2] for event in events]


def _with_reply(thread: dict[str, Any], reply: dict[str, Any]) -> dict[str, Any]:
    comments = thread["comments"]
    return {**thread, "comments": {**comments, "nodes": [*comments["nodes"], reply]}}


def _labels(issue: dict[str, Any]) -> list[str]:
    return [label["name"] for label in issue["labels"]]


def test_each_unresolved_thread_is_filed_then_replied_to_then_resolved() -> None:
    """Each thread becomes one issue, with no milestone and labelled source/agent since Copilot
    started it, before its reply names the issue and the thread is resolved, one thread after
    the other."""
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], events)
    result = _file_issues(gh, "--confirm")
    assert (
        result.exit_code,
        _writes(events),
        "Filed as #1701" in events[1][2],
        "Filed as #1702" in events[4][2],
        gh.opened[0]["title"],
        [(_labels(issue), issue["milestone"]) for issue in gh.opened],
        gh.stores,
    ) == (
        0,
        [
            ("issue", 1701),
            ("reply", "PRRT_kwDOThbRVc5Ak1aA"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
            ("issue", 1702),
            ("reply", "PRRT_kwDOThbRVc5Ak1bB"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1bB"),
        ],
        True,
        True,
        "chore(review): follow up src/devops_cli/github/pr_monitor.py:412 from #1283",
        [(["source/agent"], None), (["source/agent"], None)],
        [_REPO],
    )


def test_an_issue_holds_the_fenced_thread_its_location_and_its_link() -> None:
    gh = _ThreadsGitHub([_THREAD_B], [])
    _file_issues(gh, "--confirm")
    body = gh.opened[0]["body"]
    fenced = body.split("```")[1]
    assert (
        "This loop reads the board twice." in fenced,
        "Agreed, after the release." in fenced,
        "src/devops_cli/commands/pr.py:2890" in body,
        f"https://github.com/{_REPO}/pull/{_PULL}#discussion_r2412345679" in body,
    ) == (True, True, True, True)


def test_a_mention_and_an_issue_reference_stay_inside_a_fence_longer_than_any_in_the_text() -> None:
    """Neither `@someone` nor `#12` may notify or link from the issue, and a fence in the
    comment cannot close the one around it."""
    text = "@someone see #12 first:\n```python\nx = 1\n```"
    thread = _thread("PRRT_kwDOThbRVc5Ak1cC", "src/a.py", 3, _comment("PRRC_c", text, discussion=7))
    gh = _ThreadsGitHub([thread], [])
    _file_issues(gh, "--confirm")
    before, fenced, after = gh.opened[0]["body"].split("````\n", 2)
    outside = before + after
    reference = re.compile(r"#12\b")
    assert (
        "@someone" in fenced,
        bool(reference.search(fenced)),
        "@someone" in outside,
        bool(reference.search(outside)),
    ) == (True, True, False, False)


def test_a_kept_thread_is_left_untouched() -> None:
    """`--keep` leaves open the thread of a regression the release fixes before it merges."""
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], events)
    result = _file_issues(gh, "--confirm", "--keep", "PRRT_kwDOThbRVc5Ak1bB")
    assert (result.exit_code, _writes(events), len(gh.opened)) == (
        0,
        [
            ("issue", 1701),
            ("reply", "PRRT_kwDOThbRVc5Ak1aA"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
        ],
        1,
    )


@pytest.mark.parametrize("confirm", [(), ("--confirm",)], ids=["preview", "confirm"])
def test_a_keep_id_that_names_no_unresolved_thread_is_refused_before_any_write(
    confirm: tuple[str, ...],
) -> None:
    """A mistyped `--keep` would leave the regression thread to be filed and resolved, and the
    release pull request would show no unresolved thread, so it stops the run."""
    typo = "PRRT_kwDOThbRVc5Ak1bb"
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], events)
    result = _file_issues(gh, *confirm, "--keep", typo)
    assert (result.exit_code, events, gh.opened, typo in result.output) == (1, [], [], True)


def test_the_preview_keeps_a_kept_thread() -> None:
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], [])
    result = _file_issues(gh, "--keep", "PRRT_kwDOThbRVc5Ak1bB")
    assert (
        result.exit_code,
        "Kept PRRT_kwDOThbRVc5Ak1bB" in result.output,
        "Would file PRRT_kwDOThbRVc5Ak1bB" in result.output,
        "Would file PRRT_kwDOThbRVc5Ak1aA" in result.output,
    ) == (0, True, False, True)


def test_without_confirm_the_threads_are_read_and_nothing_is_written() -> None:
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], events)
    result = _file_issues(gh)
    title = "chore(review): follow up src/devops_cli/commands/pr.py:2890 from #1283"
    assert (result.exit_code, events, gh.opened, title in result.output) == (0, [], [], True)


def test_dry_run_makes_no_request_and_lists_the_requests(github_api: GitHubApiFake) -> None:
    """`--dry-run` reads nothing either (#412), through gh or the GitHub session: it lists the
    reads, the issue listing as the session's GET, then the issue, reply and resolve each
    thread would get."""
    gh = _ThreadsGitHub([_THREAD_A], [])
    result = _file_issues(gh, "--confirm", "--dry-run", over_github=True)
    output = "".join(result.output.split())
    assert (
        result.exit_code,
        gh.calls,
        gh.stores,
        github_api.requested,
        "queryViewer" in output,
        "queryGetThreadComments" in output,
        f"GET'{API}{_ISSUES_LISTING}'" in output,
        "labels[]=source/agent" in output,
        "mutationAddReply" in output,
        "mutationResolveThread" in output,
    ) == (0, [], [], [], True, True, True, True, True, True)


def test_a_thread_the_viewer_already_filed_is_resolved_and_not_filed_again() -> None:
    """A run that stopped after the reply left the thread open; the rerun reads the marker line
    in the reply the same account wrote, and only resolves the thread, naming its issue."""
    marker = CONST_PR_THREAD_FILED_MARKER.format(issue=7)
    earlier = _comment(
        "PRRC_kwDOThbRVc6Ak1aZ", f"Filed as #7.\n\n{marker}", author=_VIEWER, discussion=8
    )
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_with_reply(_THREAD_A, earlier), _THREAD_B], events)
    result = _file_issues(gh, "--confirm")
    assert (result.exit_code, _writes(events), "#7" in result.output) == (
        0,
        [
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
            ("issue", 1701),
            ("reply", "PRRT_kwDOThbRVc5Ak1bB"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1bB"),
        ],
        True,
    )


def test_a_marker_reply_past_the_first_page_of_comments_is_read() -> None:
    marker = CONST_PR_THREAD_FILED_MARKER.format(issue=7)
    earlier = _comment(
        "PRRC_kwDOThbRVc6Ak1aZ", f"Filed as #7.\n\n{marker}", author=_VIEWER, discussion=8
    )
    first_page = _thread(
        "PRRT_kwDOThbRVc5Ak1aA",
        "src/devops_cli/github/pr_monitor.py",
        412,
        *_THREAD_A["comments"]["nodes"],
        more_after="Y3Vyc29yOnYyOpHOBUf6iC==",
    )
    events: list[tuple[Any, ...]] = []
    later = {"PRRT_kwDOThbRVc5Ak1aA": [earlier]}
    result = _file_issues(_ThreadsGitHub([first_page], events, later_comments=later), "--confirm")
    assert (result.exit_code, _writes(events)) == (0, [("resolve", "PRRT_kwDOThbRVc5Ak1aA")])


def test_a_copilot_suggestion_quoting_the_marker_leaves_its_thread_to_be_filed() -> None:
    """The first comment never counts: a suggestion on the line that defines the marker quotes
    it whole."""
    marker = CONST_PR_THREAD_FILED_MARKER.format(issue=3)
    suggestion = f"Name the issue in the marker:\n```suggestion\n{marker}\n```"
    thread = _thread(
        "PRRT_kwDOThbRVc5Ak1dD",
        "src/devops_cli/config/constants.py",
        1593,
        _comment("PRRC_kwDOThbRVc6Ak1dD", suggestion, discussion=99),
    )
    events: list[tuple[Any, ...]] = []
    result = _file_issues(_ThreadsGitHub([thread], events), "--confirm")
    assert (result.exit_code, _writes(events)) == (
        0,
        [
            ("issue", 1701),
            ("reply", "PRRT_kwDOThbRVc5Ak1dD"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1dD"),
        ],
    )


def test_a_marker_reply_from_another_login_does_not_count() -> None:
    marker = CONST_PR_THREAD_FILED_MARKER.format(issue=3)
    other = _comment(
        "PRRC_kwDOThbRVc6Ak1aY", f"Filed as #3.\n\n{marker}", author="someone", discussion=9
    )
    events: list[tuple[Any, ...]] = []
    result = _file_issues(_ThreadsGitHub([_with_reply(_THREAD_A, other)], events), "--confirm")
    assert (result.exit_code, _writes(events)) == (
        0,
        [
            ("issue", 1701),
            ("reply", "PRRT_kwDOThbRVc5Ak1aA"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
        ],
    )


def test_a_rerun_after_a_failed_reply_opens_no_second_issue() -> None:
    """The issue is open when the reply fails: the failed run names it, and the rerun finds it
    in the store's issue listing by the thread's link in its body, replies naming it and
    resolves the thread."""
    events: list[tuple[Any, ...]] = []
    failing = frozenset({"PRRT_kwDOThbRVc5Ak1aA"})
    stopped = _ThreadsGitHub([_THREAD_A], events, failing_replies=failing)
    first = _file_issues(stopped, "--confirm")
    rerun = _file_issues(_ThreadsGitHub([_THREAD_A], events, issues=stopped.opened), "--confirm")
    assert (
        first.exit_code,
        "#1701" in first.output,
        rerun.exit_code,
        _writes(events),
        "Filed as #1701" in events[1][2],
    ) == (
        1,
        True,
        0,
        [
            ("issue", 1701),
            ("reply", "PRRT_kwDOThbRVc5Ak1aA"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
        ],
        True,
    )


def test_the_issues_are_listed_once_a_run_through_the_github_session(
    github_api: GitHubApiFake,
) -> None:
    """Two threads whose issues a run opened before their replies failed: the rerun reads the
    issue listing once, through the GitHub session, and names in each reply the open issue
    that ends a line with that thread's link, not one whose link only begins with it nor a
    closed one."""
    link_a = _THREAD_A["comments"]["nodes"][0]["url"]
    listing = [
        _rest_issue(1690, "decoy", f"Quoted.\n\nsrc/a.py:1, {link_a}1\n"),
        _rest_issue(1701, "follow up A", _linking(_THREAD_A)),
        _rest_issue(1695, "closed", _linking(_THREAD_B), state="closed"),
        _rest_issue(1702, "follow up B", _linking(_THREAD_B)),
    ]
    github_api.route("GET", _ISSUES_LISTING, github_json(listing))
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], events)
    result = _file_issues(gh, "--confirm", over_github=True)
    named = [event[2].split(",")[0] for event in events if event[0] == "reply"]
    assert (result.exit_code, _writes(events), named, gh.opened, github_api.requested) == (
        0,
        [
            ("reply", "PRRT_kwDOThbRVc5Ak1aA"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1aA"),
            ("reply", "PRRT_kwDOThbRVc5Ak1bB"),
            ("resolve", "PRRT_kwDOThbRVc5Ak1bB"),
        ],
        ["Filed as #1701", "Filed as #1702"],
        [],
        [f"GET {API}{_ISSUES_LISTING}"],
    )


def test_a_bad_page_of_the_issue_listing_stops_the_run_before_any_write(
    github_api: GitHubApiFake,
) -> None:
    """A page that holds no list is never taken as the end of the listing, since the issue that
    links the thread may be on it: the run stops before it opens, replies or resolves anything,
    and requests no page after it."""
    later = f"{_ISSUES_LISTING}&page=2"
    full = github_json([_RECORDED_ISSUE] * 100, headers=next_page(later))
    github_api.route("GET", _ISSUES_LISTING, full)
    github_api.route("GET", later, github_json({"message": "Moved Permanently"}))
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A], events)
    result = _file_issues(gh, "--confirm", over_github=True)
    assert (result.exit_code, events, gh.opened, len(github_api.sent)) == (1, [], [], 2)


def test_a_failure_part_way_reports_the_threads_already_filed() -> None:
    failing = frozenset({"PRRT_kwDOThbRVc5Ak1bB"})
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], [], failing_replies=failing)
    result = _file_issues(gh, "--confirm")
    output = " ".join(result.output.split())
    assert (
        result.exit_code,
        "Filed PRRT_kwDOThbRVc5Ak1aA (src/devops_cli/github/pr_monitor.py:412) as #1701" in output,
        "#1702" in output,
    ) == (1, True, True)


def test_a_failed_issue_stops_the_run_before_its_reply_and_resolve() -> None:
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A, _THREAD_B], events, failing_issue=True)
    result = _file_issues(gh, "--confirm")
    assert (result.exit_code, events, "HTTP 502" in result.output) == (1, [], True)


def test_a_pull_request_that_is_not_the_release_pull_request_is_refused() -> None:
    """The stop rule is the release pull request's: an item pull request's threads are its
    author's to answer."""
    pull = _release_pull(head="feat/1345-review-threads", base="release/v0.2.37")
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A], events, pull=pull)
    result = _file_issues(gh, "--confirm")
    queries = [call for call in gh.calls if "graphql" in call]
    assert (
        result.exit_code,
        queries,
        events,
        "not the release pull request" in result.output,
    ) == (1, [], [], True)


@pytest.mark.parametrize(("merged", "shown"), [(True, "merged"), (False, "closed")])
def test_a_release_pull_request_that_is_not_open_is_refused_before_its_threads_are_read(
    merged: bool, shown: str
) -> None:
    """The previous release's pull request still runs release/vX.Y.Z into main."""
    pull = {**_release_pull("release/v0.2.36"), "state": "closed", "merged": merged}
    events: list[tuple[Any, ...]] = []
    gh = _ThreadsGitHub([_THREAD_A], events, pull=pull)
    result = _file_issues(gh, "--confirm")
    queries = [call for call in gh.calls if "graphql" in call]
    output = " ".join(result.output.split())
    assert (result.exit_code, queries, events, f"is {shown}, not open" in output) == (
        1,
        [],
        [],
        True,
    )


def test_a_thread_a_person_started_is_filed_without_source_agent() -> None:
    """`source/agent` says a model wrote the text; a person's thread is theirs."""
    person = _thread(
        "PRRT_kwDOThbRVc5Ak1eE",
        "src/a.py",
        5,
        _comment("PRRC_kwDOThbRVc6Ak1eE", "This needs a test.", author=_VIEWER, discussion=11),
    )
    gh = _ThreadsGitHub([_THREAD_A, person], [])
    _file_issues(gh, "--confirm")
    assert [_labels(issue) for issue in gh.opened] == [["source/agent"], []]


def test_a_deleted_author_is_named_ghost() -> None:
    """GitHub gives a deleted account's comment a null author and shows it as ghost."""
    thread = _thread(
        "PRRT_kwDOThbRVc5Ak1fF",
        "src/a.py",
        8,
        _comment("PRRC_f", "Old note.", author=None, discussion=12),
    )
    gh = _ThreadsGitHub([thread], [])
    _file_issues(gh, "--confirm")
    assert "ghost:\nOld note." in gh.opened[0]["body"]


def test_a_thread_a_push_moved_off_the_diff_is_placed_by_its_original_line() -> None:
    thread = _thread(
        "PRRT_kwDOThbRVc5Ak1gG",
        "src/devops_cli/github/pr_monitor.py",
        None,
        _comment("PRRC_g", "Guard the None.", discussion=13),
        original_line=40,
        outdated=True,
    )
    gh = _ThreadsGitHub([thread], [])
    _file_issues(gh, "--confirm")
    expected = "chore(review): follow up src/devops_cli/github/pr_monitor.py:40 from #1283"
    assert gh.opened[0]["title"] == expected


def test_two_threads_on_a_whole_file_get_titles_that_tell_them_apart() -> None:
    """A thread on a file, not a line, has neither `line` nor `originalLine`; its first
    comment's id tells it from another on the same file."""
    first = _thread(
        "PRRT_kwDOThbRVc5Ak1hH",
        "docs/a.md",
        None,
        _comment("PRRC_h1", "Split this.", discussion=14),
    )
    second = _thread(
        "PRRT_kwDOThbRVc5Ak1iI", "docs/a.md", None, _comment("PRRC_i1", "Retitle.", discussion=15)
    )
    gh = _ThreadsGitHub([first, second], [])
    _file_issues(gh, "--confirm")
    titles = [issue["title"] for issue in gh.opened]
    assert (len(set(titles)), "PRRC_h1" in titles[0], "PRRC_i1" in titles[1]) == (2, True, True)


def test_the_preview_marks_an_outdated_thread() -> None:
    """A later push has probably dealt with an outdated thread, so the preview says so."""
    thread = _thread(
        "PRRT_kwDOThbRVc5Ak1jJ",
        "src/a.py",
        None,
        _comment("PRRC_j", "Off by one.", discussion=16),
        original_line=9,
        outdated=True,
    )
    result = _file_issues(_ThreadsGitHub([thread, _THREAD_A], []))
    output = " ".join(result.output.split())
    marked = ["outdated" in line for line in output.split("Would file")[1:]]
    assert (result.exit_code, marked) == (0, [True, False])


def test_a_long_thread_is_cut_and_says_so() -> None:
    text = "x" * (DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS + 50)
    comment = {"id": "PRRC_long", "body": text, "author": _COPILOT_GRAPHQL}
    thread = ReviewThread.model_validate(
        {"id": "PRRT_long", "path": "src/a.py", "line": 1, "comments": [comment]}
    )
    body = thread_issue_body(_PULL, thread)
    assert (body.count("x") <= DEFAULT_PR_THREAD_ISSUE_TEXT_CHARS, "cut" in body) == (True, True)
