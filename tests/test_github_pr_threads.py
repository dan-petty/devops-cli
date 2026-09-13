"""Unit tests for GitHub PR review thread management and GraphQL resolution."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_threads import (
    ReviewComment,
    ThreadResolutionResult,
    list_pr_review_threads,
    reply_pr_review_thread,
    resolve_pr_review_thread,
    unresolve_pr_review_thread,
)

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

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_res):
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

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_res):
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

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_res):
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

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_res):
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

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_res):
        result = unresolve_pr_review_thread("PRRT_thread_1")
        assert isinstance(result, ThreadResolutionResult)
        assert result.thread_id == "PRRT_thread_1"
        assert result.is_resolved is False
        assert result.success is True


def test_pr_threads_error_handling() -> None:
    mock_res = MagicMock()
    mock_res.returncode = 1
    mock_res.stderr = "GraphQL error: Thread not found"

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_res):
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

    with patch("devops_cli.github.pr_threads.run_subprocess", side_effect=[mock_res_1, mock_res_2]):
        threads = list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=86)
        assert len(threads) == 2
        assert threads[0].id == "PRRT_1"
        assert threads[1].id == "PRRT_2"


def test_list_pr_review_threads_graphql_rate_limit_fallback_to_rest() -> None:
    """Verify list_pr_review_threads falls back to REST when GraphQL hits rate limits."""
    mock_graphql_err = MagicMock()
    mock_graphql_err.returncode = 1
    mock_graphql_err.stderr = "GraphQL: API rate limit already exceeded for user ID 7726889."
    mock_graphql_err.stdout = ""

    rest_comments = [
        {
            "id": 101,
            "node_id": "PRRC_node_101",
            "in_reply_to_id": None,
            "body": "Root comment on security",
            "user": {"login": "security-reviewer"},
            "path": "src/devops_cli/security.py",
            "line": 42,
            "created_at": "2026-09-09T10:00:00Z",
        },
        {
            "id": 102,
            "node_id": "PRRC_node_102",
            "in_reply_to_id": 101,
            "body": "Addressed with bounded timeout",
            "user": {"login": "dan-petty"},
            "path": "src/devops_cli/security.py",
            "line": 42,
            "created_at": "2026-09-09T10:05:00Z",
        },
        {
            "id": 201,
            "node_id": "PRRC_node_201",
            "in_reply_to_id": None,
            "body": "Independent comment",
            "user": {"login": "copilot"},
            "path": "src/devops_cli/main.py",
            "line": 15,
            "created_at": "2026-09-09T10:10:00Z",
        },
    ]
    mock_rest_res = MagicMock()
    mock_rest_res.returncode = 0
    mock_rest_res.stdout = json.dumps(rest_comments)
    mock_rest_res.stderr = ""

    with patch(
        "devops_cli.github.pr_threads.run_subprocess", side_effect=[mock_graphql_err, mock_rest_res]
    ):
        threads = list_pr_review_threads(
            owner="dan-petty",
            repo="devops-cli",
            pr_number=83,
            unresolved_only=False,
        )
        assert len(threads) == 2
        # Verify thread 1 contains both root comment and reply
        assert threads[0].id == "PRRC_node_101"
        assert threads[0].path == "src/devops_cli/security.py"
        assert threads[0].line == 42
        assert len(threads[0].comments) == 2
        assert threads[0].comments[0].id == "101"
        assert threads[0].comments[0].author == "security-reviewer"
        assert threads[0].comments[1].id == "102"
        assert threads[0].comments[1].author == "dan-petty"

        # Verify thread 2
        assert threads[1].id == "PRRC_node_201"
        assert threads[1].path == "src/devops_cli/main.py"
        assert len(threads[1].comments) == 1


def test_list_pr_review_threads_graphql_generic_error_propagates() -> None:
    """Verify non-rate-limit GraphQL errors are raised without attempting REST fallback."""
    mock_graphql_err = MagicMock()
    mock_graphql_err.returncode = 1
    mock_graphql_err.stderr = "Could not resolve to a Repository with the name 'unknown'."
    mock_graphql_err.stdout = ""

    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_graphql_err):
        with pytest.raises(GitHubOperationError, match="Could not resolve to a Repository"):
            list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=83)


def test_fetch_review_threads_rest_empty() -> None:
    """Verify fetch_review_threads_rest returns empty list when no comments exist."""
    from devops_cli.github.pr_threads import fetch_review_threads_rest

    mock_rest = MagicMock(returncode=0, stdout="[]", stderr="")
    with patch("devops_cli.github.pr_threads.run_subprocess", return_value=mock_rest):
        threads = fetch_review_threads_rest(owner="dan-petty", repo="devops-cli", pr_number=83)
        assert threads == []
