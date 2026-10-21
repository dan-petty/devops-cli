"""Fail-closed GitHub pull request queue and single PR GraphQL provider for dashboard."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Final

from pydantic import BaseModel, Field

from devops_cli.config.defaults import (
    DEFAULT_DASHBOARD_GITHUB_MAX_PACING_SECONDS,
    DEFAULT_DASHBOARD_GITHUB_PR_LIMIT,
)
from devops_cli.exceptions.git import GitHubOperationError, GitHubRateLimitError
from devops_cli.github.check_verdict import CheckBucket, PRCheckItem, classify_check_item
from devops_cli.github.rate_limiter import (
    calculate_request_delay,
    get_github_rate_limiter,
    run_gh,
)

logger = logging.getLogger(__name__)

GRAPHQL_PR_QUEUE_QUERY: Final[str] = """
query GetPRQueue($owner: String!, $repo: String!, $limit: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequests(states: OPEN, first: $limit, orderBy: {field: CREATED_AT, direction: ASC}) {
      totalCount
      pageInfo {
        hasNextPage
      }
      nodes {
        number
        title
        url
        createdAt
        isDraft
        baseRefName
        reviewDecision
        additions
        deletions
        changedFiles
        reviewThreads(first: 100) {
          pageInfo {
            hasNextPage
          }
          nodes {
            isResolved
          }
        }
        commits(last: 1) {
          nodes {
            commit {
              oid
              statusCheckRollup {
                pageInfo {
                  hasNextPage
                }
                contexts(first: 100) {
                  pageInfo {
                    hasNextPage
                  }
                  nodes {
                    __typename
                    ... on CheckRun {
                      name
                      status
                      conclusion
                      detailsUrl
                      checkSuite {
                        workflowRun {
                          workflow {
                            name
                          }
                        }
                      }
                    }
                    ... on StatusContext {
                      context
                      state
                      targetUrl
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  rateLimit {
    limit
    remaining
    used
    resetAt
  }
}
"""

GRAPHQL_SINGLE_PR_QUERY: Final[str] = """
query GetSinglePR($owner: String!, $repo: String!, $number: Int!) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $number) {
      number
      title
      url
      createdAt
      isDraft
      baseRefName
      reviewDecision
      additions
      deletions
      changedFiles
      reviewThreads(first: 100) {
        pageInfo {
          hasNextPage
        }
        nodes {
          isResolved
        }
      }
      commits(last: 1) {
        nodes {
          commit {
            oid
            statusCheckRollup {
              pageInfo {
                hasNextPage
              }
              contexts(first: 100) {
                pageInfo {
                  hasNextPage
                }
                nodes {
                  __typename
                  ... on CheckRun {
                    name
                    status
                    conclusion
                    detailsUrl
                    checkSuite {
                      workflowRun {
                        workflow {
                          name
                        }
                      }
                    }
                  }
                  ... on StatusContext {
                    context
                    state
                    targetUrl
                  }
                }
              }
            }
          }
        }
      }
    }
  }
  rateLimit {
    limit
    remaining
    used
    resetAt
  }
}
"""


def _utc_text(epoch: float) -> str:
    """Format an epoch as ISO 8601 UTC string."""
    return datetime.fromtimestamp(epoch, tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def check_pacing_guard(
    subcommand: str = "graphql",
    max_pacing_seconds: float = DEFAULT_DASHBOARD_GITHUB_MAX_PACING_SECONDS,
) -> None:
    """Check rate limit pacing before calling gh, failing closed instead of sleeping.

    Raises GitHubRateLimitError if the pacing delay exceeds max_pacing_seconds.
    Does not raise or sleep when the quota is unknown.
    """
    limiter = get_github_rate_limiter()
    quota = limiter.get_quota(subcommand)
    if quota.remaining is None or quota.reset_epoch is None:
        return
    time_until_reset = max(0.0, quota.reset_epoch - time.time())
    if time_until_reset <= 0.0:
        return
    delay = calculate_request_delay(time_until_reset, quota.remaining, limit=quota.limit)
    if delay > max_pacing_seconds:
        reset_time = _utc_text(quota.reset_epoch)
        raise GitHubRateLimitError(
            f"Rate limit wait of {delay:.1f}s exceeds limit of {max_pacing_seconds:.1f}s "
            f"(reset at {reset_time})",
            subcommand=subcommand,
            details={
                "wait": delay,
                "reset_epoch": quota.reset_epoch,
                "max_wait": max_pacing_seconds,
            },
        )


class PRChecksSummary(BaseModel):
    """Aggregate check counts and individual items for a PR."""

    has_rollup: bool = True
    fail: int = 0
    pending: int = 0
    unread: int = 0
    cancel: int = 0
    skipping: int = 0
    pass_count: int = 0
    has_next_page: bool = False
    items: list[PRCheckItem] = Field(default_factory=list)

    @property
    def has_failing_checks(self) -> bool:
        """Whether any check failed."""
        return self.fail > 0

    def format_counts(self) -> str:
        """Format the checks bucket counts for queue table display."""
        if not self.has_rollup or (not self.items and not self.has_next_page):
            return "none"
        counts = [
            (label, getattr(self, attr))
            for label, attr in (
                ("fail", "fail"),
                ("pending", "pending"),
                ("unread", "unread"),
                ("cancel", "cancel"),
                ("skip", "skipping"),
                ("pass", "pass_count"),
            )
        ]
        parts = [f"{label} {val}" for label, val in counts if val > 0]
        suffix = "+" if self.has_next_page else ""
        if not parts:
            return f"none{suffix}"
        return f"{', '.join(parts)}{suffix}"


class GitHubPRSummary(BaseModel):
    """Normalized pull request information for dashboard queue and inspector."""

    number: int
    title: str
    url: str
    created_at: str
    is_draft: bool = False
    base_ref_name: str = ""
    review_decision: str | None = None
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    head_sha: str = ""
    checks: PRChecksSummary = Field(default_factory=PRChecksSummary)
    unresolved_threads_count: int = 0
    threads_has_next_page: bool = False

    @property
    def has_failing_checks(self) -> bool:
        """Whether this PR has failing checks."""
        return self.checks.has_failing_checks

    @property
    def threads_display(self) -> str:
        """Unresolved threads count or ? when paginated."""
        if self.threads_has_next_page:
            return "?"
        return str(self.unresolved_threads_count)


class GitHubQuotaSummary(BaseModel):
    """API quota metrics for Core REST and GraphQL APIs."""

    core_limit: int = 0
    core_remaining: int = 0
    core_reset_epoch: float | None = None
    graphql_limit: int = 0
    graphql_remaining: int = 0
    graphql_reset_epoch: float | None = None

    @staticmethod
    def _format_time_to_reset(epoch: float | None) -> str:
        if epoch is None:
            return "reset unknown"
        wait = max(0.0, epoch - time.time())
        if wait >= 3600:
            hours = int(wait // 3600)
            minutes = round((wait % 3600) / 60)
            if minutes == 60:
                hours += 1
                minutes = 0
            return f"reset in {hours}h {minutes}m" if minutes else f"reset in {hours}h"
        minutes = round(wait / 60)
        if minutes >= 1:
            return f"reset in {minutes}m"
        return f"reset in {round(wait)}s"

    def format_banner(self) -> str:
        """Format quota information for status banner."""
        core_reset = self._format_time_to_reset(self.core_reset_epoch)
        gql_reset = self._format_time_to_reset(self.graphql_reset_epoch)
        return (
            f"core {self.core_remaining}/{self.core_limit} ({core_reset}), "
            f"graphql {self.graphql_remaining}/{self.graphql_limit} ({gql_reset})"
        )


class PRQueueResult(BaseModel):
    """Result of fetching the open pull request queue."""

    total_count: int = 0
    has_next_page: bool = False
    prs: list[GitHubPRSummary] = Field(default_factory=list)


def _extract_workflow_name(node: dict[str, Any]) -> str:
    cs = node.get("checkSuite")
    if not isinstance(cs, dict):
        return ""
    wr = cs.get("workflowRun")
    if not isinstance(wr, dict):
        return ""
    wf = wr.get("workflow")
    if not isinstance(wf, dict):
        return ""
    return str(wf.get("name") or "")


def _classify_rollup_node(node: dict[str, Any]) -> PRCheckItem:
    typename = node.get("__typename")
    if typename == "CheckRun" or "conclusion" in node or "detailsUrl" in node:
        return classify_check_item(
            name=str(node.get("name") or "unknown"),
            status=node.get("status"),
            conclusion=node.get("conclusion"),
            workflow=_extract_workflow_name(node),
            link=str(node.get("detailsUrl") or ""),
        )
    return classify_check_item(
        name=str(node.get("context") or "unknown"),
        state=node.get("state"),
        link=str(node.get("targetUrl") or ""),
    )


_BUCKET_ATTR_MAP: Final[dict[CheckBucket, str]] = {
    CheckBucket.FAIL: "fail",
    CheckBucket.PENDING: "pending",
    CheckBucket.UNREAD: "unread",
    CheckBucket.CANCEL: "cancel",
    CheckBucket.SKIPPING: "skipping",
    CheckBucket.PASS: "pass_count",
}


def _accumulate_check_bucket(summary: PRChecksSummary, item: PRCheckItem) -> None:
    attr = _BUCKET_ATTR_MAP.get(item.bucket)
    if attr:
        setattr(summary, attr, getattr(summary, attr) + 1)
    summary.items.append(item)


def parse_status_check_rollup(rollup: dict[str, Any] | None) -> PRChecksSummary:
    """Classify status check rollup contexts into an aggregate PRChecksSummary."""
    if rollup is None:
        return PRChecksSummary(has_rollup=False)
    contexts = rollup.get("contexts")
    ctx_page_info = (contexts or {}).get("pageInfo", {}) if isinstance(contexts, dict) else {}
    rollup_page_info = rollup.get("pageInfo", {}) if isinstance(rollup, dict) else {}
    has_next = bool(ctx_page_info.get("hasNextPage") or rollup_page_info.get("hasNextPage"))

    nodes = (contexts or {}).get("nodes", []) if isinstance(contexts, dict) else []
    summary = PRChecksSummary(has_rollup=True, has_next_page=has_next)
    for node in nodes:
        if isinstance(node, dict):
            item = _classify_rollup_node(node)
            _accumulate_check_bucket(summary, item)
    return summary


def _parse_pr_node(node: dict[str, Any]) -> GitHubPRSummary:
    number = int(node.get("number") or 0)
    title = str(node.get("title") or "")
    url = str(node.get("url") or "")
    created_at = str(node.get("createdAt") or "")
    is_draft = bool(node.get("isDraft", False))
    base_ref = str(node.get("baseRefName") or "")
    review_dec = node.get("reviewDecision")
    additions = int(node.get("additions") or 0)
    deletions = int(node.get("deletions") or 0)
    changed_files = int(node.get("changedFiles") or 0)

    commits_nodes = node.get("commits", {}).get("nodes", [])
    commit = commits_nodes[0].get("commit", {}) if commits_nodes else {}
    head_sha = str(commit.get("oid") or "")
    status_rollup = commit.get("statusCheckRollup")
    checks = parse_status_check_rollup(status_rollup)

    threads_data = node.get("reviewThreads", {})
    threads_page_info = threads_data.get("pageInfo", {})
    threads_has_next = bool(threads_page_info.get("hasNextPage", False))
    thread_nodes = threads_data.get("nodes", [])
    unresolved_count = sum(1 for t in thread_nodes if not t.get("isResolved", False))

    return GitHubPRSummary(
        number=number,
        title=title,
        url=url,
        created_at=created_at,
        is_draft=is_draft,
        base_ref_name=base_ref,
        review_decision=review_dec,
        additions=additions,
        deletions=deletions,
        changed_files=changed_files,
        head_sha=head_sha,
        checks=checks,
        unresolved_threads_count=unresolved_count,
        threads_has_next_page=threads_has_next,
    )


def _build_graphql_args(variables: dict[str, Any]) -> list[str]:
    args: list[str] = []
    for k, v in variables.items():
        if v is None:
            continue
        flag = "-F" if isinstance(v, int) else "-f"
        args.extend([flag, f"{k}={v}"])
    return args


def _run_graphql_query(
    query: str,
    variables: dict[str, Any],
    runner: Callable[..., Any] = run_gh,
) -> dict[str, Any]:
    args = ["api", "graphql", "-f", f"query={query}", *_build_graphql_args(variables)]
    proc = runner(args, check=False)
    if proc.returncode != 0 or not proc.stdout:
        err = proc.stderr.strip() if proc.stderr else f"Exit code {proc.returncode}"
        raise GitHubOperationError(f"GitHub GraphQL query failed: {err}")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubOperationError(f"Failed to parse GraphQL response: {exc}") from exc
    if not isinstance(data, dict):
        raise GitHubOperationError("Unexpected GraphQL response: expected JSON object")
    if data.get("errors"):
        first_err = data["errors"][0].get("message", "Unknown GraphQL error")
        raise GitHubOperationError(f"GraphQL error: {first_err}")
    return data


def fetch_pr_queue(
    owner: str,
    repo: str,
    limit: int = DEFAULT_DASHBOARD_GITHUB_PR_LIMIT,
    runner: Callable[..., Any] = run_gh,
) -> PRQueueResult:
    """Fetch open pull requests sorted oldest first via single GraphQL query."""
    variables = {"owner": owner, "repo": repo, "limit": limit}
    data = _run_graphql_query(GRAPHQL_PR_QUEUE_QUERY, variables, runner=runner)
    repo_data = data.get("data", {}).get("repository")
    if not isinstance(repo_data, dict):
        raise GitHubOperationError(f"Repository {owner}/{repo} not found in GraphQL response")
    pr_conn = repo_data.get("pullRequests", {})
    total_count = int(pr_conn.get("totalCount") or 0)
    has_next_page = bool(pr_conn.get("pageInfo", {}).get("hasNextPage", False))
    nodes = pr_conn.get("nodes", [])
    prs = [_parse_pr_node(n) for n in nodes if isinstance(n, dict)]
    return PRQueueResult(total_count=total_count, has_next_page=has_next_page, prs=prs)


def fetch_single_pr(
    owner: str,
    repo: str,
    pr_number: int,
    runner: Callable[..., Any] = run_gh,
) -> GitHubPRSummary:
    """Fetch single pull request details via GraphQL query."""
    variables = {"owner": owner, "repo": repo, "number": pr_number}
    data = _run_graphql_query(GRAPHQL_SINGLE_PR_QUERY, variables, runner=runner)
    repo_data = data.get("data", {}).get("repository")
    if not isinstance(repo_data, dict):
        raise GitHubOperationError(f"Repository {owner}/{repo} not found in GraphQL response")
    pr_node = repo_data.get("pullRequest")
    if not isinstance(pr_node, dict):
        raise GitHubOperationError(f"Pull request #{pr_number} not found")
    return _parse_pr_node(pr_node)
