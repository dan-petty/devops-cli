"""Unit tests for GitHub PR review thread management and GraphQL resolution."""

from __future__ import annotations

import json
import time

import pytest

from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.pr_threads import (
    ReviewComment,
    ReviewThread,
    ThreadResolutionResult,
    get_pr_review_thread,
    has_non_opener_reply,
    list_pr_review_threads,
    reply_pr_review_thread,
    resolve_all_pr_review_threads,
    resolve_pr_review_thread,
    unresolve_pr_review_thread,
)
from devops_cli.github.request_classifier import is_write_gh_command
from tests.support.fakes.process import ProcessAnswer, ProcessCall, ProcessFake


def _rate_limit_payload() -> str:
    """A /rate_limit answer with a live quota so `run_gh` refreshes without a real gh."""
    return json.dumps(
        {
            "resources": {
                name: {"limit": 5000, "used": 0, "remaining": 4990, "reset": int(time.time()) + 600}
                for name in ("core", "graphql", "search")
            }
        }
    )


def _is_listing(call: ProcessCall) -> bool:
    """The review-thread listing query, as opposed to a later comment page or a rate-limit read."""
    return any("GetReviewThreads" in arg for arg in call.argv)


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
                                        "body": "Ensure rate limit margin is checked before decrementing quota",
                                        "author": {"login": "security-reviewer"},
                                        "createdAt": "2026-09-09T10:00:00Z",
                                        "url": "https://github.com/dan-petty/devops-cli/pull/83#discussion_r1",
                                    }
                                ]
                            },
                        },
                        {
                            "id": "PRRT_thread_2",
                            "isResolved": True,
                            "path": "src/devops_cli/runner.py",
                            "line": 105,
                            "comments": {
                                "nodes": [
                                    {
                                        "id": "PRRC_comment_2",
                                        "body": "Approved pattern",
                                        "author": {"login": "dan-petty"},
                                        "createdAt": "2026-09-09T10:30:00Z",
                                        "url": "https://github.com/dan-petty/devops-cli/pull/83#discussion_r2",
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


def test_list_pr_review_threads_returns_all_threads(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        _is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(SAMPLE_GRAPHQL_RESPONSE))
    )

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


def test_list_pr_review_threads_filters_unresolved_threads(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        _is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(SAMPLE_GRAPHQL_RESPONSE))
    )

    threads = list_pr_review_threads(
        owner="dan-petty",
        repo="devops-cli",
        pr_number=83,
        unresolved_only=True,
    )
    assert len(threads) == 1
    assert threads[0].id == "PRRT_thread_1"
    assert threads[0].is_resolved is False


def test_reply_pr_review_thread_returns_posted_comment(process_fake: ProcessFake) -> None:
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
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("addPullRequestReviewThreadReply" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(reply_resp)),
    )

    comment = reply_pr_review_thread(
        thread_id="PRRT_thread_1",
        body="Remediated with bounded timeout in commit abc1234",
    )
    assert isinstance(comment, ReviewComment)
    assert comment.id == "PRRC_reply_99"
    assert "Remediated with bounded timeout" in comment.body
    assert comment.author == "dan-petty"


def test_resolve_pr_review_thread_marks_thread_resolved(process_fake: ProcessFake) -> None:
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
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("resolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resolve_resp)),
    )

    result = resolve_pr_review_thread("PRRT_thread_1")
    assert isinstance(result, ThreadResolutionResult)
    assert result.thread_id == "PRRT_thread_1"
    assert result.is_resolved is True
    assert result.success is True


def test_unresolve_pr_review_thread_marks_thread_unresolved(process_fake: ProcessFake) -> None:
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
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("unresolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(unresolve_resp)),
    )

    result = unresolve_pr_review_thread("PRRT_thread_1")
    assert isinstance(result, ThreadResolutionResult)
    assert result.thread_id == "PRRT_thread_1"
    assert result.is_resolved is False
    assert result.success is True


def test_resolve_pr_review_thread_raises_when_gh_fails(process_fake: ProcessFake) -> None:
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("resolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=1, stderr="GraphQL error: Thread not found"),
    )

    with pytest.raises(GitHubOperationError, match="GraphQL error"):
        resolve_pr_review_thread("INVALID_ID")


def test_list_pr_review_threads_walks_paginated_pages(process_fake: ProcessFake) -> None:
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

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(page_1)))
    process_fake.answer(
        lambda call: any("cursor=cursor_1" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(page_2)),
    )

    threads = list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=86)
    assert len(threads) == 2
    assert threads[0].id == "PRRT_1"
    assert threads[1].id == "PRRT_2"


def test_list_pr_review_threads_graphql_rate_limit_honors_quota_no_rest_fallback(
    process_fake: ProcessFake,
) -> None:
    """Verify list_pr_review_threads honors rate limits and never falls back to REST."""
    graphql_err_body = {
        "errors": [{"message": "API rate limit already exceeded for user ID 7726889."}]
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        _is_listing,
        ProcessAnswer(returncode=0, stdout=json.dumps(graphql_err_body)),
    )

    with pytest.raises(GitHubOperationError, match="rate limit"):
        list_pr_review_threads(
            owner="dan-petty",
            repo="devops-cli",
            pr_number=83,
            unresolved_only=False,
        )

    listing_calls = [call for call in process_fake.calls if _is_listing(call)]
    assert len(listing_calls) == 1
    assert not any(any("pulls" in arg for arg in call.argv) for call in process_fake.calls)


def test_list_pr_review_threads_graphql_generic_error_propagates(
    process_fake: ProcessFake,
) -> None:
    """Verify non-rate-limit GraphQL errors are raised without attempting REST fallback."""
    graphql_err_body = {
        "errors": [{"message": "Could not resolve to a Repository with the name 'unknown'."}]
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        _is_listing,
        ProcessAnswer(returncode=0, stdout=json.dumps(graphql_err_body)),
    )

    with pytest.raises(GitHubOperationError, match="Could not resolve to a Repository"):
        list_pr_review_threads(owner="dan-petty", repo="devops-cli", pr_number=83)


def test_resolve_all_pr_review_threads_only_replied(process_fake: ProcessFake) -> None:
    """Verify resolve_all_pr_review_threads only targets threads with replies when only_replied=True."""
    listing_body = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {
                                "id": "PRRT_1",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 1,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c1",
                                            "author": {"login": "reviewer"},
                                            "body": "Issue",
                                        },
                                        {
                                            "id": "c2",
                                            "author": {"login": "dev"},
                                            "body": "Fixed in commit abc",
                                        },
                                    ]
                                },
                            },
                            {
                                "id": "PRRT_2",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 2,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c3",
                                            "author": {"login": "reviewer"},
                                            "body": "Unaddressed issue",
                                        },
                                    ]
                                },
                            },
                        ],
                    }
                }
            }
        }
    }
    resolved_body = {
        "data": {"resolveReviewThread": {"thread": {"id": "PRRT_1", "isResolved": True}}}
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing_body)))
    process_fake.answer(
        lambda call: any("resolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resolved_body)),
    )

    results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200, only_replied=True)
    assert (len(results), results[0].thread_id, results[0].is_resolved) == (1, "PRRT_1", True)

    resolve_calls = [
        call
        for call in process_fake.calls
        if any("resolveReviewThread" in arg for arg in call.argv)
    ]
    assert len(resolve_calls) == 1
    assert any("PRRT_1" in arg for arg in resolve_calls[0].argv)


def test_resolve_all_pr_review_threads_all(process_fake: ProcessFake) -> None:
    """Verify resolve_all_pr_review_threads resolves all threads when only_replied=False."""
    listing_body = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {
                                "id": "PRRT_1",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 1,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c1",
                                            "author": {"login": "reviewer"},
                                            "body": "Comment 1",
                                        },
                                        {"id": "c2", "author": {"login": "dev"}, "body": "Reply"},
                                    ]
                                },
                            },
                            {
                                "id": "PRRT_2",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 2,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c3",
                                            "author": {"login": "reviewer"},
                                            "body": "Comment 2",
                                        },
                                    ]
                                },
                            },
                        ],
                    }
                }
            }
        }
    }
    resolved_body = {
        "data": {"resolveReviewThread": {"thread": {"id": "PRRT_1", "isResolved": True}}}
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing_body)))
    process_fake.answer(
        lambda call: any("resolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resolved_body)),
    )

    results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200, only_replied=False)
    resolve_calls = [
        call
        for call in process_fake.calls
        if any("resolveReviewThread" in arg for arg in call.argv)
    ]
    assert (len(results), len(resolve_calls)) == (2, 2)


def test_resolve_all_pr_review_threads_handles_individual_errors(
    process_fake: ProcessFake,
) -> None:
    """Verify individual thread resolution errors are logged and captured without failing the batch."""
    listing_body = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {
                                "id": "PRRT_1",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 1,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c1",
                                            "author": {"login": "reviewer"},
                                            "body": "Comment 1",
                                        },
                                        {"id": "c2", "author": {"login": "dev"}, "body": "Reply"},
                                    ]
                                },
                            },
                            {
                                "id": "PRRT_2",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 2,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c3",
                                            "author": {"login": "reviewer"},
                                            "body": "Comment 2",
                                        },
                                        {"id": "c4", "author": {"login": "dev"}, "body": "Reply"},
                                    ]
                                },
                            },
                        ],
                    }
                }
            }
        }
    }
    resolved_body = {
        "data": {"resolveReviewThread": {"thread": {"id": "PRRT_2", "isResolved": True}}}
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing_body)))
    process_fake.answer(
        lambda call: (
            any("resolveReviewThread" in arg for arg in call.argv)
            and any("threadId=PRRT_2" in arg for arg in call.argv)
        ),
        ProcessAnswer(returncode=0, stdout=json.dumps(resolved_body)),
    )
    process_fake.answer(
        lambda call: (
            any("resolveReviewThread" in arg for arg in call.argv)
            and any("threadId=PRRT_1" in arg for arg in call.argv)
        ),
        ProcessAnswer(returncode=1, stderr="GraphQL timeout"),
    )

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


def test_resolve_all_pr_review_threads_empty(process_fake: ProcessFake) -> None:
    """Verify resolve_all_pr_review_threads returns empty list when no unresolved threads exist."""
    listing_body = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [],
                    }
                }
            }
        }
    }
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing_body)))

    results = resolve_all_pr_review_threads("dan-petty", "devops-cli", 200)
    assert results == []


def test_has_non_opener_reply_predicates() -> None:
    """Verify has_non_opener_reply correctly distinguishes opener follow-ups from true replies."""
    empty_thread = ReviewThread(id="t0", comments=[])
    single_comment = ReviewThread(
        id="t1",
        comments=[ReviewComment(id="c1", author="reviewer", body="Fix this")],
    )
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


def test_resolve_all_pr_review_threads_probe_case_skipped(
    process_fake: ProcessFake,
) -> None:
    """Verify resolve_all_pr_review_threads skips threads where reviewer only replied to self."""
    listing_body = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {
                                "id": "PRRT_PROBE",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 1,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c1",
                                            "author": {"login": "codeql"},
                                            "body": "Security alert",
                                        },
                                        {
                                            "id": "c2",
                                            "author": {"login": "codeql"},
                                            "body": "Still not fixed.",
                                        },
                                    ]
                                },
                            },
                            {
                                "id": "PRRT_VALID",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 2,
                                "comments": {
                                    "nodes": [
                                        {
                                            "id": "c3",
                                            "author": {"login": "reviewer"},
                                            "body": "Issue found",
                                        },
                                        {
                                            "id": "c4",
                                            "author": {"login": "author"},
                                            "body": "Resolved in fix commit",
                                        },
                                    ]
                                },
                            },
                        ],
                    }
                }
            }
        }
    }
    resolved_body = {
        "data": {"resolveReviewThread": {"thread": {"id": "PRRT_VALID", "isResolved": True}}}
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing_body)))
    process_fake.answer(
        lambda call: any("resolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resolved_body)),
    )

    results = resolve_all_pr_review_threads("owner", "repo", 42, only_replied=True)
    assert (len(results), results[0].thread_id) == (1, "PRRT_VALID")

    resolve_calls = [
        call
        for call in process_fake.calls
        if any("resolveReviewThread" in arg for arg in call.argv)
    ]
    assert len(resolve_calls) == 1
    assert any("PRRT_VALID" in arg for arg in resolve_calls[0].argv)


def test_get_pr_review_thread_parses_node(process_fake: ProcessFake) -> None:
    """Verify get_pr_review_thread parses GraphQL node into ReviewThread."""
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
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("GetReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resp)),
    )

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


def test_get_pr_review_thread_raises_when_node_missing(process_fake: ProcessFake) -> None:
    """Verify get_pr_review_thread raises GitHubOperationError when node is missing."""
    resp = {"data": {"node": None}}
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        lambda call: any("GetReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resp)),
    )

    with pytest.raises(GitHubOperationError, match="Review thread PRRT_missing not found"):
        get_pr_review_thread("PRRT_missing")


def test_resolve_all_paces_each_resolve_as_a_write_and_the_listing_as_a_read(
    process_fake: ProcessFake,
) -> None:
    """Through the real `run_gh` with gh's process stubbed (#1125): the thread listing acquires
    as a read and each of the three resolves as a write, so `pr threads resolve-all` sends its
    resolves at least the write interval apart."""
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
    resolved = {"data": {"resolveReviewThread": {"thread": {"id": "PRRT_1", "isResolved": True}}}}

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing)))
    process_fake.answer(
        lambda call: any("resolveReviewThread" in arg for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(resolved)),
    )

    results = resolve_all_pr_review_threads("o", "r", 7)
    graphql_calls = [
        call for call in process_fake.calls if "api" in call.argv and "graphql" in call.argv
    ]
    assert [result.success for result in results] == [True, True, True]
    assert [is_write_gh_command(call.argv[1:]) for call in graphql_calls] == [
        False,
        True,
        True,
        True,
    ]


def test_a_deleted_author_reads_as_ghost_and_an_outdated_thread_keeps_its_original_line(
    process_fake: ProcessFake,
) -> None:
    """GitHub gives a deleted account's comment a null author, which it shows as `ghost`, and an
    outdated thread a null `line` with the `originalLine` it was opened on."""
    node = {
        "id": "PRRT_outdated",
        "isResolved": False,
        "isOutdated": True,
        "path": "src/a.py",
        "line": None,
        "originalLine": 40,
        "comments": {"nodes": [{"id": "C1", "body": "Old note.", "author": None}]},
    }
    listing = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {"pageInfo": {"hasNextPage": False}, "nodes": [node]}
                }
            }
        }
    }
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing)))

    (thread,) = list_pr_review_threads("o", "r", 7)
    assert (thread.is_outdated, thread.line, thread.original_line, thread.comments[0].author) == (
        True,
        None,
        40,
        "ghost",
    )


def test_a_thread_whose_comments_span_three_pages_reads_every_comment_in_order(
    process_fake: ProcessFake,
) -> None:
    """A review thread whose comments are on three pages returns every comment, in order (#2158)."""
    listing = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "pageInfo": {"hasNextPage": False},
                        "nodes": [
                            {
                                "id": "PRRT_thread_1",
                                "isResolved": False,
                                "path": "a.py",
                                "line": 5,
                                "comments": {
                                    "nodes": [
                                        {"id": "C1", "body": "first", "author": {"login": "r"}}
                                    ],
                                    "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                                },
                            }
                        ],
                    }
                }
            }
        }
    }
    after_c1 = {
        "data": {
            "node": {
                "comments": {
                    "nodes": [{"id": "C2", "body": "second", "author": {"login": "r"}}],
                    "pageInfo": {"hasNextPage": True, "endCursor": "c2"},
                }
            }
        }
    }
    after_c2 = {
        "data": {
            "node": {
                "comments": {
                    "nodes": [{"id": "C3", "body": "third", "author": {"login": "r"}}],
                    "pageInfo": {"hasNextPage": False},
                }
            }
        }
    }

    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps(listing)))
    process_fake.answer(
        lambda call: any(arg == "cursor=c1" for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(after_c1)),
    )
    process_fake.answer(
        lambda call: any(arg == "cursor=c2" for arg in call.argv),
        ProcessAnswer(returncode=0, stdout=json.dumps(after_c2)),
    )

    (thread,) = list_pr_review_threads("o", "r", 7)
    assert [comment.id for comment in thread.comments] == ["C1", "C2", "C3"]
    assert [comment.body for comment in thread.comments] == ["first", "second", "third"]


def test_a_non_json_listing_reply_raises_a_github_operation_error(
    process_fake: ProcessFake,
) -> None:
    """A listing reply that is not JSON is a GitHubOperationError naming the parse failure."""
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout="not json"))

    with pytest.raises(GitHubOperationError, match="Failed to parse GraphQL response"):
        list_pr_review_threads("o", "r", 7)


def test_a_list_listing_reply_raises_a_github_operation_error(process_fake: ProcessFake) -> None:
    """A listing reply that is a JSON list, not an object, is a GitHubOperationError."""
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(_is_listing, ProcessAnswer(returncode=0, stdout=json.dumps([1, 2, 3])))

    with pytest.raises(GitHubOperationError, match="expected JSON object"):
        list_pr_review_threads("o", "r", 7)


def test_a_listing_reply_with_graphql_errors_raises_a_github_operation_error(
    process_fake: ProcessFake,
) -> None:
    """A listing reply carrying GraphQL errors is a GitHubOperationError naming the first message."""
    process_fake.answer(
        ["gh", "api", "rate_limit"], ProcessAnswer(returncode=0, stdout=_rate_limit_payload())
    )
    process_fake.answer(
        _is_listing,
        ProcessAnswer(
            returncode=0, stdout=json.dumps({"errors": [{"message": "Cannot query field"}]})
        ),
    )

    with pytest.raises(GitHubOperationError, match="GraphQL error: Cannot query field"):
        list_pr_review_threads("o", "r", 7)
