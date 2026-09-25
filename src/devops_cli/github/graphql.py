"""GitHub GraphQL client, batch query consolidation, RFC 7234 ETag caching, and webhook verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx2
from pydantic import BaseModel, Field

from devops_cli.config.constants import (
    CONST_GH_CLI,
    CONST_GH_ETAG_CACHE_FILENAME,
    CONST_GH_HEADER_ETAG,
    CONST_GH_HEADER_IF_NONE_MATCH,
    CONST_GH_HEADER_USER_AGENT,
    CONST_URL_GITHUB_GRAPHQL,
)
from devops_cli.config.defaults import (
    DEFAULT_DATA_DIR,
    DEFAULT_GH_GRAPHQL_CACHE_MAX_ENTRIES,
    DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD,
    DEFAULT_HTTP_TIMEOUT_SECONDS,
)
from devops_cli.exceptions.git import (
    GitHubGraphQLError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubWebhookVerificationError,
)
from devops_cli.github.rate_limiter import run_gh

logger = logging.getLogger(__name__)


# ── Models ───────────────────────────────────────────────────────────────────


class GraphQLRateLimit(BaseModel):
    """Normalized GitHub GraphQL rate limit telemetry."""

    limit: int = 5000
    cost: int = 1
    remaining: int = 5000
    reset_at: str = ""


class GraphQLMilestone(BaseModel):
    """Normalized milestone representation returned by GraphQL batch queries."""

    number: int
    title: str
    description: str = ""
    state: str = "OPEN"
    due_on: str | None = None
    total_issues: int = 0
    closed_issues: int = 0


class GraphQLIssue(BaseModel):
    """Normalized GitHub Issue representation returned by GraphQL queries."""

    number: int
    title: str
    body: str = ""
    state: str = "OPEN"
    url: str = ""
    created_at: str = ""
    updated_at: str = ""
    milestone: str | None = None
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)


class GraphQLPullRequest(BaseModel):
    """Normalized GitHub Pull Request representation returned by GraphQL queries."""

    number: int
    title: str
    state: str = "OPEN"
    is_draft: bool = False
    url: str = ""
    created_at: str = ""
    updated_at: str = ""
    base_ref: str = ""
    head_ref: str = ""
    mergeable: str | None = None
    milestone: str | None = None
    labels: list[str] = Field(default_factory=list)


class RepoOverview(BaseModel):
    """Consolidated repository snapshot retrieved in a single GraphQL round-trip."""

    owner: str
    name: str
    description: str = ""
    is_private: bool = False
    default_branch: str = ""
    milestones: list[GraphQLMilestone] = Field(default_factory=list)
    issues: list[GraphQLIssue] = Field(default_factory=list)
    pull_requests: list[GraphQLPullRequest] = Field(default_factory=list)
    rate_limit: GraphQLRateLimit | None = None


class WebhookEvent(BaseModel):
    """Normalized GitHub Webhook event dispatch payload."""

    event_type: str
    action: str | None = None
    repository: str | None = None
    sender: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


# ── RFC 7234 ETag Caching ────────────────────────────────────────────────────


@dataclass
class _ETagCacheEntry:
    etag: str
    data: Any
    timestamp: float


class RFC7234ETagCache:
    """In-memory and file-backed RFC 7234 conditional HTTP cache utilizing ETags."""

    def __init__(
        self,
        cache_file: Path | None = None,
        max_entries: int = DEFAULT_GH_GRAPHQL_CACHE_MAX_ENTRIES,
    ) -> None:
        self._cache_file = cache_file
        self._max_entries = max_entries
        self._entries: dict[str, _ETagCacheEntry] = {}
        self._lock = threading.Lock()
        self._load_from_disk()

    @staticmethod
    def compute_key(query: str, variables: dict[str, Any] | None = None) -> str:
        """Derive a deterministic SHA-256 cache key from query text and variables."""
        norm_query = " ".join(query.strip().split())
        vars_str = json.dumps(variables or {}, sort_keys=True, separators=(",", ":"))
        combined = f"{norm_query}::{vars_str}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    def get(self, key: str) -> tuple[str | None, Any | None]:
        """Return (etag, cached_data) tuple for the key if present."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                return entry.etag, entry.data
            return None, None

    def set(self, key: str, etag: str, data: Any) -> None:
        """Store an ETag and payload entry, enforcing bounded cache capacity."""
        with self._lock:
            if len(self._entries) >= self._max_entries:
                oldest_key = min(self._entries.keys(), key=lambda k: self._entries[k].timestamp)
                self._entries.pop(oldest_key, None)
            self._entries[key] = _ETagCacheEntry(
                etag=etag,
                data=data,
                timestamp=time.time(),
            )
            self._save_to_disk()

    def clear(self) -> None:
        """Purge all entries from the in-memory cache and persistent store."""
        with self._lock:
            self._entries.clear()
            if self._cache_file and self._cache_file.exists():
                try:
                    self._cache_file.unlink()
                except OSError as exc:
                    logger.debug("Failed to remove cache file: %s", exc)

    def _load_from_disk(self) -> None:
        """Hydrate entries from persistent cache file if available."""
        if not self._cache_file or not self._cache_file.is_file():
            return
        try:
            raw = json.loads(self._cache_file.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, item in raw.items():
                    if isinstance(item, dict) and "etag" in item and "data" in item:
                        self._entries[k] = _ETagCacheEntry(
                            etag=str(item["etag"]),
                            data=item["data"],
                            timestamp=float(item.get("timestamp", 0.0)),
                        )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.debug("Could not read ETag cache from disk: %s", exc)

    def _save_to_disk(self) -> None:
        """Persist cache entries to disk defensively."""
        if not self._cache_file:
            return
        try:
            self._cache_file.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                k: {"etag": v.etag, "data": v.data, "timestamp": v.timestamp}
                for k, v in self._entries.items()
            }
            tmp = self._cache_file.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._cache_file)
        except OSError as exc:
            logger.debug("Could not write ETag cache to disk: %s", exc)


# ── Token-Bucket Rate Optimization ───────────────────────────────────────────


class GraphQLTokenBucket:
    """Client-side token bucket rate tracking for GitHub GraphQL point quotas."""

    def __init__(self, safety_threshold: int = DEFAULT_GH_GRAPHQL_SAFETY_THRESHOLD) -> None:
        self._safety_threshold = safety_threshold
        self._limit = 5000
        self._remaining = 5000
        self._cost = 1
        self._reset_epoch: float | None = None
        self._lock = threading.Lock()

    @property
    def remaining(self) -> int:
        with self._lock:
            return self._remaining

    @property
    def cost(self) -> int:
        with self._lock:
            return self._cost

    def update_from_rate_limit(self, data: dict[str, Any]) -> None:
        """Update quota state from the rateLimit field in a GraphQL response."""
        with self._lock:
            self._limit = int(data.get("limit", self._limit))
            self._remaining = int(data.get("remaining", self._remaining))
            self._cost = int(data.get("cost", self._cost))
            reset_at = str(data.get("resetAt", "") or "")
            if reset_at:
                try:
                    from datetime import datetime

                    clean = reset_at.replace("Z", "+00:00")
                    self._reset_epoch = datetime.fromisoformat(clean).timestamp()
                except ValueError, TypeError:
                    pass

    def estimate_pacing_delay(self) -> float:
        """Calculate mandatory pause when approaching the rate limit safety margin."""
        with self._lock:
            if self._remaining > self._safety_threshold:
                return 0.0
            if self._reset_epoch is None:
                return 1.0
            now = time.time()
            time_until_reset = max(0.0, self._reset_epoch - now)
            rem = max(1, self._remaining)
            return min(60.0, time_until_reset / rem)


# ── Webhook Signature Verification & Event Dispatcher ────────────────────────


def verify_webhook_signature(
    payload: bytes | str,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify GitHub webhook payload against HMAC-SHA256 signature using constant-time comparison."""
    if not signature_header or not secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    received_hash = signature_header[len("sha256=") :]
    payload_bytes = payload.encode("utf-8") if isinstance(payload, str) else payload
    secret_bytes = secret.encode("utf-8")
    computed_hash = hmac.new(secret_bytes, payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received_hash, computed_hash)


class WebhookEventDispatcher:
    """Observer pattern event dispatcher for verified GitHub webhook events."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[WebhookEvent], None]]] = {}

    def register(self, event_type: str, handler: Callable[[WebhookEvent], None]) -> None:
        """Register a handler for a specific event type (or '*' for all events)."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def dispatch(
        self,
        event_type: str,
        payload: dict[str, Any],
        signature_header: str | None = None,
        secret: str | None = None,
        raw_body: bytes | str | None = None,
    ) -> bool:
        """Verify signature if secret is provided and dispatch event to registered handlers."""
        if secret is not None:
            body_to_verify = (
                raw_body
                if raw_body is not None
                else json.dumps(payload, separators=(",", ":")).encode("utf-8")
            )
            if not verify_webhook_signature(body_to_verify, signature_header, secret):
                raise GitHubWebhookVerificationError(
                    "GitHub webhook HMAC-SHA256 signature validation failed",
                    details={"event_type": event_type[:256]},
                )

        repo_name: str | None = None
        repo_data = payload.get("repository")
        if isinstance(repo_data, dict):
            repo_name = repo_data.get("full_name") or repo_data.get("name")

        sender_login: str | None = None
        sender_data = payload.get("sender")
        if isinstance(sender_data, dict):
            sender_login = sender_data.get("login")

        event = WebhookEvent(
            event_type=event_type,
            action=payload.get("action"),
            repository=repo_name,
            sender=sender_login,
            payload=payload,
        )

        matched = self._handlers.get(event_type, []) + self._handlers.get("*", [])
        for handler in matched:
            try:
                handler(event)
            except Exception as exc:
                logger.error("Handler error on webhook event %s: %s", event_type, exc)

        return True


# ── GraphQL Queries ──────────────────────────────────────────────────────────


GRAPHQL_REPO_OVERVIEW_QUERY = """
query GetRepoOverview(
  $owner: String!
  $name: String!
  $issuesLimit: Int!
  $prsLimit: Int!
  $milestonesLimit: Int!
) {
  repository(owner: $owner, name: $name) {
    name
    nameWithOwner
    description
    isPrivate
    defaultBranchRef {
      name
    }
    milestones(first: $milestonesLimit, states: [OPEN, CLOSED], orderBy: {field: DUE_DATE, direction: ASC}) {
      nodes {
        number
        title
        description
        state
        dueOn
        totalIssues: issues {
          totalCount
        }
        closedIssues: issues(states: [CLOSED]) {
          totalCount
        }
      }
    }
    issues(first: $issuesLimit, states: [OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number
        title
        body
        state
        url
        createdAt
        updatedAt
        milestone {
          title
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
        assignees(first: 5) {
          nodes {
            login
          }
        }
      }
    }
    pullRequests(first: $prsLimit, states: [OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number
        title
        state
        isDraft
        url
        createdAt
        updatedAt
        baseRefName
        headRefName
        mergeable
        milestone {
          title
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
      }
    }
  }
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
}
"""

GRAPHQL_ISSUES_QUERY = """
query GetIssues($owner: String!, $name: String!, $states: [IssueState!], $limit: Int!) {
  repository(owner: $owner, name: $name) {
    issues(first: $limit, states: $states, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number
        title
        body
        state
        url
        createdAt
        updatedAt
        milestone {
          title
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
        assignees(first: 5) {
          nodes {
            login
          }
        }
      }
    }
  }
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
}
"""

GRAPHQL_PULL_REQUESTS_QUERY = """
query GetPullRequests($owner: String!, $name: String!, $states: [PullRequestState!], $limit: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $limit, states: $states, orderBy: {field: UPDATED_AT, direction: DESC}) {
      nodes {
        number
        title
        state
        isDraft
        url
        createdAt
        updatedAt
        baseRefName
        headRefName
        mergeable
        milestone {
          title
        }
        labels(first: 10) {
          nodes {
            name
          }
        }
      }
    }
  }
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
}
"""

GRAPHQL_MILESTONES_QUERY = """
query GetMilestones($owner: String!, $name: String!, $states: [MilestoneState!], $limit: Int!) {
  repository(owner: $owner, name: $name) {
    milestones(first: $limit, states: $states, orderBy: {field: DUE_DATE, direction: ASC}) {
      nodes {
        number
        title
        description
        state
        dueOn
        totalIssues: issues {
          totalCount
        }
        closedIssues: issues(states: [CLOSED]) {
          totalCount
        }
      }
    }
  }
  rateLimit {
    limit
    cost
    remaining
    resetAt
  }
}
"""


# ── Parsing Helpers ──────────────────────────────────────────────────────────


def _parse_labels(raw_labels: Any) -> list[str]:
    """Extract string label names from a GraphQL labels connection."""
    if not isinstance(raw_labels, dict):
        return []
    nodes = raw_labels.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [str(n.get("name", "")) for n in nodes if isinstance(n, dict) and n.get("name")]


def _parse_assignees(raw_assignees: Any) -> list[str]:
    """Extract assignee logins from a GraphQL assignees connection."""
    if not isinstance(raw_assignees, dict):
        return []
    nodes = raw_assignees.get("nodes")
    if not isinstance(nodes, list):
        return []
    return [str(n.get("login", "")) for n in nodes if isinstance(n, dict) and n.get("login")]


def _parse_milestone_node(node: dict[str, Any]) -> GraphQLMilestone:
    """Convert raw GraphQL milestone node into a typed GraphQLMilestone."""
    total_raw = node.get("totalIssues")
    closed_raw = node.get("closedIssues")
    total_count = total_raw.get("totalCount", 0) if isinstance(total_raw, dict) else 0
    closed_count = closed_raw.get("totalCount", 0) if isinstance(closed_raw, dict) else 0
    return GraphQLMilestone(
        number=int(node.get("number", 0)),
        title=str(node.get("title", "")),
        description=str(node.get("description", "") or ""),
        state=str(node.get("state", "OPEN")),
        due_on=node.get("dueOn"),
        total_issues=total_count,
        closed_issues=closed_count,
    )


def _parse_issue_node(node: dict[str, Any]) -> GraphQLIssue:
    """Convert raw GraphQL issue node into a typed GraphQLIssue."""
    raw_m = node.get("milestone")
    milestone_title = raw_m.get("title") if isinstance(raw_m, dict) else None
    return GraphQLIssue(
        number=int(node.get("number", 0)),
        title=str(node.get("title", "")),
        body=str(node.get("body", "") or ""),
        state=str(node.get("state", "OPEN")),
        url=str(node.get("url", "")),
        created_at=str(node.get("createdAt", "")),
        updated_at=str(node.get("updatedAt", "")),
        milestone=milestone_title,
        labels=_parse_labels(node.get("labels")),
        assignees=_parse_assignees(node.get("assignees")),
    )


def _parse_pr_node(node: dict[str, Any]) -> GraphQLPullRequest:
    """Convert raw GraphQL pull request node into a typed GraphQLPullRequest."""
    raw_m = node.get("milestone")
    milestone_title = raw_m.get("title") if isinstance(raw_m, dict) else None
    return GraphQLPullRequest(
        number=int(node.get("number", 0)),
        title=str(node.get("title", "")),
        state=str(node.get("state", "OPEN")),
        is_draft=bool(node.get("isDraft", False)),
        url=str(node.get("url", "")),
        created_at=str(node.get("createdAt", "")),
        updated_at=str(node.get("updatedAt", "")),
        base_ref=str(node.get("baseRefName", "")),
        head_ref=str(node.get("headRefName", "")),
        mergeable=str(node.get("mergeable")) if node.get("mergeable") else None,
        milestone=milestone_title,
        labels=_parse_labels(node.get("labels")),
    )


def _parse_rate_limit(raw: Any) -> GraphQLRateLimit | None:
    """Convert rateLimit field dictionary into a GraphQLRateLimit model."""
    if not isinstance(raw, dict):
        return None
    return GraphQLRateLimit(
        limit=int(raw.get("limit", 5000)),
        cost=int(raw.get("cost", 1)),
        remaining=int(raw.get("remaining", 5000)),
        reset_at=str(raw.get("resetAt", "")),
    )


# ── Client Implementation ───────────────────────────────────────────────────


def resolve_github_token(explicit_token: str | None = None) -> str | None:
    """Resolve GitHub token from arguments, environment variables, or gh CLI auth."""
    if explicit_token:
        return explicit_token
    for env_var in ("DEVOPS_CLI_GITHUB_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        val = os.environ.get(env_var)
        if val:
            return val
    try:
        res = run_gh([CONST_GH_CLI, "auth", "token"], check=False, quiet=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    except Exception as exc:
        logger.debug("Failed to obtain token from gh CLI: %s", exc)
    return None


class GitHubGraphQLClient:
    """High-performance GitHub GraphQL client with batching and RFC 7234 ETag caching."""

    def __init__(
        self,
        token: str | None = None,
        cache: RFC7234ETagCache | None = None,
        http_client: httpx2.Client | None = None,
    ) -> None:
        from devops_cli.core.repo import resolve_data_path

        self._token = resolve_github_token(token)
        self._cache = cache or RFC7234ETagCache(
            cache_file=resolve_data_path(Path(DEFAULT_DATA_DIR) / CONST_GH_ETAG_CACHE_FILENAME)
        )
        self._http_client = http_client
        self._rate_limiter = GraphQLTokenBucket()

    @property
    def rate_limiter(self) -> GraphQLTokenBucket:
        return self._rate_limiter

    @property
    def cache(self) -> RFC7234ETagCache:
        return self._cache

    def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        use_cache: bool = True,
    ) -> dict[str, Any]:
        """Execute a GraphQL query returning the data payload, using ETag caching when available."""
        delay = self._rate_limiter.estimate_pacing_delay()
        if delay > 0:
            time.sleep(delay)

        cache_key = RFC7234ETagCache.compute_key(query, variables)
        cached_etag, cached_data = self._cache.get(cache_key) if use_cache else (None, None)

        if self._token:
            return self._execute_http(
                query, variables, cache_key, cached_etag, cached_data, use_cache
            )
        return self._execute_cli_fallback(query, variables)

    def _execute_http(
        self,
        query: str,
        variables: dict[str, Any] | None,
        cache_key: str,
        cached_etag: str | None,
        cached_data: Any | None,
        use_cache: bool,
    ) -> dict[str, Any]:
        """Execute direct in-process HTTP POST against GitHub GraphQL endpoint."""
        headers: dict[str, str] = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "User-Agent": CONST_GH_HEADER_USER_AGENT,
        }
        if use_cache and cached_etag:
            headers[CONST_GH_HEADER_IF_NONE_MATCH] = cached_etag

        body = {"query": query, "variables": variables or {}}
        client = self._http_client or httpx2.Client(timeout=DEFAULT_HTTP_TIMEOUT_SECONDS)

        try:
            resp = client.post(CONST_URL_GITHUB_GRAPHQL, headers=headers, json=body)
        finally:
            if not self._http_client:
                client.close()

        if resp.status_code == 304 and cached_data is not None:
            return cached_data  # type: ignore[no-any-return]

        if resp.status_code >= 400:
            self._handle_http_error(resp)

        payload = resp.json()
        if "errors" in payload:
            raise GitHubGraphQLError(
                f"GraphQL query returned errors: {payload['errors']}",
                errors=payload["errors"],
            )

        data = payload.get("data", {})
        if "rateLimit" in data:
            self._rate_limiter.update_from_rate_limit(data["rateLimit"])

        etag = resp.headers.get(CONST_GH_HEADER_ETAG)
        if use_cache and etag:
            self._cache.set(cache_key, etag, data)

        return data  # type: ignore[no-any-return]

    def _execute_cli_fallback(self, query: str, variables: dict[str, Any] | None) -> dict[str, Any]:
        """Fallback to gh api graphql subprocess execution when no PAT is provided."""
        cmd = [CONST_GH_CLI, "api", "graphql", "-f", f"query={query}"]
        if variables:
            for k, v in variables.items():
                cmd.extend(["-F", f"{k}={v}"])
        res = run_gh(cmd, check=False, quiet=True)
        if res.returncode != 0:
            raise GitHubOperationError(
                f"gh api graphql execution failed: {res.stderr}",
                operation="graphql_cli_fallback",
            )
        try:
            payload = json.loads(res.stdout)
            if "errors" in payload:
                raise GitHubGraphQLError("GraphQL errors in CLI response", errors=payload["errors"])
            data = payload.get("data", {})
            if "rateLimit" in data:
                self._rate_limiter.update_from_rate_limit(data["rateLimit"])
            return data  # type: ignore[no-any-return]
        except (json.JSONDecodeError, ValueError) as exc:
            raise GitHubOperationError(
                f"Failed to decode GraphQL output: {exc}",
                operation="graphql_cli_parse",
            ) from exc

    def _handle_http_error(self, resp: httpx2.Response) -> None:
        """Handle HTTP error statuses from the GraphQL API."""
        status = resp.status_code
        if status in (403, 429):
            raise GitHubRateLimitError(
                f"GitHub rate limit or abuse detection triggered (HTTP {status})",
                operation="graphql_execute",
                details={"status_code": str(status)},
            )
        raise GitHubOperationError(
            f"GitHub GraphQL request failed with HTTP {status}: {resp.text}",
            operation="graphql_execute",
            details={"status_code": str(status)},
        )

    # ── High-Level Batch Query Consolidations ─────────────────────────────────

    def fetch_repo_overview(
        self,
        owner: str,
        repo: str,
        issues_limit: int = 50,
        prs_limit: int = 50,
        milestones_limit: int = 20,
        use_cache: bool = True,
    ) -> RepoOverview:
        """Fetch repository details, milestones, issues, and PRs in a single GraphQL query."""
        variables = {
            "owner": owner,
            "name": repo,
            "issuesLimit": issues_limit,
            "prsLimit": prs_limit,
            "milestonesLimit": milestones_limit,
        }
        data = self.execute(GRAPHQL_REPO_OVERVIEW_QUERY, variables, use_cache=use_cache)
        repo_data = data.get("repository") or {}

        milestones = [
            _parse_milestone_node(n)
            for n in repo_data.get("milestones", {}).get("nodes", [])
            if isinstance(n, dict)
        ]
        issues = [
            _parse_issue_node(n)
            for n in repo_data.get("issues", {}).get("nodes", [])
            if isinstance(n, dict)
        ]
        prs = [
            _parse_pr_node(n)
            for n in repo_data.get("pullRequests", {}).get("nodes", [])
            if isinstance(n, dict)
        ]
        rate_limit = _parse_rate_limit(data.get("rateLimit"))

        branch_ref = repo_data.get("defaultBranchRef")
        default_branch = branch_ref.get("name", "") if isinstance(branch_ref, dict) else ""

        return RepoOverview(
            owner=owner,
            name=repo_data.get("name", repo),
            description=str(repo_data.get("description", "") or ""),
            is_private=bool(repo_data.get("isPrivate", False)),
            default_branch=default_branch,
            milestones=milestones,
            issues=issues,
            pull_requests=prs,
            rate_limit=rate_limit,
        )

    def fetch_issues(
        self,
        owner: str,
        repo: str,
        states: list[str] | None = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> list[GraphQLIssue]:
        """Fetch issues via GraphQL query."""
        variables = {
            "owner": owner,
            "name": repo,
            "states": states or ["OPEN"],
            "limit": limit,
        }
        data = self.execute(GRAPHQL_ISSUES_QUERY, variables, use_cache=use_cache)
        nodes = data.get("repository", {}).get("issues", {}).get("nodes", [])
        return [_parse_issue_node(n) for n in nodes if isinstance(n, dict)]

    def fetch_pull_requests(
        self,
        owner: str,
        repo: str,
        states: list[str] | None = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> list[GraphQLPullRequest]:
        """Fetch pull requests via GraphQL query."""
        variables = {
            "owner": owner,
            "name": repo,
            "states": states or ["OPEN"],
            "limit": limit,
        }
        data = self.execute(GRAPHQL_PULL_REQUESTS_QUERY, variables, use_cache=use_cache)
        nodes = data.get("repository", {}).get("pullRequests", {}).get("nodes", [])
        return [_parse_pr_node(n) for n in nodes if isinstance(n, dict)]

    def fetch_milestones(
        self,
        owner: str,
        repo: str,
        states: list[str] | None = None,
        limit: int = 50,
        use_cache: bool = True,
    ) -> list[GraphQLMilestone]:
        """Fetch milestones via GraphQL query."""
        variables = {
            "owner": owner,
            "name": repo,
            "states": states or ["OPEN", "CLOSED"],
            "limit": limit,
        }
        data = self.execute(GRAPHQL_MILESTONES_QUERY, variables, use_cache=use_cache)
        nodes = data.get("repository", {}).get("milestones", {}).get("nodes", [])
        return [_parse_milestone_node(n) for n in nodes if isinstance(n, dict)]
