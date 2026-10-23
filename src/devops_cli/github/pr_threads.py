"""GitHub Pull Request review thread management, in-thread replies, and resolution."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from devops_cli.config.constants import CONST_GITHUB_GHOST_LOGIN
from devops_cli.config.defaults import DEFAULT_GH_MAX_PAGINATED_PAGES
from devops_cli.exceptions.git import GitHubOperationError
from devops_cli.github.rate_limiter import run_gh

logger = logging.getLogger(__name__)


class ReviewComment(BaseModel):
    """A comment within a pull request review thread."""

    id: str
    body: str
    author: str = ""
    created_at: str = ""
    url: str = ""


class ReviewThread(BaseModel):
    """A pull request review thread containing one or more comments.

    `line` is None once a later push moved the thread's lines out of the diff, which makes it
    outdated, and for a thread on a whole file; `original_line` is the line it was opened on,
    None for a thread on a whole file.
    """

    id: str
    is_resolved: bool = False
    is_outdated: bool = False
    path: str = ""
    line: int | None = None
    original_line: int | None = None
    comments: list[ReviewComment] = Field(default_factory=list)


class ThreadResolutionResult(BaseModel):
    """Result of resolving or unresolving a review thread."""

    thread_id: str
    is_resolved: bool
    success: bool = True


def _build_graphql_args(variables: dict[str, Any]) -> list[str]:
    """Format GraphQL variable arguments for gh api."""
    args: list[str] = []
    for k, v in variables.items():
        if v is None:
            continue
        flag = "-F" if isinstance(v, int) else "-f"
        args.extend([flag, f"{k}={v}"])
    return args


def _parse_graphql_output(stdout: str) -> dict[str, Any]:
    """Parse and validate JSON response from GraphQL API."""
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse GraphQL response: {exc}") from exc

    if not isinstance(data, dict):
        raise GitHubOperationError("Unexpected GraphQL response: expected JSON object")

    if data.get("errors"):
        first_err = data["errors"][0].get("message", "Unknown GraphQL error")
        raise GitHubOperationError(f"GraphQL error: {first_err}")

    return data


def graphql_args(query: str, variables: dict[str, Any]) -> list[str]:
    """The `gh api graphql` arguments that send `query` with `variables`."""
    return ["api", "graphql", "-f", f"query={query}", *_build_graphql_args(variables)]


def _run_graphql(args: list[str]) -> dict[str, Any]:
    """Run a `gh api graphql` call with rate limiting and backoff, and parse its answer."""
    proc = run_gh(args, check=False)
    if proc.returncode != 0 or not proc.stdout:
        err = proc.stderr.strip() if proc.stderr else f"Exit code {proc.returncode}"
        raise GitHubOperationError(f"GitHub GraphQL query failed: {err}")

    return _parse_graphql_output(proc.stdout)


def _run_graphql_query(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """Execute a GraphQL query/mutation via `gh api graphql` with rate limiting and backoff."""
    return _run_graphql(graphql_args(query, variables))


_QUERY_GET_REVIEW_THREADS = """
query GetReviewThreads($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
  rateLimit {
    limit
    remaining
    cost
    resetAt
  }
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      reviewThreads(first: 50, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 50) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              id
              body
              author { login }
              createdAt
              url
            }
          }
        }
      }
    }
  }
}
""".strip()

_QUERY_GET_REVIEW_THREAD = """
query GetReviewThread($threadId: ID!) {
  node(id: $threadId) {
    ... on PullRequestReviewThread {
      id
      isResolved
      isOutdated
      path
      line
      originalLine
      comments(first: 50) {
        nodes {
          id
          body
          author { login }
          createdAt
          url
        }
      }
    }
  }
}
""".strip()

_QUERY_GET_THREAD_COMMENTS = """
query GetThreadComments($threadId: ID!, $cursor: String) {
  node(id: $threadId) {
    ... on PullRequestReviewThread {
      comments(first: 100, after: $cursor) {
        pageInfo {
          hasNextPage
          endCursor
        }
        nodes {
          id
          body
          author { login }
          createdAt
          url
        }
      }
    }
  }
}
""".strip()

_MUTATION_ADD_REPLY = """
mutation AddReply($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(input: { pullRequestReviewThreadId: $threadId, body: $body }) {
    comment {
      id
      body
      author { login }
      createdAt
    }
  }
}
""".strip()

_MUTATION_RESOLVE_THREAD = """
mutation ResolveThread($threadId: ID!) {
  resolveReviewThread(input: { threadId: $threadId }) {
    thread {
      id
      isResolved
    }
  }
}
""".strip()

_MUTATION_UNRESOLVE_THREAD = """
mutation UnresolveThread($threadId: ID!) {
  unresolveReviewThread(input: { threadId: $threadId }) {
    thread {
      id
      isResolved
    }
  }
}
""".strip()


def review_threads_args(
    owner: str, repo_name: str, pr_number: int | str, cursor: str | None = None
) -> list[str]:
    """The arguments that read one page of a pull request's review threads."""
    variables = {"owner": owner, "repo": repo_name, "pr": pr_number, "cursor": cursor}
    return graphql_args(_QUERY_GET_REVIEW_THREADS, variables)


def thread_comments_args(thread_id: str, cursor: str) -> list[str]:
    """The arguments that read the page of review thread `thread_id`'s comments after `cursor`."""
    return graphql_args(_QUERY_GET_THREAD_COMMENTS, {"threadId": thread_id, "cursor": cursor})


def reply_thread_args(thread_id: str, body: str) -> list[str]:
    """The arguments that post `body` as a reply in review thread `thread_id`."""
    return graphql_args(_MUTATION_ADD_REPLY, {"threadId": thread_id, "body": body})


def resolve_thread_args(thread_id: str) -> list[str]:
    """The arguments that resolve review thread `thread_id`."""
    return graphql_args(_MUTATION_RESOLVE_THREAD, {"threadId": thread_id})


def _author_login(raw: dict[str, Any]) -> str:
    """A comment's author login: GitHub's `ghost` for a deleted account, whose `author` is
    null; empty when the author was not read."""
    if "author" not in raw:
        return ""
    author = raw["author"]
    if author is None:
        return CONST_GITHUB_GHOST_LOGIN
    return str(author.get("login", "")) if isinstance(author, dict) else str(author)


def _parse_review_comment(raw: dict[str, Any]) -> ReviewComment:
    """Parse a single comment dictionary from GraphQL nodes."""
    return ReviewComment(
        id=raw.get("id", ""),
        body=raw.get("body", ""),
        author=_author_login(raw),
        created_at=raw.get("createdAt", ""),
        url=raw.get("url", "") or "",
    )


def _parse_review_thread(node: dict[str, Any]) -> ReviewThread:
    """Parse a single review thread node from GraphQL response."""
    raw_comments = node.get("comments", {}).get("nodes", [])
    comments = [_parse_review_comment(c) for c in raw_comments if isinstance(c, dict)]
    return ReviewThread(
        id=node.get("id", ""),
        is_resolved=bool(node.get("isResolved", False)),
        is_outdated=bool(node.get("isOutdated", False)),
        path=node.get("path", "") or "",
        line=node.get("line"),
        original_line=node.get("originalLine"),
        comments=comments,
    )


def _later_comments(thread_id: str, cursor: str) -> list[ReviewComment]:
    """The comments of review thread `thread_id` after `cursor`, every page of them."""
    comments: list[ReviewComment] = []
    after: str | None = cursor
    for _ in range(DEFAULT_GH_MAX_PAGINATED_PAGES):
        if not after:
            break
        data = _run_graphql(thread_comments_args(thread_id, after))
        page = ((data.get("data") or {}).get("node") or {}).get("comments") or {}
        nodes = page.get("nodes") or []
        comments.extend(_parse_review_comment(c) for c in nodes if isinstance(c, dict))
        info = page.get("pageInfo") or {}
        after = info.get("endCursor") if info.get("hasNextPage") else None
    return comments


def _read_thread(node: dict[str, Any]) -> ReviewThread:
    """A review thread node, with the comments past its first page read too."""
    thread = _parse_review_thread(node)
    info = (node.get("comments") or {}).get("pageInfo") or {}
    cursor = info.get("endCursor") if info.get("hasNextPage") else None
    if not cursor:
        return thread
    later = _later_comments(thread.id, str(cursor))
    return thread.model_copy(update={"comments": [*thread.comments, *later]})


def _list_pr_review_threads_graphql(
    owner: str,
    repo_name: str,
    pr_number: int,
    unresolved_only: bool = False,
) -> list[ReviewThread]:
    """Execute paginated GraphQL query to retrieve PR review threads."""
    threads: list[ReviewThread] = []
    cursor: str | None = None

    while True:
        data = _run_graphql(review_threads_args(owner, repo_name, pr_number, cursor or None))
        pr_data = (
            data.get("data", {})
            .get("repository", {})
            .get("pullRequest", {})
            .get("reviewThreads", {})
        )
        raw_nodes = pr_data.get("nodes", [])
        threads.extend(_read_thread(n) for n in raw_nodes if isinstance(n, dict))

        page_info = pr_data.get("pageInfo", {})
        if not page_info.get("hasNextPage"):
            break
        cursor = page_info.get("endCursor")
        if not cursor:
            break

    if unresolved_only:
        return [t for t in threads if not t.is_resolved]
    return threads


def list_pr_review_threads(
    owner: str,
    repo: str,
    pr_number: int,
    unresolved_only: bool = False,
) -> list[ReviewThread]:
    """Retrieve PR review discussion threads via GitHub GraphQL API with cursor pagination.

    Honors GraphQL rate limits with adaptive pacing and progressive backoff without REST fallback.
    """
    repo_name = repo.split("/")[-1]
    return _list_pr_review_threads_graphql(owner, repo_name, pr_number, unresolved_only)


def reply_pr_review_thread(thread_id: str, body: str) -> ReviewComment:
    """Post an in-thread reply to a specific PR review discussion thread."""
    clean_body = body.strip()
    if not clean_body:
        raise GitHubOperationError("Reply comment body cannot be empty.")
    data = _run_graphql(reply_thread_args(thread_id, clean_body))
    comment_data = (
        data.get("data", {}).get("addPullRequestReviewThreadReply", {}).get("comment", {})
    )
    return _parse_review_comment(comment_data)


def resolve_pr_review_thread(thread_id: str) -> ThreadResolutionResult:
    """Programmatically mark a PR review discussion thread as resolved."""
    data = _run_graphql(resolve_thread_args(thread_id))
    thread_data = data.get("data", {}).get("resolveReviewThread", {}).get("thread", {})
    is_resolved = bool(thread_data.get("isResolved", True))
    return ThreadResolutionResult(thread_id=thread_id, is_resolved=is_resolved, success=True)


def unresolve_pr_review_thread(thread_id: str) -> ThreadResolutionResult:
    """Reopen a previously resolved PR review discussion thread."""
    data = _run_graphql_query(
        _MUTATION_UNRESOLVE_THREAD,
        variables={"threadId": thread_id},
    )
    thread_data = data.get("data", {}).get("unresolveReviewThread", {}).get("thread", {})
    is_resolved = bool(thread_data.get("isResolved", False))
    return ThreadResolutionResult(thread_id=thread_id, is_resolved=is_resolved, success=True)


def _attempt_resolve_thread(thread_id: str, pr_number: int) -> ThreadResolutionResult:
    """Attempt to resolve an individual PR review thread, logging any failure defensively."""
    try:
        return resolve_pr_review_thread(thread_id)
    except GitHubOperationError as exc:
        logger.warning(
            "Failed to resolve review thread %s on PR #%d: %s",
            thread_id,
            pr_number,
            str(exc)[:256],
        )
        return ThreadResolutionResult(thread_id=thread_id, is_resolved=False, success=False)


def get_pr_review_thread(thread_id: str) -> ReviewThread:
    """Retrieve an individual PR review thread by its GraphQL node ID."""
    data = _run_graphql_query(
        _QUERY_GET_REVIEW_THREAD,
        variables={"threadId": thread_id},
    )
    node = data.get("data", {}).get("node")
    if not isinstance(node, dict) or not node.get("id"):
        raise GitHubOperationError(f"Review thread {thread_id} not found.")
    return _parse_review_thread(node)


def has_non_opener_reply(thread: ReviewThread) -> bool:
    """Return True if at least one comment after the first is authored by someone other than the opener."""
    if len(thread.comments) <= 1:
        return False
    opener = (thread.comments[0].author or "").strip().lower()
    return any((c.author or "").strip().lower() != opener for c in thread.comments[1:])


def resolve_all_pr_review_threads(
    owner: str,
    repo: str,
    pr_number: int,
    only_replied: bool = True,
) -> list[ThreadResolutionResult]:
    """Resolve review discussion threads on a PR, optionally filtering to replied-only threads.

    Args:
        owner: Repository owner/org.
        repo: Repository name (with or without owner prefix).
        pr_number: Pull request number.
        only_replied: If True, only threads with a reply from someone other than the thread opener are resolved.

    Returns:
        List of ThreadResolutionResult for each attempted thread resolution.
    """
    repo_name = repo.split("/")[-1]
    unresolved = list_pr_review_threads(owner, repo_name, pr_number, unresolved_only=True)
    if not unresolved:
        return []

    targets = [t for t in unresolved if not only_replied or has_non_opener_reply(t)]
    return [_attempt_resolve_thread(t.id, pr_number) for t in targets]
