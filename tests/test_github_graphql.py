"""Unit tests for GitHub GraphQL client, batching, ETag caching, and webhook verification."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import UTC
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from devops_cli.exceptions.git import (
    GitHubGraphQLError,
    GitHubOperationError,
    GitHubRateLimitError,
    GitHubWebhookVerificationError,
)
from devops_cli.github.client import GitHubClient
from devops_cli.github.graphql import (
    GitHubGraphQLClient,
    GraphQLIssue,
    GraphQLMilestone,
    GraphQLPullRequest,
    GraphQLRateLimit,
    GraphQLTokenBucket,
    RepoOverview,
    RFC7234ETagCache,
    WebhookEvent,
    WebhookEventDispatcher,
    resolve_github_token,
    verify_webhook_signature,
)

# ── Models & Parsing Tests ───────────────────────────────────────────────────


def test_graphql_models_instantiation() -> None:
    """Verify typed model construction and defaults."""
    rate_limit = GraphQLRateLimit(
        limit=5000, cost=2, remaining=4998, reset_at="2026-09-19T23:00:00Z"
    )
    milestone = GraphQLMilestone(
        number=1,
        title="v1.0.0",
        description="Release 1.0",
        state="OPEN",
        due_on="2026-10-01T00:00:00Z",
        total_issues=10,
        closed_issues=4,
    )
    issue = GraphQLIssue(
        number=42,
        title="Test Issue",
        body="Body text",
        state="OPEN",
        url="https://example.com/issues/42",
        milestone="v1.0.0",
        labels=["bug", "scope/cli"],
        assignees=["developer1"],
    )
    pr = GraphQLPullRequest(
        number=100,
        title="Test PR",
        state="OPEN",
        is_draft=False,
        url="https://example.com/pulls/100",
        base_ref="main",
        head_ref="feat/branch",
        mergeable="MERGEABLE",
        milestone="v1.0.0",
        labels=["type/feature"],
    )

    assert (rate_limit.limit, rate_limit.cost, rate_limit.remaining) == (5000, 2, 4998)
    assert (milestone.number, milestone.title, milestone.total_issues, milestone.closed_issues) == (
        1,
        "v1.0.0",
        10,
        4,
    )
    assert (issue.number, issue.title, issue.milestone, issue.labels) == (
        42,
        "Test Issue",
        "v1.0.0",
        ["bug", "scope/cli"],
    )
    assert (pr.number, pr.base_ref, pr.head_ref, pr.mergeable) == (
        100,
        "main",
        "feat/branch",
        "MERGEABLE",
    )


def test_repo_overview_model() -> None:
    """Verify consolidated RepoOverview model representation."""
    overview = RepoOverview(
        owner="dan-petty",
        name="devops-cli",
        description="DevOps CLI Tooling",
        is_private=False,
        default_branch="main",
        milestones=[GraphQLMilestone(number=1, title="v1.0.0")],
        issues=[GraphQLIssue(number=10, title="Issue 10")],
        pull_requests=[GraphQLPullRequest(number=20, title="PR 20")],
        rate_limit=GraphQLRateLimit(remaining=4500),
    )

    assert (
        overview.owner,
        overview.name,
        overview.is_private,
        overview.default_branch,
        len(overview.milestones),
        len(overview.issues),
        len(overview.pull_requests),
        overview.rate_limit.remaining if overview.rate_limit else 0,
    ) == ("dan-petty", "devops-cli", False, "main", 1, 1, 1, 4500)


# ── RFC 7234 ETag Cache Tests ────────────────────────────────────────────────


def test_etag_cache_key_computation() -> None:
    """Verify compute_key produces deterministic SHA-256 hashes ignoring whitespace."""
    q1 = 'query { repository(owner: "a", name: "b") { id } }'
    q2 = '   query   { \n  repository(owner: "a", name: "b") { id } \n} '
    vars1 = {"limit": 10, "state": "OPEN"}
    vars2 = {"state": "OPEN", "limit": 10}

    k1 = RFC7234ETagCache.compute_key(q1, vars1)
    k2 = RFC7234ETagCache.compute_key(q2, vars2)
    k3 = RFC7234ETagCache.compute_key(q1, {"limit": 20})

    assert (k1 == k2, k1 != k3) == (True, True)


def test_etag_cache_operations_and_bounding(tmp_path: Path) -> None:
    """Verify set, get, capacity eviction, and clear."""
    cache_file = tmp_path / "cache.json"
    cache = RFC7234ETagCache(cache_file=cache_file, max_entries=2)

    cache.set("key1", "etag1", {"val": 1})
    time.sleep(0.01)
    cache.set("key2", "etag2", {"val": 2})

    t1, d1 = cache.get("key1")
    t2, d2 = cache.get("key2")
    t3, d3 = cache.get("nonexistent")

    assert (t1, d1) == ("etag1", {"val": 1})
    assert (t2, d2) == ("etag2", {"val": 2})
    assert (t3, d3) == (None, None)

    # Exceed capacity: key1 should be evicted as oldest
    time.sleep(0.01)
    cache.set("key3", "etag3", {"val": 3})
    assert (cache.get("key1"), cache.get("key3")) == ((None, None), ("etag3", {"val": 3}))

    # Clear
    cache.clear()
    assert (cache.get("key2"), cache.get("key3"), cache_file.exists()) == (
        (None, None),
        (None, None),
        False,
    )


def test_etag_cache_disk_persistence(tmp_path: Path) -> None:
    """Verify cache entries survive persistence to disk and reload."""
    cache_file = tmp_path / "cache.json"
    cache1 = RFC7234ETagCache(cache_file=cache_file, max_entries=10)
    cache1.set("persisted_key", "etag_disk_123", {"items": [1, 2, 3]})

    # Load in new instance
    cache2 = RFC7234ETagCache(cache_file=cache_file, max_entries=10)
    etag, data = cache2.get("persisted_key")
    assert (etag, data) == ("etag_disk_123", {"items": [1, 2, 3]})


# ── Token-Bucket Rate Optimization Tests ─────────────────────────────────────


def test_graphql_token_bucket_metrics() -> None:
    """Verify rate limit tracking and pacing delay calculations."""
    bucket = GraphQLTokenBucket(safety_threshold=100)
    assert (bucket.remaining, bucket.cost) == (5000, 1)

    # No delay when above safety threshold
    assert bucket.estimate_pacing_delay() == 0.0

    # Update with low remaining and future reset
    now = time.time()
    future_reset = now + 10.0
    from datetime import datetime

    dt_str = datetime.fromtimestamp(future_reset, tz=UTC).isoformat()

    bucket.update_from_rate_limit({"limit": 5000, "remaining": 50, "cost": 1, "resetAt": dt_str})
    assert (bucket.remaining, bucket.cost) == (50, 1)

    delay = bucket.estimate_pacing_delay()
    assert delay > 0.0


# ── Webhook Verification & Dispatcher Tests ──────────────────────────────────


def test_verify_webhook_signature() -> None:
    """Verify constant-time HMAC-SHA256 signature verification."""
    secret = "my-secret-key-12345"
    payload = b'{"action":"opened","issue":{"number":1}}'

    valid_hex = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    valid_sig = f"sha256={valid_hex}"
    invalid_sig = "sha256=badbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadbadb"

    assert (
        verify_webhook_signature(payload, valid_sig, secret),
        verify_webhook_signature(payload, invalid_sig, secret),
        verify_webhook_signature(payload, None, secret),
        verify_webhook_signature(payload, "invalid_prefix", secret),
        verify_webhook_signature(payload, valid_sig, ""),
    ) == (True, False, False, False, False)


def test_webhook_event_dispatcher() -> None:
    """Verify webhook event dispatching to type-specific and wildcard handlers."""
    dispatcher = WebhookEventDispatcher()
    received_issues: list[WebhookEvent] = []
    received_all: list[WebhookEvent] = []

    dispatcher.register("issues", received_issues.append)
    dispatcher.register("*", received_all.append)

    secret = "webhook-secret"
    payload = {
        "action": "labeled",
        "issue": {"number": 15},
        "repository": {"full_name": "example/repo"},
        "sender": {"login": "octocat"},
    }
    raw_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = "sha256=" + hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    success = dispatcher.dispatch(
        "issues",
        payload,
        signature_header=sig,
        secret=secret,
        raw_body=raw_body,
    )

    assert (success, len(received_issues), len(received_all)) == (True, 1, 1)
    ev = received_issues[0]
    assert (ev.event_type, ev.action, ev.repository, ev.sender) == (
        "issues",
        "labeled",
        "example/repo",
        "octocat",
    )


def test_webhook_event_dispatcher_invalid_signature() -> None:
    """Verify dispatch raises GitHubWebhookVerificationError on invalid signature."""
    dispatcher = WebhookEventDispatcher()
    with pytest.raises(GitHubWebhookVerificationError):
        dispatcher.dispatch(
            "issues",
            {"action": "opened"},
            signature_header="sha256=invalid",
            secret="correct-secret",
            raw_body=b'{"action":"opened"}',
        )


# ── Client Execution & Batching Tests ────────────────────────────────────────


def test_resolve_github_token() -> None:
    """Verify token resolution from argument, env, and CLI fallback."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "token_from_env"}, clear=True):
        assert resolve_github_token("explicit_token") == "explicit_token"
        assert resolve_github_token() == "token_from_env"


def test_graphql_client_execute_200_and_cache() -> None:
    """Verify HTTP 200 GraphQL response parsing and ETag caching."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.headers = {"ETag": 'W/"123456"'}
    mock_resp.json.return_value = {
        "data": {
            "repository": {"name": "test-repo"},
            "rateLimit": {"limit": 5000, "remaining": 4999, "cost": 1, "resetAt": ""},
        }
    }

    mock_http = MagicMock()
    mock_http.post.return_value = mock_resp

    cache = RFC7234ETagCache()
    client = GitHubGraphQLClient(token="mock_token", cache=cache, http_client=mock_http)

    res = client.execute("query { repository { name } }")
    assert res == {
        "repository": {"name": "test-repo"},
        "rateLimit": {"limit": 5000, "remaining": 4999, "cost": 1, "resetAt": ""},
    }

    # Verify ETag was stored
    key = RFC7234ETagCache.compute_key("query { repository { name } }")
    cached_etag, cached_data = cache.get(key)
    assert cached_data is not None
    assert (cached_etag, cached_data["repository"]["name"]) == ('W/"123456"', "test-repo")


def test_graphql_client_execute_304_not_modified() -> None:
    """Verify HTTP 304 returns cached payload without modification."""
    cache = RFC7234ETagCache()
    query = "query { viewer { login } }"
    key = RFC7234ETagCache.compute_key(query)
    cache.set(key, 'W/"etag-304"', {"viewer": {"login": "cached-user"}})

    mock_resp = MagicMock()
    mock_resp.status_code = 304

    mock_http = MagicMock()
    mock_http.post.return_value = mock_resp

    client = GitHubGraphQLClient(token="mock_token", cache=cache, http_client=mock_http)
    res = client.execute(query)

    assert res == {"viewer": {"login": "cached-user"}}


def test_graphql_client_execute_errors() -> None:
    """Verify GraphQL syntax / operational errors raise GitHubGraphQLError."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "errors": [{"message": "Field 'invalid' does not exist on type 'Repository'"}]
    }

    mock_http = MagicMock()
    mock_http.post.return_value = mock_resp

    client = GitHubGraphQLClient(token="mock_token", http_client=mock_http)
    with pytest.raises(GitHubGraphQLError) as exc_info:
        client.execute("query { invalid }")
    assert "Field 'invalid' does not exist" in str(exc_info.value)


def test_graphql_client_execute_http_error() -> None:
    """Verify HTTP 403/429 triggers GitHubRateLimitError and other status triggers GitHubOperationError."""
    mock_resp_403 = MagicMock()
    mock_resp_403.status_code = 403
    mock_resp_403.text = "Rate limit exceeded"

    mock_http = MagicMock()
    mock_http.post.return_value = mock_resp_403

    client = GitHubGraphQLClient(token="mock_token", http_client=mock_http)
    with pytest.raises(GitHubRateLimitError):
        client.execute("query { viewer { login } }")

    mock_resp_500 = MagicMock()
    mock_resp_500.status_code = 500
    mock_resp_500.text = "Internal Server Error"
    mock_http.post.return_value = mock_resp_500

    with pytest.raises(GitHubOperationError):
        client.execute("query { viewer { login } }")


def test_graphql_client_fetch_repo_overview() -> None:
    """Verify fetch_repo_overview batch query parsing."""
    client = GitHubGraphQLClient(token="mock_token")
    mock_data = {
        "repository": {
            "name": "devops-cli",
            "nameWithOwner": "dan-petty/devops-cli",
            "description": "DevOps Automation",
            "isPrivate": False,
            "defaultBranchRef": {"name": "main"},
            "milestones": {
                "nodes": [
                    {
                        "number": 1,
                        "title": "v0.2.22",
                        "description": "Milestone desc",
                        "state": "OPEN",
                        "dueOn": "2026-10-01T00:00:00Z",
                        "totalIssues": {"totalCount": 20},
                        "closedIssues": {"totalCount": 5},
                    }
                ]
            },
            "issues": {
                "nodes": [
                    {
                        "number": 316,
                        "title": "GraphQL consolidation",
                        "body": "Issue body",
                        "state": "OPEN",
                        "url": "https://example.com/issues/316",
                        "createdAt": "2026-09-19T20:00:00Z",
                        "updatedAt": "2026-09-19T21:00:00Z",
                        "milestone": {"title": "v0.2.22"},
                        "labels": {"nodes": [{"name": "scope/github"}]},
                        "assignees": {"nodes": [{"login": "dan-petty"}]},
                    }
                ]
            },
            "pullRequests": {
                "nodes": [
                    {
                        "number": 336,
                        "title": "K8s Informer PR",
                        "state": "OPEN",
                        "isDraft": False,
                        "url": "https://example.com/pulls/336",
                        "createdAt": "2026-09-19T21:30:00Z",
                        "updatedAt": "2026-09-19T22:00:00Z",
                        "baseRefName": "release/v0.2.22",
                        "headRefName": "research/k8s-307",
                        "mergeable": "MERGEABLE",
                        "milestone": {"title": "v0.2.22"},
                        "labels": {"nodes": [{"name": "scope/k8s"}]},
                    }
                ]
            },
        },
        "rateLimit": {"limit": 5000, "cost": 1, "remaining": 4995, "resetAt": ""},
    }

    with patch.object(client, "execute", return_value=mock_data):
        overview = client.fetch_repo_overview("dan-petty", "devops-cli")

    assert (
        overview.name,
        overview.default_branch,
        len(overview.milestones),
        len(overview.issues),
        len(overview.pull_requests),
    ) == ("devops-cli", "main", 1, 1, 1)

    m = overview.milestones[0]
    iss = overview.issues[0]
    pr = overview.pull_requests[0]

    assert (m.number, m.title, m.total_issues, m.closed_issues) == (1, "v0.2.22", 20, 5)
    assert (iss.number, iss.title, iss.milestone, iss.labels, iss.assignees) == (
        316,
        "GraphQL consolidation",
        "v0.2.22",
        ["scope/github"],
        ["dan-petty"],
    )
    assert (pr.number, pr.base_ref, pr.head_ref, pr.mergeable) == (
        336,
        "release/v0.2.22",
        "research/k8s-307",
        "MERGEABLE",
    )


def test_graphql_client_fetch_helpers() -> None:
    """Verify fetch_issues, fetch_pull_requests, and fetch_milestones."""
    client = GitHubGraphQLClient(token="mock_token")

    mock_issues_data = {
        "repository": {
            "issues": {
                "nodes": [
                    {
                        "number": 1,
                        "title": "Issue 1",
                        "state": "OPEN",
                        "labels": {"nodes": [{"name": "bug"}]},
                        "assignees": {"nodes": []},
                    }
                ]
            }
        }
    }
    with patch.object(client, "execute", return_value=mock_issues_data):
        issues = client.fetch_issues("owner", "repo")
        assert (len(issues), issues[0].number, issues[0].labels) == (1, 1, ["bug"])

    mock_prs_data = {
        "repository": {
            "pullRequests": {
                "nodes": [
                    {
                        "number": 10,
                        "title": "PR 10",
                        "state": "OPEN",
                        "baseRefName": "main",
                        "labels": {"nodes": []},
                    }
                ]
            }
        }
    }
    with patch.object(client, "execute", return_value=mock_prs_data):
        prs = client.fetch_pull_requests("owner", "repo")
        assert (len(prs), prs[0].number, prs[0].base_ref) == (1, 10, "main")

    mock_ms_data = {
        "repository": {
            "milestones": {
                "nodes": [
                    {
                        "number": 2,
                        "title": "v2.0",
                        "state": "OPEN",
                        "totalIssues": {"totalCount": 5},
                        "closedIssues": {"totalCount": 1},
                    }
                ]
            }
        }
    }
    with patch.object(client, "execute", return_value=mock_ms_data):
        milestones = client.fetch_milestones("owner", "repo")
        assert (len(milestones), milestones[0].number, milestones[0].total_issues) == (1, 2, 5)


def test_github_client_graphql_integration() -> None:
    """Verify GitHubClient initializes GitHubGraphQLClient and get_repo_overview works."""
    with patch("github.Github"):
        gh_client = GitHubClient("mock_token")

    assert isinstance(gh_client.graphql, GitHubGraphQLClient)

    overview_mock = RepoOverview(owner="owner", name="repo")
    with patch.object(
        gh_client.graphql, "fetch_repo_overview", return_value=overview_mock
    ) as mock_fetch:
        res = gh_client.get_repo_overview("owner/repo")
        assert res == overview_mock
        mock_fetch.assert_called_once_with(
            owner="owner",
            repo="repo",
            issues_limit=50,
            prs_limit=50,
            milestones_limit=20,
        )


def test_cli_fallback_execution() -> None:
    """Verify CLI fallback executes run_gh and parses result or raises appropriate errors."""
    client = GitHubGraphQLClient(token=None)
    client._token = None

    # Success case
    mock_res_ok = MagicMock(
        returncode=0,
        stdout=json.dumps(
            {
                "data": {"repository": {"name": "cli-repo"}},
                "rateLimit": {"limit": 5000, "remaining": 4900, "cost": 1, "resetAt": ""},
            }
        ),
        stderr="",
    )
    with patch("devops_cli.github.graphql.run_gh", return_value=mock_res_ok):
        data = client.execute("query { repository { name } }", {"var1": "val1"})
        assert data["repository"]["name"] == "cli-repo"

    # Non-zero returncode
    mock_res_fail = MagicMock(returncode=1, stdout="", stderr="API error occurred")
    with patch("devops_cli.github.graphql.run_gh", return_value=mock_res_fail):
        with pytest.raises(GitHubOperationError):
            client.execute("query { repository { name } }")

    # GraphQL errors in response
    mock_res_gql_err = MagicMock(
        returncode=0,
        stdout=json.dumps({"errors": [{"message": "Syntax error"}]}),
        stderr="",
    )
    with patch("devops_cli.github.graphql.run_gh", return_value=mock_res_gql_err):
        with pytest.raises(GitHubGraphQLError):
            client.execute("query { repository { name } }")

    # Non-JSON response
    mock_res_bad_json = MagicMock(returncode=0, stdout="not valid json", stderr="")
    with patch("devops_cli.github.graphql.run_gh", return_value=mock_res_bad_json):
        with pytest.raises(GitHubOperationError):
            client.execute("query { repository { name } }")


def test_etag_cache_corrupt_file_handling(tmp_path: Path) -> None:
    """Verify corrupt cache file does not prevent initialization."""
    cache_file = tmp_path / "corrupt_cache.json"
    cache_file.write_text("invalid json content", encoding="utf-8")

    cache = RFC7234ETagCache(cache_file=cache_file)
    assert cache.get("any_key") == (None, None)


def test_webhook_dispatcher_handler_exception_handling() -> None:
    """Verify dispatcher catches handler exceptions and continues dispatching."""
    dispatcher = WebhookEventDispatcher()

    def buggy_handler(event: WebhookEvent) -> None:
        raise RuntimeError("boom")

    delivered: list[WebhookEvent] = []
    dispatcher.register("push", buggy_handler)
    dispatcher.register("push", delivered.append)

    res = dispatcher.dispatch("push", {"ref": "refs/heads/main"})
    assert (res, len(delivered)) == (True, 1)
